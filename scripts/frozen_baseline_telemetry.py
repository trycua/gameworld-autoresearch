"""Export an anchored, replay-verified baseline report through the trusted outbox."""

import argparse
from datetime import datetime
import json
from pathlib import Path

from fps_bench.evaluation_contract import digest
from fps_bench.telemetry import ResearchTelemetry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--report-sha256', required=True)
    parser.add_argument('--outbox', required=True, type=Path)
    args = parser.parse_args()
    raw = args.report.read_bytes()
    if digest(raw) != args.report_sha256:
        raise ValueError('Report differs from trusted replay anchor')
    report = json.loads(raw)
    if report['contract_sha256'] != 'f2a1161156fa185ba9ad696b8bfc05369420cdde065ebd9fe7ae367faf38d5f9':
        raise ValueError('Wrong frozen contract')
    telemetry = ResearchTelemetry(args.outbox, 'gameworld-joint-20260913')
    for row in report['rows']:
        if (row['verification'] != 'frozen evaluator replay on trusted controller'
                or row['candidate'] != 'baseline' or row['split'] != 'development'):
            raise ValueError('Expected replay-verified development baseline')
        manifest_path = Path(report['run']) / row['episode_id'] / 'artifacts/manifest.json'
        manifest_raw = manifest_path.read_bytes()
        if digest(manifest_raw) != row['artifact_sha256']['manifest.json']:
            raise ValueError('Episode timestamp provenance mismatch')
        stamp = datetime.fromisoformat(json.loads(manifest_raw)['finished_at'])
        if stamp.tzinfo is None:
            raise ValueError('Timezone required')
        telemetry.record('baseline-' + row['episode_id'], 'gameworld-eval',
            {'experiment': 'baseline-' + row['episode_id'], 'phase': 'eval', 'split': 'development', 'objective': 'tile32'},
            {'gameworld_eval_success_rate': float(row['success']), 'gameworld_eval_completed_episodes': 1,
             'gameworld_eval_seconds': row['seconds']}, timestamp_ns=int(stamp.timestamp() * 1_000_000_000))
    print(json.dumps(telemetry.flush()))


if __name__ == '__main__':
    main()
