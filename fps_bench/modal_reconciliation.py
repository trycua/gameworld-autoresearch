"""Conservative app-hour reconciliation: close work without refunding its allocation."""

from datetime import datetime, timezone
import json
import re

from fps_bench.campaign_ledger import LedgerConflict
from fps_bench.evaluation_contract import canonical, digest
from fps_bench.modal_billing import normalize_report, utc_hour


def overlap(left, right):
    return (left['workspace'] == right['workspace'] and left['environment'] == right['environment']
            and bool(set(left['object_ids']) & set(right['object_ids']))
            and utc_hour(left['start']) < utc_hour(right['end'])
            and utc_hour(right['start']) < utc_hour(left['end']))


def schema(connection):
    connection.execute('CREATE TABLE IF NOT EXISTS modal_reconciliation_groups ('
                       'id TEXT PRIMARY KEY, specification TEXT NOT NULL, floor INTEGER NOT NULL, '
                       'observed INTEGER NOT NULL DEFAULT 0, excess INTEGER NOT NULL DEFAULT 0)')
    connection.execute('CREATE TABLE IF NOT EXISTS modal_reconciliation_members ('
                       'reservation_id TEXT PRIMARY KEY REFERENCES reservations(id), '
                       'group_id TEXT NOT NULL REFERENCES modal_reconciliation_groups(id))')
    connection.execute('CREATE TABLE IF NOT EXISTS modal_reconciliation_rows ('
                       'id TEXT PRIMARY KEY, group_id TEXT NOT NULL REFERENCES modal_reconciliation_groups(id), '
                       'maximum INTEGER NOT NULL, latest INTEGER NOT NULL, receipt TEXT NOT NULL)')
    connection.execute('CREATE TABLE IF NOT EXISTS modal_reconciliation_observations ('
                       'receipt TEXT PRIMARY KEY, group_id TEXT NOT NULL, evidence TEXT NOT NULL)')


def reconcile(ledger, specification, rows, closure):
    required = {'scope', 'reservation_ids', 'policy'}
    if set(specification) != required or specification['policy'] != 'retain-full-allocation-no-refund-v1':
        raise ValueError('Explicit conservative reconciliation policy required')
    scope, identifiers = specification['scope'], specification['reservation_ids']
    normalized = normalize_report(rows, scope)
    if (not isinstance(identifiers, list) or not identifiers or identifiers != sorted(set(identifiers))
            or len(identifiers) > 256 or any(not isinstance(item, str) or not item for item in identifiers)):
        raise ValueError('Sorted unique reservation IDs required')
    checked = datetime.fromisoformat(closure['checked_at'])
    now = datetime.now(timezone.utc)
    if checked.tzinfo is None or not 0 <= (now - checked).total_seconds() <= 300:
        raise ValueError('Fresh provider closure checks required')
    if closure['scope'] != scope or closure['running_sandbox_ids'] != []:
        raise ValueError('Wrong scope or still-running sandboxes')
    closed = closure['resources']
    if len(closed) != len(identifiers) or sorted(item['reservation_id'] for item in closed) != identifiers:
        raise ValueError('Exactly one closure per reservation required')
    providers = [item['provider_id'] for item in closed]
    if len(set(providers)) != len(providers):
        raise ValueError('One resource cannot close multiple reservations')
    for item in closed:
        if item['app_id'] not in scope['object_ids']:
            raise ValueError('Resource belongs to another app')
        finished = datetime.fromisoformat(item['finished_at'])
        if finished.tzinfo is None or not utc_hour(scope['start']) <= finished < utc_hour(scope['end']):
            raise ValueError('Resource completion outside completed billing scope')
        if item['kind'] == 'sandbox':
            if (not item['provider_id'].startswith('sb-') or type(item['returncode']) is not int
                    or item['observed_tags'] != item['expected_tags']):
                raise ValueError('Sandbox termination/identity not verified')
        elif item['kind'] == 'image_import':
            if not item['provider_id'].startswith('im-') or item['state'] != 'complete':
                raise ValueError('Image import not complete')
        elif item['kind'] == 'deployed_app':
            if (item['provider_id'] != item['app_id'] or not item['provider_id'].startswith('ap-')
                    or item.get('state') != 'stopped' or item.get('running_tasks') != 0
                    or item.get('observed_app_id') != item['provider_id']
                    or item.get('observed_deployment_name') != item.get('deployment_name')
                    or not isinstance(item.get('deployment_name'), str)
                    or not item['deployment_name'].startswith('gameworld-')
                    or not isinstance(item.get('function_id'), str)
                    or not item['function_id'].startswith('fu-')
                    or not isinstance(item.get('function_tag'), str) or not item['function_tag']
                    or not isinstance(item.get('image_ids'), list) or not item['image_ids']
                    or item['image_ids'] != sorted(set(item['image_ids']))
                    or any(not isinstance(image, str) or not image.startswith('im-') for image in item['image_ids'])
                    or not re.fullmatch(r'[0-9a-f]{64}', item.get('deployment_manifest_sha256', ''))):
                raise ValueError('Deployed app closure is incomplete or differs from launch identity')
        else:
            raise ValueError('Unknown resource closure type')
    encoded = canonical(specification).decode()
    group_id = 'modal-retained:' + digest(canonical(specification))
    evidence = {'specification': specification, 'rows': normalized, 'closure': closure}
    receipt = 'modal-reconciliation:' + digest(canonical(evidence))
    with ledger.transaction() as connection:
        schema(connection)
        existing = connection.execute('SELECT * FROM modal_reconciliation_groups WHERE id=?', (group_id,)).fetchone()
        if existing is None:
            if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='modal_prior_scope'").fetchone():
                prior = connection.execute('SELECT specification FROM modal_prior_scope').fetchone()
                if prior and overlap(scope, json.loads(prior['specification'])):
                    raise LedgerConflict('Billing scope overlaps historical imports')
            for group in connection.execute('SELECT specification FROM modal_reconciliation_groups'):
                if overlap(scope, json.loads(group['specification'])['scope']):
                    raise LedgerConflict('Billing scopes overlap; revise the original group instead')
            reservations = []
            events = {json.loads(event['payload'])['id']: event['timestamp'] for event in connection.execute(
                "SELECT timestamp,payload FROM events WHERE kind='reserved'")}
            for item in closed:
                row = connection.execute('SELECT * FROM reservations WHERE id=?', (item['reservation_id'],)).fetchone()
                if row is None or row['state'] != 'held' or row['resource'] != 'modal_micro_usd' or row['purpose'] != 'normal':
                    raise LedgerConflict('Expected an existing normal Modal hold')
                reserved = events.get(row['id'])
                finished = datetime.fromisoformat(item['finished_at']).timestamp()
                if reserved is None or not utc_hour(scope['start']).timestamp() <= reserved <= finished:
                    raise LedgerConflict('Reservation start outside billing coverage')
                if item['kind'] == 'image_import':
                    imported = connection.execute('SELECT state,image_id FROM training_image_imports WHERE id=?', (row['id'],)).fetchone()
                    if imported is None or imported['state'] != 'complete' or imported['image_id'] != item['provider_id']:
                        raise LedgerConflict('Durable image import does not match closure')
                if connection.execute('SELECT 1 FROM modal_reconciliation_members WHERE reservation_id=?', (row['id'],)).fetchone():
                    raise LedgerConflict('Reservation already belongs to another reconciliation')
                reservations.append(row)
            floor = sum(row['amount'] for row in reservations)
            connection.execute('INSERT INTO modal_reconciliation_groups(id,specification,floor) VALUES (?,?,?)',
                               (group_id, encoded, floor))
            for row in reservations:
                connection.execute('INSERT INTO modal_reconciliation_members VALUES (?,?)', (row['id'], group_id))
                connection.execute("UPDATE reservations SET state='reconciled_retained',receipt=? WHERE id=?",
                                   (group_id + ':' + row['id'], row['id']))
        else:
            if existing['specification'] != encoded:
                raise LedgerConflict('Group identity changed')
            first = connection.execute('SELECT evidence FROM modal_reconciliation_observations WHERE group_id=? ORDER BY rowid LIMIT 1',
                                       (group_id,)).fetchone()
            if first is None:
                raise LedgerConflict('Missing original closure evidence')
            def bindings(items):
                return sorted([canonical({key: item.get(key) for key in
                    ('reservation_id', 'kind', 'provider_id', 'app_id', 'finished_at', 'expected_tags',
                     'deployment_name', 'function_id', 'function_tag', 'image_ids',
                     'deployment_manifest_sha256')}).decode()
                    for item in items])
            if bindings(json.loads(first['evidence'])['closure']['resources']) != bindings(closed):
                raise LedgerConflict('Closed provider resource identities cannot change')
        for row in normalized:
            if connection.execute('SELECT 1 FROM prior_usage WHERE id=?', (row['id'],)).fetchone():
                raise LedgerConflict('Provider row already counted as prior usage')
            old = connection.execute('SELECT * FROM modal_reconciliation_rows WHERE id=?', (row['id'],)).fetchone()
            if old and old['group_id'] != group_id:
                raise LedgerConflict('Provider row already belongs to another group')
            maximum = max(row['micro_usd'], old['maximum'] if old else 0)
            connection.execute('INSERT INTO modal_reconciliation_rows VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET '
                               'maximum=excluded.maximum,latest=excluded.latest,receipt=excluded.receipt',
                               (row['id'], group_id, maximum, row['micro_usd'], row['receipt']))
        observed = connection.execute('SELECT COALESCE(SUM(maximum),0) FROM modal_reconciliation_rows WHERE group_id=?',
                                      (group_id,)).fetchone()[0]
        group = connection.execute('SELECT * FROM modal_reconciliation_groups WHERE id=?', (group_id,)).fetchone()
        excess = max(0, observed - group['floor'])
        connection.execute('UPDATE modal_reconciliation_groups SET observed=?,excess=? WHERE id=?', (observed, excess, group_id))
        if excess:
            connection.execute('UPDATE campaign SET frozen=1,reason=?', ('Provider charges exceed retained allocation ' + group_id,))
        if not connection.execute('SELECT 1 FROM modal_reconciliation_observations WHERE receipt=?', (receipt,)).fetchone():
            connection.execute('INSERT INTO modal_reconciliation_observations VALUES (?,?,?)', (receipt, group_id, canonical(evidence).decode()))
            ledger._event(connection, 'modal_reconciled_retained', {'group_id': group_id, 'receipt': receipt,
                'retained_micro_usd': group['floor'], 'observed_micro_usd': observed, 'excess_micro_usd': excess,
                'refund_micro_usd': 0, 'provider_finality_claimed': False})
        result = {'group_id': group_id, 'receipt': receipt, 'retained_micro_usd': group['floor'],
                  'observed_micro_usd': observed, 'excess_micro_usd': excess, 'refund_micro_usd': 0,
                  'provider_finality_claimed': False, 'closed_reservations': identifiers}
    return {**result, 'snapshot': ledger.snapshot()}
