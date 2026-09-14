"""Retain a complete replay report and its verified artifacts outside candidate workspaces."""

import argparse
import json
from pathlib import Path

from fps_bench.evaluation_contract import canonical, digest, exclusive_write, safe_file


def register(report_path, expected_hash, destination):
    data = report_path.read_bytes()
    if digest(data) != expected_hash:
        raise ValueError('Baseline report anchor mismatch')
    report = json.loads(data)
    if (report['contract_sha256'] != 'f2a1161156fa185ba9ad696b8bfc05369420cdde065ebd9fe7ae367faf38d5f9'
            or report['baseline']['status'] != 'complete' or len(report['rows']) != 16):
        raise ValueError('Only complete frozen baseline reports can be registered')
    destination = destination.resolve()
    workspace = Path(__file__).resolve().parents[1]
    if destination.is_relative_to(workspace):
        raise ValueError('Baseline custody must be outside the candidate workspace')
    destination.mkdir(parents=True, exist_ok=False, mode=0o700)
    inventory = {}
    for row in report['rows']:
        if row['verification'] != 'frozen evaluator replay on trusted controller':
            raise ValueError('Unverified episode')
        episode = row['episode_id']
        for name, expected in row['artifact_sha256'].items():
            source = safe_file(Path(report['run']), episode + '/artifacts/' + name)
            content = source.read_bytes()
            if digest(content) != expected:
                raise ValueError('Baseline artifact changed before registration')
            relative = episode + '/artifacts/' + name
            exclusive_write(safe_file(destination, relative), content, 0o400)
            inventory[relative] = expected
    exclusive_write(destination / 'report.json', data, 0o400)
    registration = {'schema_version': 1, 'report_sha256': expected_hash,
                    'contract_sha256': report['contract_sha256'], 'files': inventory,
                    'source_run': report['run'], 'custody_root': str(destination),
                    'boundary': 'Outside repository and read-only files; same-user access is not OS isolation'}
    exclusive_write(destination / 'registration.json', canonical(registration), 0o400)
    return {'custody': str(destination), 'report_sha256': expected_hash,
            'registration_sha256': digest(canonical(registration)), 'artifact_count': len(inventory)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--report-sha256', required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(register(args.report, args.report_sha256, args.destination)))
