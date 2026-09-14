"""Supervised frozen development baseline, not the autonomous campaign launcher."""

import argparse
import asyncio
import io
import json
import os
from pathlib import Path
import secrets
import shlex
import tarfile
import time
import urllib.error
import urllib.request

from fps_bench.campaign_ledger import CampaignLedger
from fps_bench.evaluation_contract import canonical, digest, exclusive_write, safe_file, schedule, verify
from fps_bench.fleet_provider import FleetSDKBackend
from fps_bench.modal_scope import inspect_app_scope, validate_app_scope
from qwen_fleet import check_public_ghcr, gvisor_requests

ANCHOR = 'f2a1161156fa185ba9ad696b8bfc05369420cdde065ebd9fe7ae367faf38d5f9'
DRIVER = '37f78e4db6f96e5b36a6dc2912ca6b1539bf938569967aaade99ab5fc81e0ec4'
IMAGE = 'im-hmkT3sdePUgwumIXCs7ErB'


def archive_files(files):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w:gz') as archive:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(data), 0o400
            archive.addfile(info, io.BytesIO(data))
    return output.getvalue()


def extract_artifacts(data, destination):
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        members = archive.getmembers()
        if len(members) > 1000 or sum(item.size for item in members) > 128 * 1024 * 1024:
            raise ValueError('Artifact archive exceeds bounds')
        names = set()
        for item in members:
            if not item.isfile() or item.name in names:
                raise ValueError('Only unique regular artifacts are accepted')
            names.add(item.name)
            safe_file(destination, item.name)
        for item in members:
            exclusive_write(safe_file(destination, item.name), archive.extractfile(item).read(), 0o400)


def verify_episode(root, assignment, contract):
    manifest = json.loads((root / 'manifest.json').read_bytes())
    summary = json.loads((root / 'summary.json').read_bytes())
    config = {**contract['episode_template'], 'seed': assignment['seed']}
    if (manifest['status'] != 'complete' or manifest['contract_sha256'] != ANCHOR
            or manifest['config'] != config or manifest['config_sha256'] != digest(canonical(config))
            or manifest['driver_sha256'] != DRIVER or manifest['source']['frozen_hashes'] != contract['source_hashes']):
        raise ValueError('Episode provenance differs from assignment')
    for key in ('gameworld_revision', 'games_revision'):
        if manifest[key] != contract['spec']['provenance'][key]:
            raise ValueError('Upstream revision mismatch')
    rows = [json.loads(line) for line in (root / 'trajectory.jsonl').read_text().splitlines()]
    if (summary['status'] != 'complete' or type(summary['success']) is not bool
            or not 1 <= len(rows) <= config['max_steps'] or summary['steps'] != len(rows)):
        raise ValueError('Incomplete episode')
    for step, row in enumerate(rows):
        if row['step'] != step or row['observation'] != f'{step:03d}.png':
            raise ValueError('Trajectory ordering mismatch')
        if digest((root / row['observation']).read_bytes()) != row['observation_sha256']:
            raise ValueError('Screenshot hash mismatch')
        response = json.loads((root / f'{step:03d}-response.json').read_bytes())
        if response['choices'][0]['message']['content'] != row['response']:
            raise ValueError('Response artifact differs from trajectory')
    if json.loads((root / 'final-state.json').read_bytes()) != rows[-1]['after']:
        raise ValueError('Final state differs from trajectory')
    return {**assignment, 'summary': summary, 'artifact_sha256': {
        path.name: digest(path.read_bytes()) for path in sorted(root.iterdir()) if path.is_file()},
        'verification': 'provenance and artifact consistency; independent evaluator replay pending'}


async def shell(sandbox, command):
    result = await sandbox.shell.run(command, timeout=25)
    if not result.success:
        raise RuntimeError('Fleet shell failed: ' + result.stderr[-1000:] + result.stdout[-1000:])
    return result.stdout


async def release_claim(handle, pool_name, name, backend=None, timeout_seconds=120):
    backend = backend or FleetSDKBackend()
    await asyncio.wait_for(handle.release(), 30)
    deadline = time.monotonic() + timeout_seconds
    while await asyncio.wait_for(backend.find_claim(pool_name, name), 30) is not None:
        if time.monotonic() >= deadline:
            raise TimeoutError('Claim release unconfirmed; cleanup obligation retained')
        await asyncio.sleep(2)


async def collect(args):
    import modal
    from cua_sandbox import Pool
    from cua_sandbox.pool import Template, _ClaimHandle

    contract = verify(args.custody / 'contract.json', ANCHOR, args.custody / 'evaluator',
                      args.custody / 'upstream', args.custody / 'games')
    assignments = schedule(contract, 'development', ['baseline'], 20260913)[:args.episodes]
    ledger = CampaignLedger(args.database)
    if ledger.snapshot()['campaign']['id'] != 'gameworld-joint-20260913':
        raise ValueError('Canonical campaign ledger required')
    scope = json.loads(args.scope.read_bytes())
    validate_app_scope(await inspect_app_scope(scope['workspace'], scope['environment'], scope['app']), scope)
    args.output.mkdir(parents=True, exist_ok=False)
    identity = 'baseline-' + time.strftime('%Y%m%d-%H%M%S', time.gmtime()) + '-' + secrets.token_hex(3)
    metadata = {'pool': 'gw-' + identity, 'image': contract['spec']['provenance']['image'],
                'cpu': 4, 'memory_mb': 16384, 'pool_ttl_seconds': 21600}
    check_public_ghcr(metadata['image'])
    ledger.reserve(identity, 'modal_micro_usd', 25_000_000, int(time.time()) + 10800)
    intent = {'id': identity, 'scope': scope, 'image_id': IMAGE, 'pool': metadata,
              'assignments': assignments, 'contract_sha256': ANCHOR, 'reservation_micro_usd': 25_000_000,
              'gpu': 'L4', 'cpu': 4, 'memory_mib': 32768, 'gpu_timeout_seconds': 7200,
              'desktop_concurrency': 2, 'supervised_only': True}
    exclusive_write(args.output / 'intent.json', canonical(intent))
    exclusive_write(args.output / 'runner-source.py', Path(__file__).read_bytes())
    files = {name: safe_file(args.custody / 'evaluator', name).read_bytes() for name in contract['source_hashes']}
    files['contract.json'] = (args.custody / 'contract.json').read_bytes()
    bundle = archive_files(files)
    exclusive_write(args.output / 'frozen-snapshot.tar.gz', bundle)
    tags = {'campaign': 'gameworld-joint-20260913', 'baseline': identity, 'identity': digest(canonical(intent))}
    gpu, pool = None, None
    claims = {}
    api_key = secrets.token_urlsafe(32)
    try:
        pool_request, template_request = gvisor_requests(metadata)
        pool = await Pool.reconcile(pool_request)
        await Template.reconcile(template_request)
        observation = await FleetSDKBackend().inspect_pool(metadata['pool'])
        exclusive_write(args.output / 'pool-observation.json', canonical(observation))
        if (not observation['runtime'].endswith('GVISOR') or observation['image'] != metadata['image']
                or observation['min_pool_size'] != 0 or observation['max_pool_size'] != 20):
            raise ValueError('Unexpected Fleet pool configuration')
        for lane in range(min(2, args.episodes)):
            name = f'baseline-{lane}'
            claims[name] = _ClaimHandle(namespace=metadata['pool'], name=name, pool_name=metadata['pool'])
            exclusive_write(args.output / (name + '-claim.json'), canonical(claims[name].to_dict()))
            await asyncio.wait_for(pool.create_claim(name=name, ttl_seconds_after_created=9000), 60)
        desktops = await asyncio.wait_for(asyncio.gather(*[handle.wait(time_to_start=900) for handle in claims.values()]), 960)
        for desktop in desktops:
            await desktop.files.write_bytes('/tmp/frozen-snapshot.tar.gz', bundle)
            await shell(desktop, 'mkdir /tmp/frozen-evaluator && tar xzf /tmp/frozen-snapshot.tar.gz -C /tmp/frozen-evaluator')
            check = ('cd /tmp/frozen-evaluator && /opt/gameworld-venv/bin/python -m fps_bench.evaluation_contract verify '
                     '--contract contract.json --expected-hash ' + ANCHOR + ' --workspace . --upstream /opt/GameWorld '
                     '--games /opt/GameWorld/games/gameworld-games && sha256sum /usr/local/bin/cua-driver')
            checked = await shell(desktop, check)
            if DRIVER not in checked:
                raise ValueError('Desktop driver mismatch')
        print(json.dumps({'status': 'desktops-verified', 'pool': metadata['pool']}), flush=True)
        app = await modal.App.lookup.aio(scope['app'], environment_name=scope['environment'], create_if_missing=False)
        if app.app_id != scope['app_id']:
            raise ValueError('Modal app replaced')
        cache = modal.Volume.from_name('gameworld-qwen-hf-cache', create_if_missing=False).with_mount_options(read_only=True)
        gpu = await asyncio.wait_for(modal.Sandbox.create.aio(
            '/bin/sleep', '7200', name=identity, app=app, image=modal.Image.from_id(IMAGE),
            gpu='L4', cpu=(4, 4), memory=(32768, 32768), timeout=7200, tags=tags,
            encrypted_ports=[8000], outbound_cidr_allowlist=[], secrets=[], volumes={'/cache': cache},
            network_file_systems={}, include_oidc_identity_token=False,
            env={'HF_HOME': '/cache/huggingface', 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
                 'HF_HUB_DISABLE_TELEMETRY': '1', 'VLLM_NO_USAGE_STATS': '1', 'DO_NOT_TRACK': '1'}), 180)
        exclusive_write(args.output / 'gpu.json', canonical({'sandbox_id': gpu.object_id, 'tags': tags}))
        config = contract['episode_template']
        command = ['vllm', 'serve', config['model'], '--revision', config['revision'], '--tokenizer-revision', config['revision'],
                   '--served-model-name', config['served_model'], '--host', '0.0.0.0', '--port', '8000',
                   '--dtype', 'bfloat16', '--max-model-len', '8192', '--max-num-seqs', '1',
                   '--gpu-memory-utilization', '0.85', '--limit-mm-per-prompt', '{"image":1,"video":0}',
                   '--seed', '42', '--generation-config', 'vllm', '--enforce-eager']
        await gpu.filesystem.write_bytes.aio(canonical({'command': command, 'api_key': api_key}), '/tmp/server.json')
        launch = "import os,json,subprocess,importlib.metadata; assert importlib.metadata.version('vllm')=='0.13.0'; c=json.load(open('/tmp/server.json')); log=open('/tmp/server.log','w'); subprocess.Popen(c['command'],stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'VLLM_API_KEY':c['api_key']},start_new_session=True)"
        process = await gpu.exec.aio('python', '-c', launch, timeout=30)
        if await process.wait.aio() != 0:
            raise RuntimeError('Serving launch failed')
        tunnels = await gpu.tunnels.aio()
        base = tunnels[8000].url + '/v1'
        def models():
            query = urllib.request.Request(base + '/models', headers={'Authorization': 'Bearer ' + api_key})
            with urllib.request.urlopen(query, timeout=15) as response:
                return json.load(response)
        started = time.monotonic()
        while True:
            try:
                response = await asyncio.to_thread(models)
                if config['served_model'] not in [item['id'] for item in response['data']]:
                    raise ValueError('Serving model mismatch')
                break
            except OSError:
                if time.monotonic() - started > 600:
                    raise TimeoutError('Serving readiness exceeded 600 seconds')
                await asyncio.sleep(5)
        exclusive_write(args.output / 'serving.json', canonical({'base_url': base, 'models': response, 'command': command}))
        print(json.dumps({'status': 'inference-ready', 'sandbox_id': gpu.object_id}), flush=True)
        queue = asyncio.Queue()
        for assignment in assignments:
            queue.put_nowait(assignment)
        async def lane(desktop):
            await desktop.files.write_text('/tmp/baseline-auth.env', 'export QWEN_BASE_URL=' + shlex.quote(base) + '\nexport QWEN_API_KEY=' + shlex.quote(api_key) + '\n')
            await shell(desktop, 'chmod 600 /tmp/baseline-auth.env')
            try:
                while not queue.empty():
                    assignment = queue.get_nowait()
                    episode = assignment['episode_id']
                    root = args.output / episode
                    root.mkdir(exist_ok=False)
                    exclusive_write(root / 'assignment.json', canonical(assignment))
                    await desktop.files.write_bytes('/tmp/' + episode + '.json', canonical({**config, 'seed': assignment['seed']}))
                    command = ('cd /tmp/frozen-evaluator || exit 1\nexport DISPLAY=${DISPLAY:-:1}\nsource /tmp/baseline-auth.env\n'
                        'timeout --kill-after=10s 940s /opt/gameworld-venv/bin/python -m fps_bench.gameworld_baseline '
                        '--output /tmp/' + episode + ' --config /tmp/' + episode + '.json --contract contract.json '
                        '--contract-sha256 ' + ANCHOR + ' --expected-driver-sha256 ' + DRIVER +
                        ' --expected-served-model ' + shlex.quote(config['served_model']) + '\nstatus=$?\nprintf "%s" "$status" > /tmp/' + episode + '.rc\n')
                    await desktop.files.write_text('/tmp/' + episode + '.sh', command)
                    launcher = "import subprocess; subprocess.Popen(['bash','/tmp/" + episode + ".sh'],stdin=subprocess.DEVNULL,stdout=open('/tmp/" + episode + ".log','w'),stderr=subprocess.STDOUT,start_new_session=True)"
                    await shell(desktop, '/opt/gameworld-venv/bin/python -c ' + shlex.quote(launcher))
                    exclusive_write(root / 'dispatched.json', canonical({'at': time.time(), 'claim': desktop.claim_name}))
                    deadline = time.monotonic() + 1000
                    while True:
                        status = await shell(desktop, 'if test -f /tmp/' + episode + '.rc; then cat /tmp/' + episode + '.rc; else echo running; fi')
                        if status.strip() != 'running':
                            break
                        if time.monotonic() > deadline:
                            raise TimeoutError('Episode completion unknown')
                        await asyncio.sleep(5)
                    log = await desktop.files.read_bytes('/tmp/' + episode + '.log')
                    exclusive_write(root / 'episode.log', log)
                    if status.strip() != '0':
                        exclusive_write(root / 'failed.json', canonical({'exit_code': status.strip()}))
                        raise RuntimeError('Frozen episode failed: ' + episode)
                    archive_command = "import tarfile,pathlib; root=pathlib.Path('/tmp/" + episode + "'); archive=tarfile.open('/tmp/" + episode + ".tar.gz','w:gz'); [archive.add(p,arcname=p.name,recursive=False) for p in root.iterdir() if p.is_file()]; archive.close()"
                    await shell(desktop, '/opt/gameworld-venv/bin/python -c ' + shlex.quote(archive_command))
                    remote = '/tmp/' + episode + '.tar.gz'
                    size = await desktop.files.size(remote)
                    if size > 64 * 1024 * 1024:
                        raise ValueError('Compressed artifacts exceed bounds')
                    data = b''.join([await desktop.files.read_bytes(remote, offset=offset, length=min(1024*1024, size-offset)) for offset in range(0, size, 1024*1024)])
                    if len(data) != size:
                        raise ValueError('Incomplete artifact transfer')
                    extract_artifacts(data, root / 'artifacts')
                    verified = verify_episode(root / 'artifacts', assignment, contract)
                    exclusive_write(root / 'verified.json', canonical(verified))
                    print(json.dumps({'status': 'episode-complete', 'episode_id': episode,
                                      'success': verified['summary']['success'], 'steps': verified['summary']['steps']}), flush=True)
            finally:
                await desktop.disconnect()
        async with asyncio.TaskGroup() as tasks:
            for desktop in desktops:
                tasks.create_task(lane(desktop))
        exclusive_write(args.output / 'complete.json', canonical({'episodes': len(assignments), 'at': time.time(), 'independent_replay_pending': True}))
    finally:
        errors = []
        if gpu is None:
            try:
                gpu = await modal.Sandbox.from_name.aio(scope['app'], identity, environment_name=scope['environment'])
            except modal.exception.NotFoundError:
                pass
        if gpu is not None:
            try:
                if await gpu.get_tags.aio() != tags:
                    raise ValueError('GPU ownership mismatch')
                try:
                    from fps_bench.modal_artifacts import ModalSandboxFiles
                    exclusive_write(args.output / 'server.log', await ModalSandboxFiles(gpu.object_id).read('/tmp/server.log'))
                except Exception as error:
                    errors.append({'log_export': type(error).__name__})
                await asyncio.wait_for(gpu.terminate.aio(wait=True), 120)
                code = await gpu.poll.aio()
                if type(code) is not int:
                    raise RuntimeError('GPU termination unconfirmed')
                exclusive_write(args.output / 'gpu-terminated.json', canonical({'sandbox_id': gpu.object_id, 'returncode': code, 'at': time.time()}))
            except Exception as error:
                errors.append({'gpu_cleanup': type(error).__name__})
        for name, handle in claims.items():
            try:
                await release_claim(handle, metadata['pool'], name)
            except Exception as error:
                errors.append({'claim': name, 'cleanup_error': type(error).__name__})
        exclusive_write(args.output / 'cleanup.json', canonical({'errors': errors, 'at': time.time(), 'billing_reconciled': False}))
        if errors:
            raise RuntimeError('Cleanup/export requires reconciliation: ' + json.dumps(errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('database', 'scope', 'custody', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--episodes', type=int, choices=range(1, 17), default=16)
    args = parser.parse_args()
    asyncio.run(collect(args))


if __name__ == '__main__':
    main()
