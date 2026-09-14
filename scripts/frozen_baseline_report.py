"""Replay frozen evaluator results and report seed-cluster uncertainty on baseline."""

import argparse
import asyncio
from dataclasses import asdict
import importlib.util
import json
import math
from pathlib import Path
import statistics
import sys

from frozen_baseline import ANCHOR, verify_episode
from fps_bench.evaluation_contract import canonical, digest, exclusive_write, schedule, verify
from fps_bench.gameworld_protocol import parse_action


async def replay_episode(root, assignment, contract, custody):
    import yaml

    report = verify_episode(root, assignment, contract)
    task = yaml.safe_load((custody / 'upstream/catalog/tasks/01_2048/01_01.yaml').read_text())
    if json.loads((root / 'task.json').read_bytes()) != task:
        raise ValueError('Recorded task differs from frozen custody')
    path = custody / 'upstream/env/task_evaluator.py'
    spec = importlib.util.spec_from_file_location('frozen_task_evaluator', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    evaluate = module.build_task_evaluator(task['evaluator_config'], max_steps=contract['episode_template']['max_steps'])
    rows = [json.loads(line) for line in (root / 'trajectory.jsonl').read_text().splitlines()]
    metrics, invalid, usage = {}, 0, {'prompt_tokens': 0, 'completion_tokens': 0}
    for step, row in enumerate(rows):
        if row['before']['seed'] != assignment['seed'] or row['after']['seed'] != assignment['seed']:
            raise ValueError('State seed differs from assignment')
        try:
            action = parse_action(row['response'])
        except (ValueError, TypeError):
            action = None
            invalid += 1
        if action != row['action'] or (action is None) != (row['invalid_action'] is not None):
            raise ValueError('Recorded action differs from frozen parser')
        result = await evaluate(row['after'], step + 1, metrics)
        if asdict(result) != row['evaluation']:
            raise ValueError('Per-step evaluator replay differs')
        if (result.should_stop or result.should_reset) and step != len(rows) - 1:
            raise ValueError('Trajectory continued beyond evaluator stop')
        metrics = result.metrics
        response = json.loads((root / f'{step:03d}-response.json').read_bytes())
        for name in usage:
            value = (response.get('usage') or {}).get(name, 0) or 0
            if type(value) is not int or value < 0:
                raise ValueError('Invalid inference usage')
            usage[name] += value
    result = await evaluate(rows[-1]['after'], len(rows), metrics, finalized=True)
    summary = report['summary']
    if (asdict(result) != summary['evaluation'] or (result.status == 'success') != summary['success']
            or invalid != summary['invalid_actions'] or usage != summary['usage']):
        raise ValueError('Summary differs from controller replay')
    if not math.isfinite(summary['seconds']) or not 0 < summary['seconds'] <= 900:
        raise ValueError('Invalid episode duration')
    return {**assignment, 'contract_sha256': ANCHOR, **summary,
            'artifact_sha256': report['artifact_sha256'], 'verification': 'frozen evaluator replay on trusted controller'}


def baseline_statistics(rows, contract):
    settings = contract['public_splits']['development']
    expected = {(seed, repeat) for seed in settings['seeds'] for repeat in range(settings['repeats'])}
    indexed = {}
    for row in rows:
        key = (row['seed'], row['repeat'])
        if (key not in expected or key in indexed or row['candidate'] != 'baseline'
                or row['split'] != 'development' or row['contract_sha256'] != ANCHOR
                or row['status'] != 'complete' or type(row['success']) is not bool):
            raise ValueError('Invalid, duplicate or cross-split baseline result')
        indexed[key] = row
    if set(indexed) != expected:
        return {'status': 'incomplete', 'verified_episodes': len(rows), 'required_episodes': len(expected),
                'success_rate': None, 'missing': len(expected - set(indexed))}
    seed_rates = [statistics.mean(indexed[seed, repeat]['success'] for repeat in range(settings['repeats']))
                  for seed in settings['seeds']]
    alpha = 0.05
    radius = math.sqrt(math.log(2 / alpha) / (2 * len(seed_rates)))
    mean = statistics.mean(seed_rates)
    return {'status': 'complete', 'episodes': len(rows), 'independent_seed_clusters': len(seed_rates),
            'successes': sum(row['success'] for row in rows), 'success_rate': mean,
            'seed_rates': seed_rates,
            'success_rate_95pct_hoeffding': [max(0, mean - radius), min(1, mean + radius)],
            'uncertainty_note': 'Conservative bounded-variable interval across independent seed clusters, not 16 independent trials; assumes sampled seeds represent the task seed distribution.',
            'median_seconds': statistics.median(row['seconds'] for row in rows),
            'mean_steps': statistics.mean(row['steps'] for row in rows),
            'invalid_action_rate': sum(row['invalid_actions'] for row in rows) / sum(row['steps'] for row in rows),
            'usage': {key: sum(row['usage'][key] for row in rows) for key in ('prompt_tokens', 'completion_tokens')}}


async def report(args):
    contract = verify(args.custody / 'contract.json', ANCHOR, args.custody / 'evaluator',
                      args.custody / 'upstream', args.custody / 'games')
    rows = []
    for assignment in schedule(contract, 'development', ['baseline'], 20260913):
        root = args.run / assignment['episode_id']
        if not (root / 'verified.json').exists():
            continue
        recorded = json.loads((root / 'assignment.json').read_bytes())
        if recorded != assignment:
            raise ValueError('Persisted assignment differs from frozen schedule')
        rows.append(await replay_episode(root / 'artifacts', assignment, contract, args.custody))
    result = {'contract_sha256': ANCHOR, 'run': str(args.run), 'rows': rows,
              'baseline': baseline_statistics(rows, contract), 'candidate_selection': False}
    exclusive_write(args.output, canonical(result))
    print(json.dumps(result['baseline']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('custody', 'run', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    asyncio.run(report(parser.parse_args()))
