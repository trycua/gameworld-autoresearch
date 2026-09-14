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


def validate_plan_scopes(plan, app_scopes):
    if len({scope['app_id'] for scope in app_scopes}) != len(app_scopes):
        raise ValueError('Modal app scopes must be unique')
    expected_ids = sorted(scope['app_id'] for scope in app_scopes)
    if plan['scope']['object_ids'] != expected_ids:
        raise ValueError('Plan must cover exactly the verified dedicated apps')
    expected_context = {(scope['workspace'], scope['environment']) for scope in app_scopes}
    if (len(expected_context) != 1
            or (plan['scope']['workspace'], plan['scope']['environment']) not in expected_context):
        raise ValueError('Billing scope differs from app credentials')
    return expected_ids


def validate_image_import_completion(connection, reservation_id, finished_at):
    completed = [event['timestamp'] for event in connection.execute(
        "SELECT timestamp,payload FROM events WHERE kind='image_import_completed'")
        if json.loads(event['payload']).get('id') == reservation_id]
    if (len(completed) != 1
            or int(datetime.fromisoformat(finished_at).timestamp()) != completed[0]):
        raise ValueError('Image import completion timestamp differs from ledger custody')
    return completed[0]


async def run(args):
    import modal
    from modal.client import _Client
    from modal_proto import api_pb2

    ledger = CampaignLedger(args.database)
    if ledger.snapshot()['campaign']['id'] != args.campaign:
        raise ValueError('Canonical GameWorld ledger required')
    app_scopes = [json.loads(path.read_bytes()) for path in args.scope]
    for app_scope in app_scopes:
        validate_app_scope(
            await inspect_app_scope(app_scope['workspace'], app_scope['environment'], app_scope['app']),
            app_scope)
    plan = json.loads(args.plan.read_bytes())
    expected_ids = validate_plan_scopes(plan, app_scopes)
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
    running = []
    for app_id in expected_ids:
        running.extend([sandbox.object_id async for sandbox in modal.Sandbox.list.aio(app_id=app_id)])
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
                validate_image_import_completion(connection, item['reservation_id'], item['finished_at'])
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
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--campaign', required=True)
    parser.add_argument('--scope', type=Path, action='append', required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    asyncio.run(run(parser.parse_args()))
