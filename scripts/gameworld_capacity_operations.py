"""Audited operational overrides; frozen evaluation and candidate inputs stay intact."""

import json
import time

from fps_bench.campaign_ledger import LedgerConflict
from fps_bench.evaluation_contract import canonical, digest
from fps_bench.gameworld_coordinator import GameWorldCoordinator
from fps_bench.gameworld_grpo import policy_digest
from fps_bench.gameworld_serving import GameWorldServingLifecycle, compute_reservation


def extend_deadline(controller, authorization, total_seconds=43200):
    if not authorization.strip() or type(total_seconds) is not int or not 21600 < total_seconds <= 64800:
        raise ValueError('An explicit authorization and at most eighteen total hours are required')
    with controller.ledger.transaction() as connection:
        current = dict(controller._controller(connection, admission=True))
        deadline = current['created'] + total_seconds
        connection.execute('CREATE TABLE IF NOT EXISTS gameworld_operational_extensions '
                           '(deadline INTEGER PRIMARY KEY, receipt TEXT NOT NULL)')
        previous = connection.execute('SELECT receipt FROM gameworld_operational_extensions WHERE deadline=?',
                                      (deadline,)).fetchone()
        if previous:
            return json.loads(previous['receipt'])
        if deadline <= current['deadline']:
            raise LedgerConflict('Extension must increase the effective deadline')
        if connection.execute("SELECT 1 FROM private_split_leases WHERE state IN ('issued','active')").fetchone():
            raise LedgerConflict('Cannot extend while private evaluation is active')
        supervisor = dict(connection.execute('SELECT * FROM gameworld_research').fetchone())
        if supervisor['state'] != 'running' or not time.time() < supervisor['deadline'] < deadline:
            raise LedgerConflict('Supervisor is stopped, expired, or already exceeds requested deadline')
        receipt = {'authorization': authorization, 'recorded_at': int(time.time()),
                   'original_created': current['created'], 'original_duration': current['duration'],
                   'previous_deadline': current['deadline'], 'deadline': deadline,
                   'previous_supervisor_deadline': supervisor['deadline'],
                   'contract_hash': current['contract_hash'], 'scope': 'operational-wall-clock-only'}
        connection.execute('INSERT INTO gameworld_operational_extensions VALUES (?,?)',
                           (deadline, canonical(receipt).decode()))
        connection.execute('UPDATE controller SET deadline=?', (deadline,))
        connection.execute('UPDATE gameworld_research SET deadline=?', (deadline,))
        connection.execute("UPDATE gameworld_actions SET deadline=? WHERE state IN ('dispatching','running')",
                           (deadline,))
        controller.ledger._event(connection, 'operational_deadline_extended', receipt)
        return receipt


class CapacityCoordinator(GameWorldCoordinator):
    def _items(self, workflow, phase=None):
        rows = super()._items(workflow, phase)
        details = self.workflow(workflow)['details']
        pointers = {'serving': details.get('serving_job'),
                    details.get('source_serving_phase'): details.get('source_serving_job')}
        for row in rows:
            current = pointers.get(row['phase'])
            if current is None or row['job_id'] == current:
                continue
            with self.controller.ledger.transaction() as connection:
                job = dict(self.controller._job(connection, current))
            result = None if job['result'] is None else json.loads(job['result'])['result']
            if job['state'] in ('cleaned', 'billing_pending'):
                state = 'complete' if result and result.get('status') == 'complete' else 'failed'
            else:
                state = 'live' if result else 'admitted'
            row.update(job_id=current, state=state)
        return rows


class ReplacementController:
    def __init__(self, controller, job_id):
        self.controller = controller
        self.job_id = job_id

    def __getattr__(self, name):
        return getattr(self.controller, name)

    def register_candidate(self, candidate):
        with self.ledger.transaction() as connection:
            existing = json.loads(self._candidate(connection, candidate['id'])['manifest'])
            if ({key: value for key, value in existing.items() if key != 'deployment'} !=
                    {key: value for key, value in candidate.items() if key != 'deployment'}):
                raise LedgerConflict('Replacement changed immutable candidate identity')
            if any(existing['deployment'][key] != candidate['deployment'][key]
                   for key in ('app_id', 'image_id')):
                raise LedgerConflict('Replacement changed pinned serving app or image')
            job = self._job(connection, self.job_id)
            result = json.loads(job['result'])['result']
            if (job['kind'] != 'serving' or result['candidate_id'] != candidate['id']
                    or result['deployment'] != candidate['deployment']
                    or result['policy_sha256'] != candidate['policy_sha256']):
                raise LedgerConflict('Replacement lacks matching authenticated serving result')
            self.ledger._event(connection, 'serving_generation_candidate_verified', {
                'job_id': self.job_id, 'candidate_id': candidate['id'],
                'policy_sha256': candidate['policy_sha256'], 'deployment': candidate['deployment']})
        return existing


async def pause_expiring_serving(runner):
    controller, coordinator = runner.controller, runner.coordinator
    with controller.ledger.transaction() as connection:
        if not connection.execute("SELECT 1 FROM sqlite_master WHERE name='gameworld_operational_extensions'").fetchone():
            return None
        if not connection.execute('SELECT 1 FROM gameworld_operational_extensions').fetchone():
            return None
        if connection.execute("SELECT 1 FROM jobs WHERE kind IN ('evaluation','rollout') "
                              "AND state IN ('reserved','dispatching','running','cleanup_pending')").fetchone():
            return None
        workflows = [coordinator._workflow(connection, row[0]) for row in connection.execute(
            "SELECT proposal_id FROM gameworld_workflows WHERE state='evaluating' AND track IN ('model','driver')")]
        due = []
        for workflow in workflows:
            details = workflow['details']
            job = controller._job(connection, details.get('serving_job') or details['source_serving_job'])
            timeout = connection.execute(
                "SELECT MAX(timeout_seconds) FROM gameworld_work_items WHERE workflow=? "
                "AND kind='evaluation' AND state='pending'", (workflow['proposal_id'],)).fetchone()[0]
            if (timeout is not None and job['state'] == 'cleanup_pending' and job['result'] is not None
                    and time.time() + timeout + 60 >= job['deadline']):
                due.append({'workflow': workflow['proposal_id'], 'job_id': job['id'],
                            'serving_deadline': job['deadline'], 'next_episode_timeout': timeout,
                            'reason': 'replace-between-episodes-before-serving-expiry'})
    for receipt in due:
        await runner.cleanup_serving_job(receipt['job_id'])
        with controller.ledger.transaction() as connection:
            controller.ledger._event(connection, 'serving_capacity_paused', receipt)
        return receipt
    return None


async def replace_expired_serving(runner):
    coordinator, controller = runner.coordinator, runner.controller
    with controller.ledger.transaction() as connection:
        authorized = connection.execute("SELECT 1 FROM sqlite_master WHERE name='gameworld_operational_extensions'").fetchone()
        if not authorized:
            return None
        authorization = connection.execute('SELECT receipt FROM gameworld_operational_extensions ORDER BY deadline DESC LIMIT 1').fetchone()
        if not authorization:
            return None
        workflows = [coordinator._workflow(connection, row[0]) for row in connection.execute(
            "SELECT proposal_id FROM gameworld_workflows WHERE state='evaluating' AND track IN ('model','driver')")]
    for workflow in workflows:
        pointer = 'serving_job' if 'serving_job' in workflow['details'] else 'source_serving_job'
        old_id = workflow['details'][pointer]
        with controller.ledger.transaction() as connection:
            old = dict(controller._job(connection, old_id))
        if old['state'] not in ('cleaned', 'billing_pending'):
            continue
        if old['state'] != 'cleaned':
            raise LedgerConflict('Replacement requires reconciled previous capacity')
        new_id = 'gw-replace-' + digest(canonical(old_id))[:24]
        with controller.ledger.transaction() as connection:
            controller._controller(connection, admission=True)
            others = connection.execute("SELECT id FROM jobs WHERE state IN ('reserved','dispatching','running','cleanup_pending') AND id!=?", (new_id,)).fetchall()
            if others:
                raise LedgerConflict('Replacement is allowed only between episodes with no other active jobs')
            existing = connection.execute('SELECT * FROM jobs WHERE id=?', (new_id,)).fetchone()
        spec = json.loads(old['specification'])
        if existing is None:
            price = await runner.serving.backend.prices(runner.modal_config['workspace'])
            quote = compute_reservation(price['rates'], 10800, price['checked_at'])
            spec.update(timeout_seconds=10800, reservations={'modal_micro_usd': quote['required_reservation_micro_usd']})
            controller.admit_job(new_id, spec['candidate'], 'serving', spec['assignment'],
                                 spec['reservations'], spec['timeout_seconds'])
        else:
            resumed_spec = json.loads(existing['specification'])
            if (resumed_spec['candidate'] != spec['candidate']
                    or resumed_spec['assignment'] != spec['assignment']
                    or resumed_spec['kind'] != 'serving' or resumed_spec['timeout_seconds'] != 10800):
                raise LedgerConflict('Replacement admission identity changed')
            spec = resumed_spec
            if existing['state'] in ('cleaned', 'billing_pending'):
                raise LedgerConflict('Replacement attempt already ended; requires operator review')
        source = spec['assignment'].get('mode') == 'source'
        lifecycle = GameWorldServingLifecycle(controller if source else ReplacementController(controller, new_id),
                                             coordinator.state_root / 'serving', runner.serving.backend)
        config = runner.modal_config
        with controller.ledger.transaction() as connection:
            prepared = connection.execute('SELECT 1 FROM gameworld_serving_launches WHERE job_id=?', (new_id,)).fetchone()
        if not prepared:
            common = {'workspace': config['workspace'], 'app': config['serving_app'],
                      'environment': config['environment'], 'environment_id': config['environment_id'],
                      'image_id': config['serving_image_id'], 'app_id': config['serving_app_id'],
                      'isolation_policy': 'app-scoped'}
            if source:
                await lifecycle.prepare_source(new_id, runner.policy_seed(spec['candidate']),
                                               runner.parent_adapter(spec['candidate']), **common)
            else:
                await lifecycle.prepare(new_id, coordinator.state_root / 'modal' / spec['assignment']['training_job'],
                                        runner.parent_adapter(spec['candidate']), **common)
        result = await lifecycle.start(new_id, runner.candidate_api_key)
        with controller.ledger.transaction() as connection:
            current = coordinator._workflow(connection, workflow['proposal_id'])
            if current['details'][pointer] != old_id or current['state'] != 'evaluating':
                raise LedgerConflict('Workflow moved during capacity replacement')
            details = {**current['details'], pointer: new_id, 'policy_path': result['policy_path']}
            connection.execute('UPDATE gameworld_workflows SET details=? WHERE proposal_id=?',
                               (canonical(details).decode(), workflow['proposal_id']))
            receipt = {'workflow': workflow['proposal_id'], 'previous_job': old_id, 'job_id': new_id,
                       'policy_sha256': policy_digest(result['policy_identity']),
                       'authorization': json.loads(authorization['receipt'])['authorization']}
            controller.ledger._event(connection, 'serving_capacity_replaced', receipt)
        return receipt
    return None
