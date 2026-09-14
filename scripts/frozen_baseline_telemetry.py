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
    baseline = report['baseline']
    if baseline['status'] != 'complete':
        print(json.dumps({'status': 'incomplete_report', 'exported': False}))
        return
    if len(report['rows']) != 16 or baseline['episodes'] != 16:
        raise ValueError('Complete frozen baseline requires all 16 episodes')
    timestamps = []
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
        timestamps.append(int(stamp.timestamp() * 1_000_000_000))
    telemetry = ResearchTelemetry(args.outbox, 'gameworld-joint-20260913')
    telemetry.record('baseline-qwen-v1-complete', 'gameworld-eval',
        {'experiment': 'baseline-qwen-v1', 'phase': 'eval', 'split': 'development', 'objective': 'tile32'},
        {'gameworld_eval_success_rate': baseline['success_rate'], 'gameworld_eval_completed_episodes': 16,
         'gameworld_eval_failed_episodes': 0,
         'gameworld_eval_mean_progress': sum(row['evaluation']['metrics']['progress_current'] for row in report['rows']) / 16,
         'gameworld_eval_seconds': baseline['median_seconds']}, timestamp_ns=max(timestamps))
    print(json.dumps(telemetry.flush()))


if __name__ == '__main__':
    main()
