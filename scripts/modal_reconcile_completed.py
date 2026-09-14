"""Authenticate provider billing and terminate-state evidence before retaining allocations."""

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path

from fps_bench.campaign_ledger import CampaignLedger
from fps_bench.evaluation_contract import canonical, digest, exclusive_write
from fps_bench.modal_reconciliation import reconcile
from fps_bench.modal_scope import inspect_app_scope, validate_app_scope


async def run(args):
    import modal
    from modal.client import _Client
    from modal_proto import api_pb2

    ledger = CampaignLedger(args.database)
    if ledger.snapshot()['campaign']['id'] != 'gameworld-joint-20260913':
        raise ValueError('Canonical GameWorld ledger required')
    app_scope = json.loads(args.scope.read_bytes())
    validate_app_scope(await inspect_app_scope(app_scope['workspace'], app_scope['environment'], app_scope['app']), app_scope)
    plan = json.loads(args.plan.read_bytes())
    if plan['scope']['object_ids'] != [app_scope['app_id']]:
        raise ValueError('Plan must cover exactly this dedicated app')
    if plan['scope']['workspace'] != app_scope['workspace'] or plan['scope']['environment'] != app_scope['environment']:
        raise ValueError('Billing scope differs from app credentials')
    args.output.mkdir(parents=True, exist_ok=False)
    exclusive_write(args.output / 'plan.json', canonical(plan))
    workspace = await modal.Workspace.from_context().hydrate.aio()
    report = await workspace.billing.report.aio(start=datetime.fromisoformat(plan['scope']['start']),
        end=datetime.fromisoformat(plan['scope']['end']), resolution='h')
    rows = [{'object_id': row.object_id, 'environment': row.environment_name, 'interval_start': row.interval_start.isoformat(),
             'cost': str(row.cost), 'cost_by_resource': {key: str(value) for key, value in row.cost_by_resource.items()}}
            for row in report if row.object_id in plan['scope']['object_ids']]
    provider = {'scope': plan['scope'], 'method': 'Workspace.billing.report', 'rows': rows,
                'retrieved_at': datetime.now(timezone.utc).isoformat()}
    exclusive_write(args.output / 'provider-report.json', canonical(provider))
    running = [sandbox.object_id async for sandbox in modal.Sandbox.list.aio(app_id=app_scope['app_id'])]
    if running:
        raise RuntimeError('Dedicated app still has running sandboxes')
    resources = []
    for resource in plan['resources']:
        item = dict(resource)
        if item['kind'] == 'sandbox':
            sandbox = await modal.Sandbox.from_id.aio(item['provider_id'])
            item['returncode'] = await sandbox.poll.aio()
            item['observed_tags'] = await sandbox.get_tags.aio()
            if type(item['returncode']) is not int or item['observed_tags'] != item['expected_tags']:
                raise ValueError('Sandbox is running or differs from the retained dispatch identity')
        else:
            with ledger.transaction() as connection:
                imported = connection.execute('SELECT state,image_id FROM training_image_imports WHERE id=?',
                                              (item['reservation_id'],)).fetchone()
                if imported is None or imported['state'] != 'complete' or imported['image_id'] != item['provider_id']:
                    raise ValueError('Image import is unresolved')
            client = await _Client.from_env()
            await asyncio.wait_for(client.stub.ImageFromId(api_pb2.ImageFromIdRequest(image_id=item['provider_id'])), 30)
            item['state'] = 'complete'
            item['image_lookup_verified'] = True
        resources.append(item)
    closure = {'scope': plan['scope'], 'resources': resources, 'running_sandbox_ids': running,
               'checked_at': datetime.now(timezone.utc).isoformat(), 'provider_report_sha256': digest(canonical(provider))}
    exclusive_write(args.output / 'closure.json', canonical(closure))
    specification = {'scope': plan['scope'], 'reservation_ids': sorted(item['reservation_id'] for item in resources),
                     'policy': 'retain-full-allocation-no-refund-v1'}
    result = reconcile(ledger, specification, rows, closure)
    exclusive_write(args.output / 'reconciliation.json', canonical(result))
    print(json.dumps({key: value for key, value in result.items() if key != 'snapshot'}))
    print(json.dumps({'committed_micro_usd': result['snapshot']['resources']['modal_micro_usd']['committed'],
                      'expired_held': result['snapshot']['expired_held']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('database', 'scope', 'plan', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    asyncio.run(run(parser.parse_args()))
