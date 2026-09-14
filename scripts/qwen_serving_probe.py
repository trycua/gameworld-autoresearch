"""Supervised adapter-serving probe; no deployment or baseline endpoint mutation."""

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time

from fps_bench.campaign_ledger import CampaignLedger
from fps_bench.evaluation_contract import canonical, digest, exclusive_write
from fps_bench.gameworld_protocol import RESPONSE_FORMAT, model_messages, parse_action
from fps_bench.modal_artifacts import ModalSandboxFiles
from fps_bench.modal_scope import inspect_app_scope, validate_app_scope
from fps_bench.qwen_lora import BASE_MODEL, BASE_REVISION, verify_adapter


async def run(args):
    import modal
    from modal.client import _Client
    from modal_proto import api_pb2

    if not re.fullmatch(r'[a-z][a-z0-9-]{0,47}', args.probe_id):
        raise ValueError('Unique bounded probe ID required')
    ledger = CampaignLedger(args.database)
    if ledger.snapshot()['campaign']['id'] != 'gameworld-joint-20260913':
        raise ValueError('Canonical campaign ledger required')
    scope = json.loads(args.scope.read_bytes())
    validate_app_scope(await inspect_app_scope(scope['workspace'], scope['environment'], scope['app']), scope)
    training = json.loads((args.training / 'probe.json').read_bytes())
    adapter = args.training / 'training/adapter'
    manifest = verify_adapter(adapter, training['training']['adapter_manifest_sha256'], BASE_MODEL, BASE_REVISION,
                              digest(canonical(training['source'])), digest(canonical(training['contract'])))
    if digest(args.observation.read_bytes()) != training['source']['image_sha256']:
        raise ValueError('Historical screenshot mismatch')
    client = await _Client.from_env()
    deployed = await asyncio.wait_for(client.stub.FunctionGet(api_pb2.FunctionGetRequest(
        app_name='gameworld-qwen-baseline', object_tag='serve', environment_name='main')), 30)
    images = {item.function.image_id for item in deployed.function.ranked_functions}
    if images != {'im-hmkT3sdePUgwumIXCs7ErB'}:
        raise ValueError('Deployed baseline image changed; inspect before proceeding')
    image_id = next(iter(images))
    worker = Path('scripts/qwen_serving_probe_worker.py').read_bytes()
    request = {'model': BASE_MODEL, 'revision': BASE_REVISION, 'served_model': 'qwen3-vl-2b-instruct-89644892e4d8',
               'payload': {'messages': model_messages(args.observation, []), 'response_format': RESPONSE_FORMAT,
                           'temperature': 0, 'max_tokens': 128, 'seed': 42}}
    plan = {'probe_id': args.probe_id, 'scope': scope, 'image_id': image_id,
            'baseline_function_id': deployed.function_id, 'worker_sha256': digest(worker),
            'request_sha256': digest(canonical(request)), 'adapter_manifest_sha256': digest((adapter / 'adapter-manifest.json').read_bytes()),
            'gpu': 'L4', 'cpu': 4, 'memory_mib': 32768, 'timeout_seconds': 900,
            'cache_volume': 'gameworld-qwen-hf-cache', 'cache_read_only': True, 'block_network': True}
    tags = {'campaign': 'gameworld-joint-20260913', 'probe': args.probe_id, 'identity': digest(canonical(plan))}
    name = 'gw-' + args.probe_id
    try:
        await modal.Sandbox.from_name.aio(scope['app'], name, environment_name=scope['environment'])
    except modal.exception.NotFoundError:
        pass
    else:
        raise ValueError('Existing named sandbox; reconcile rather than retry')
    args.output.mkdir(parents=True, exist_ok=False)
    ledger.reserve(args.probe_id, 'modal_micro_usd', 10_000_000, int(time.time()) + 3600)
    exclusive_write(args.output / 'intent.json', canonical({**plan, 'tags': tags, 'reservation_micro_usd': 10_000_000}))
    exclusive_write(args.output / 'worker-source.py', worker)
    exclusive_write(args.output / 'request.json', canonical(request))
    sandbox = None
    try:
        app = await modal.App.lookup.aio(scope['app'], environment_name=scope['environment'], create_if_missing=False)
        if app.app_id != scope['app_id']:
            raise ValueError('App replaced')
        cache = modal.Volume.from_name('gameworld-qwen-hf-cache', create_if_missing=False).with_mount_options(read_only=True)
        sandbox = await asyncio.wait_for(modal.Sandbox.create.aio(
            '/bin/sleep', '900', app=app, image=modal.Image.from_id(image_id), name=name, tags=tags,
            gpu='L4', cpu=(4, 4), memory=(32768, 32768), timeout=900, block_network=True,
            secrets=[], volumes={'/cache': cache}, network_file_systems={}, include_oidc_identity_token=False,
            env={'HF_HOME': '/cache/huggingface', 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
                 'HF_HUB_DISABLE_TELEMETRY': '1', 'VLLM_NO_USAGE_STATS': '1', 'DO_NOT_TRACK': '1'}), 180)
        exclusive_write(args.output / 'sandbox.json', canonical({'sandbox_id': sandbox.object_id}))
        print(json.dumps({'status': 'created', 'sandbox_id': sandbox.object_id}), flush=True)
        process = await sandbox.exec.aio('mkdir', '-p', '/input/adapter', timeout=30)
        if await process.wait.aio() != 0:
            raise RuntimeError('Input setup failed')
        payloads = {'worker.py': worker, 'request.json': canonical(request),
                    'adapter/adapter-manifest.json': (adapter / 'adapter-manifest.json').read_bytes()}
        payloads.update({'adapter/' + name: (adapter / name).read_bytes() for name in manifest['files']})
        for name, data in payloads.items():
            await sandbox.filesystem.write_bytes.aio(data, '/input/' + name)
        process = await sandbox.exec.aio('python', '/input/worker.py', timeout=780, secrets=[])
        stdout, stderr, code = await asyncio.wait_for(asyncio.gather(
            process.stdout.read.aio(), process.stderr.read.aio(), process.wait.aio()), 800)
        exclusive_write(args.output / 'worker.stdout', stdout.encode())
        exclusive_write(args.output / 'worker.stderr', stderr.encode())
        files = ModalSandboxFiles(sandbox.object_id)
        exclusive_write(args.output / 'server.log', await files.read('/output/server.log'))
        if code != 0:
            raise RuntimeError(f'Serving worker exited {code}; see captured logs')
        data = await files.read('/output/result.json')
        report = json.loads(data)
        if report['worker_sha256'] != digest(worker) or report['vllm_version'] != '0.13.0':
            raise ValueError('Worker source or runtime mismatch')
        if [item['model'] for item in report['results']] != [request['served_model'], 'trained']:
            raise ValueError('Expected exactly one base and one adapter result')
        for item in report['results']:
            response = item['response']
            if response['model'] != item['model'] or len(response['choices']) != 1:
                raise ValueError('Unexpected response model or choice count')
            if response['choices'][0]['finish_reason'] != 'stop':
                raise ValueError('Incomplete generated action')
            parse_action(response['choices'][0]['message']['content'])
        exclusive_write(args.output / 'result.json', data)
        print(json.dumps({'status': 'verified', 'results': [{
            'model': item['model'], 'seconds': item['seconds'],
            'action': item['response']['choices'][0]['message']['content']} for item in report['results']]}), flush=True)
    finally:
        if sandbox is None:
            try:
                sandbox = await asyncio.wait_for(modal.Sandbox.from_name.aio(scope['app'], name, environment_name=scope['environment']), 30)
            except modal.exception.NotFoundError:
                exclusive_write(args.output / 'cleanup-unresolved.json', canonical({'reason': 'No acknowledged sandbox; hold retained'}))
        if sandbox is not None:
            if await sandbox.get_tags.aio() != tags:
                raise ValueError('Refusing mismatched sandbox termination')
            await asyncio.wait_for(sandbox.terminate.aio(wait=True), 120)
            code = await asyncio.wait_for(sandbox.poll.aio(), 30)
            if type(code) is not int:
                raise RuntimeError('Unconfirmed termination')
            exclusive_write(args.output / 'terminated.json', canonical({'sandbox_id': sandbox.object_id,
                'returncode': code, 'checked_at': datetime.now(timezone.utc).isoformat(), 'billing_reconciled': False}))
            print(json.dumps({'status': 'terminated', 'sandbox_id': sandbox.object_id}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('database', 'scope', 'training', 'observation', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--probe-id', required=True)
    asyncio.run(run(parser.parse_args()))


if __name__ == '__main__':
    main()
