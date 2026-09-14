"""Export verified, positive-progress train observations as a self-imitation option."""

import argparse
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import tarfile

import yaml

from fps_bench.evaluation_contract import canonical, digest, exclusive_write, verify
from fps_bench.gameworld_research import DEFAULT_CATALOG, load_baseline, load_policy
from fps_bench.gameworld_suite_episode import prompt, resolve_action, semantic_controls
from fps_bench.gameworld_training import verify_sft_dataset
from fps_bench.qwen_protocol import messages
from fps_bench.training_data import ImageBytes, MAX_FILE_BYTES


def archive_file(archive, name):
    matches = [member for member in archive.getmembers() if member.name == name]
    if len(matches) != 1 or not matches[0].isfile() or matches[0].size > MAX_FILE_BYTES:
        raise ValueError("Missing, duplicate, linked, or oversized baseline artifact")
    return archive.extractfile(matches[0]).read()


def episode_sample(identity, archive_bytes, receipt, game_spec, task_spec, driver_hash, catalog_hash):
    from PIL import Image

    if digest(archive_bytes) != receipt['archive_sha256']:
        raise ValueError("Baseline archive differs from its receipt")
    game, task = identity.split('--')
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode='r:gz') as archive:
        manifest = json.loads(archive_file(archive, identity + '/manifest.json'))
        if (manifest['driver_sha256'] != driver_hash
                or manifest['protocol'] != 'one-step-current-driver-compatibility-v1'
                or manifest['config']['catalog_manifest_sha256'] != catalog_hash
                or manifest['config']['game'] != game or manifest['config']['task'] != task):
            raise ValueError("Baseline policy input provenance changed")
        rows = archive_file(archive, identity + '/trajectory.jsonl').splitlines()
        if len(rows) != 1:
            raise ValueError("Only one-step compatibility observations are admitted")
        row = json.loads(rows[0])
        if (row['step'] != 0 or row['observation'] != '000.png'
                or row['invalid_action'] is not None or row['execution']['status'] != 'executed'):
            raise ValueError("Baseline observation is not a valid executed first step")
        controls = semantic_controls(game_spec)
        if resolve_action(row['response'], controls) != row['action']:
            raise ValueError("Recorded action differs from the teacher response")
        image = archive_file(archive, identity + '/000.png')
    if digest(image) != row['observation_sha256']:
        raise ValueError("Baseline screenshot digest changed")
    with Image.open(io.BytesIO(image)) as decoded:
        if decoded.format != 'PNG':
            raise ValueError("PNG screenshot required")
        decoded.verify()
    image_name = 'images/' + digest(image) + '.png'
    sample_messages = messages(ImageBytes(image), [])
    sample_messages[0]['content'] = prompt(game_spec, task_spec, controls)
    sample_messages[1]['content'][1] = {'type': 'image', 'image': image_name}
    sample = {'id': identity + ':step-0', 'messages': sample_messages,
              'completion': [{'role': 'assistant', 'content': row['response']}]}
    return sample, image_name, image


def export(baseline_root, gameworld, contract_path, contract_hash, output):
    contract = verify(contract_path, contract_hash)
    _, context = load_policy()
    if (contract['spec']['policy_sha256'] != context['policy_sha256']
            or contract['spec']['catalog_manifest_sha256'] != context['catalog_manifest_sha256']):
        raise ValueError("SFT export requires the current frozen policy and catalog")
    baseline = load_baseline(baseline_root, DEFAULT_CATALOG, context['catalog_manifest_sha256'])
    if contract['spec']['baseline_sha256'] != baseline['baseline_sha256']:
        raise ValueError("Baseline evidence differs from the frozen contract")
    specs = {game['game']: game for game in context['manifest']['games']}
    samples, images, provenance = [], {}, []
    for identity in sorted(context['splits']['train']):
        receipt_path = baseline_root / 'episodes' / identity / 'receipt.json'
        if not receipt_path.is_file():
            continue
        receipt_data = receipt_path.read_bytes()
        receipt = json.loads(receipt_data)
        summary = receipt['summary']
        if (summary['execution_status'] != 'executed' or summary['invalid_actions'] != 0
                or not 0 < summary.get('progress', 0) <= 1):
            continue
        game, task = identity.split('--')
        game_bytes = (gameworld / 'catalog/games' / (game + '.yaml')).read_bytes()
        task_bytes = (gameworld / 'catalog/tasks' / game / (task + '.yaml')).read_bytes()
        task_spec = next(item for item in specs[game]['tasks'] if item['task'] == task)
        if (digest(game_bytes) != specs[game]['game_spec_sha256']
                or digest(task_bytes) != task_spec['task_spec_sha256']):
            raise ValueError("Public task prompt specifications differ from the frozen catalog")
        archive_bytes = (receipt_path.parent / 'artifacts.tar.gz').read_bytes()
        sample, image_name, image = episode_sample(
            identity, archive_bytes, receipt, yaml.safe_load(game_bytes), yaml.safe_load(task_bytes),
            contract['spec']['baseline_driver_sha256'], context['catalog_manifest_sha256'])
        samples.append(sample)
        images[image_name] = image
        provenance.append({'task': identity, 'receipt_sha256': digest(receipt_data),
                           'archive_sha256': receipt['archive_sha256'],
                           'game_spec_sha256': digest(game_bytes), 'task_spec_sha256': digest(task_bytes)})
    if not samples:
        raise ValueError("No eligible train observations; no dataset was created")
    tasks = sorted(item['task'] for item in provenance)
    audit = {'schema_version': 1, 'baseline_sha256': baseline['baseline_sha256'],
             'builder_sha256': digest(Path(__file__).read_bytes()), 'artifacts': provenance,
             'selection': 'train-only executed first steps with positive recorded progress',
             'limitation': 'Base-model self-imitation, not expert demonstrations or causal action credit; progress may be automatic.'}
    source = {'schema_version': 1, 'kind': 'teacher-policy', 'tasks': tasks,
              'rights': 'User-authorized private training on recorded campaign observations and model outputs; not a redistribution license.',
              'artifact_sha256': digest(canonical(audit)), 'created_at': datetime.now(timezone.utc).isoformat(),
              'evaluation_policy_contains_privileged_state': False}
    output.mkdir(parents=True, exist_ok=False)
    dataset = output / 'dataset'
    sample_bytes = b''.join(canonical(sample) for sample in samples)
    exclusive_write(dataset / 'samples.jsonl', sample_bytes, 0o400)
    for name, data in images.items():
        exclusive_write(dataset / name, data, 0o400)
    manifest = {'schema_version': 1, 'purpose': 'train-only-action-imitation',
                'contract_sha256': contract_hash, 'samples': len(samples), 'episodes': [],
                'files': {'samples.jsonl': digest(sample_bytes), **{name: digest(data) for name, data in images.items()}},
                'gameworld': {'schema_version': 1, 'tasks': tasks,
                              'driver_sha256': contract['spec']['baseline_driver_sha256'],
                              'source_receipt_sha256': digest(canonical(source))}}
    manifest_bytes = canonical(manifest)
    exclusive_write(dataset / 'dataset.json', manifest_bytes, 0o400)
    exclusive_write(output / 'provenance.json', canonical(audit), 0o400)
    exclusive_write(output / 'source-receipt.json', canonical(source), 0o400)
    verify_sft_dataset(dataset, digest(manifest_bytes), contract_hash, context, tasks,
                       contract['spec']['baseline_driver_sha256'], source)
    catalog = {'schema_version': 1, 'sources': [{
        'id': 'baseline-positive-train-self-imitation', 'tasks': tasks,
        'dataset_root': str(dataset.resolve()), 'dataset_sha256': digest(manifest_bytes),
        'source_receipt': str((output / 'source-receipt.json').resolve())}]}
    exclusive_write(output / 'sources.json', canonical(catalog), 0o400)
    return {'samples': len(samples), 'games': len({task.split('--')[0] for task in tasks}),
            'dataset_sha256': digest(manifest_bytes), 'catalog': str(output / 'sources.json')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'gameworld', 'contract', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--contract-sha256', required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.baseline, args.gameworld, args.contract, args.contract_sha256, args.output)))
