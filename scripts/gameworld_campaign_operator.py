"""Operate the frozen coordinator with billing waits and explicit dataset handoffs."""

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
from pathlib import Path
import time

from fps_bench.evaluation_contract import canonical, digest
from fps_bench.gameworld_billing import ACTIVE_STATES, GameWorldModalReconciler, hour
from fps_bench.gameworld_research_worker import GameWorldResearchWorker
from fps_bench.gameworld_runner import GameWorldProviderRunner, MODAL_FIELDS
from scripts.gameworld_capacity_operations import CapacityCoordinator, replace_expired_serving


class AppScopedReconciler(GameWorldModalReconciler):
    def plan(self, now=None):
        now = datetime.now(timezone.utc) if now is None else now.astimezone(timezone.utc)
        with self.ledger.transaction() as connection:
            jobs = {row['id']: dict(row) for row in connection.execute(
                "SELECT * FROM jobs WHERE kind IN ('training','serving')")}
            starts = {json.loads(row['payload'])['id']: row['timestamp'] for row in connection.execute(
                "SELECT timestamp,payload FROM events WHERE kind='reserved'")}
            groups = {}
            active_apps = set()
            unbound = False
            for reservation in connection.execute(
                    "SELECT * FROM reservations WHERE resource='modal_micro_usd' AND state='held'"):
                job_id = reservation['id'].removeprefix('job:').removesuffix(':modal_micro_usd')
                job = jobs.get(job_id)
                if job is None:
                    unbound = True
                    continue
                table = ('modal_training_launches' if job['kind'] == 'training'
                         else 'gameworld_serving_launches')
                if not connection.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
                    unbound = True
                    continue
                launch = connection.execute(f'SELECT plan FROM {table} WHERE job_id=?', (job_id,)).fetchone()
                if launch is None:
                    unbound = True
                    continue
                plan = json.loads(launch['plan'])
                identity = (plan['workspace'], plan['environment'], plan['app_id'])
                if job['state'] in ACTIVE_STATES:
                    active_apps.add(identity)
                    continue
                if job['state'] != 'billing_pending':
                    unbound = True
                    continue
                launch, plan, receipt = self._launch(connection, job)
                groups.setdefault(identity, []).append({
                    'job_id': job_id, 'reservation_id': reservation['id'], 'kind': 'sandbox',
                    'provider_id': launch['sandbox_id'], 'app_id': plan['app_id'],
                    'expected_tags': plan['tags'], 'finished_at': receipt['checked_at'],
                })
            if unbound:
                return None
            for identity, resources in sorted(groups.items()):
                if identity in active_apps or len(resources) > 256:
                    continue
                finished = [datetime.fromisoformat(item['finished_at']) for item in resources]
                if any(stamp.tzinfo is None for stamp in finished):
                    raise ValueError('Provider completion timestamp must be timezone-aware')
                end = hour(max(finished)) + timedelta(hours=1)
                if end > hour(now):
                    continue
                start = hour(datetime.fromtimestamp(
                    min(starts[item['reservation_id']] for item in resources), timezone.utc))
                return {'scope': {'workspace': identity[0], 'environment': identity[1],
                                  'object_ids': [identity[2]], 'start': start.isoformat(),
                                  'end': end.isoformat()},
                        'resources': sorted(resources, key=lambda item: item['reservation_id'])}
        return None


class CampaignOperator:
    def __init__(self, runner):
        self.runner = runner
        self.coordinator = runner.coordinator
        self.controller = runner.controller

    def billing_waits(self):
        with self.controller.ledger.transaction() as connection:
            return [row['id'] for row in connection.execute(
                "SELECT id FROM reservations WHERE state='held' AND expires_at<=? ORDER BY id",
                (int(time.time()) + 30,))]

    async def cycle(self):
        state = self.controller.snapshot()
        if time.time() >= state['controller']['deadline'] and not state['controller']['stopped']:
            self.controller.stop('Campaign deadline reached')
        if self.runner.admission_blocked():
            result = await self.runner.run_once()
            return {'status': 'stopped', 'result': result}
        waits = self.billing_waits()
        if waits:
            transitions = self.coordinator.advance()
            cleanup = await self.runner.terminate_due_serving()
            billing = await self.runner.billing.run_once() if self.runner.billing is not None else None
            return {'status': 'waiting-billing' if self.billing_waits() else 'progress',
                    'reservations': self.billing_waits(), 'transitions': transitions,
                    'cleanup': cleanup, 'billing': billing}
        for action in self.coordinator.required_actions():
            if action['action'] == 'register-training-dataset':
                workflow = self.coordinator.workflow(action['workflow'])
                result = self.coordinator.prepare_training_dataset(workflow['action_id'])
                return {'status': 'progress', 'dataset': result}
        replacement = await replace_expired_serving(self.runner)
        if replacement is not None:
            return {'status': 'progress', 'replacement': replacement}
        result = await self.runner.run_once(2)
        if any(result[key] for key in ('dispatch', 'cleanup', 'transitions', 'admitted', 'research', 'billing')):
            return {'status': 'progress', 'result': result}
        proposal = self.coordinator.supervisor.next()
        if proposal is not None:
            action = 'action-' + digest(canonical(proposal['id']))[:24]
            self.coordinator.start_next(action)
            return {'status': 'progress', 'proposal': proposal['id']}
        if self.runner.research is not None:
            generated = await self.runner.research.propose()
            if generated is not None:
                return {'status': 'progress', 'research': generated}
        required = self.coordinator.required_actions()
        return {'status': 'needs-operator' if required else 'idle', 'required_actions': required}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('database', 'contract', 'baseline', 'baseline-policy', 'state-root',
                 'policy', 'catalog', 'private-splits', 'telemetry'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--contract-sha256', required=True)
    parser.add_argument('--campaign', required=True)
    parser.add_argument('--pool', default='gameworld-autoresearch')
    parser.add_argument('--sft-source-catalog', type=Path)
    for name in sorted(MODAL_FIELDS):
        parser.add_argument('--' + name.replace('_', '-'), required=True)
    args = parser.parse_args()
    coordinator = CapacityCoordinator(
        args.database, args.contract, args.contract_sha256, args.baseline, args.state_root,
        args.policy, args.catalog, args.telemetry, args.pool, private_splits=args.private_splits)
    coordinator.initialize(args.campaign, args.baseline_policy)
    research = GameWorldResearchWorker(
        coordinator, args.state_root / 'research', sft_source_catalog=args.sft_source_catalog)
    billing = AppScopedReconciler(coordinator.controller, args.state_root / 'billing')
    runner = GameWorldProviderRunner(
        coordinator, {name: getattr(args, name) for name in MODAL_FIELDS},
        {'QWEN_API_KEY': os.environ.get('QWEN_API_KEY', '')},
        candidate_api_key=os.environ.get('QWEN_CANDIDATE_API_KEY'),
        research_worker=research, billing_reconciler=billing)
    operator = CampaignOperator(runner)

    async def run():
        for _ in range(10000):
            result = await operator.cycle()
            print(json.dumps({'at': datetime.now(timezone.utc).isoformat(), **result}), flush=True)
            if result['status'] in ('idle', 'stopped', 'needs-operator'):
                return
            if result['status'] == 'waiting-billing':
                await asyncio.sleep(60)
        raise RuntimeError('Operator cycle bound exhausted')

    with Path(str(args.database) + '.operator.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        asyncio.run(run())


if __name__ == '__main__':
    main()
