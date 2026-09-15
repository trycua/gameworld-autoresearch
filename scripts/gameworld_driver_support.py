"""Authenticated driver test support and bounded, hash-verified binary transport."""

import argparse
import hashlib
import json
from pathlib import Path
import shlex

from fps_bench.gameworld_fleet import FleetSandboxBackend


UPSTREAM = 'dbf0d3a450d9c4fc3a0a768faf0ce9b3283f908e'
TEST_SOURCE = 'cua-driver/rust/crates/cua-driver/tests/compatibility_contract_test.rs'
TEST_SHA256 = '9bff988f4730b4d0a9ad34a193b8dce4010507dfd46c1cdeb7fd1826cdd10929'
HELPER = 'scripts/gameworld_driver_contract.py'
OLD_HELPER = '40d5c05f1cc955bfde6d87fe1189c5526c35524bc229914e0158784f38c047de'
FILES = {
    'cua-driver/compat-fixtures/cli.json': '00d16fae4f44ebdbe1331b7b572764c069f0373090ab110b80536a690b52e194',
    'cua-driver/compat-fixtures/mcp.json': '5579eb51178f08c69fbb6b28a63a59f253a600858505ea80f5df94c105c387cb',
    HELPER: 'cca3c464c660aa7f9f95baf164dc5aaca47d285906550bdebe277fae25c65697',
}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def regular(root, name, missing=False):
    root = Path(root).resolve()
    path = root / name
    if any(part.is_symlink() for part in (path, *path.parents) if part != root.parent):
        raise ValueError('Driver support paths cannot contain symlinks')
    if not path.is_file() and not (missing and not path.exists()):
        raise ValueError('Driver support requires regular files')
    return path


def bundle(root):
    values = {}
    for index, (name, expected) in enumerate(FILES.items()):
        data = regular(root, name).read_bytes()
        if sha256(data) != expected:
            raise ValueError('Local driver support differs from its reviewed hash')
        values[f'driver-support-{index}'] = data
    values['driver-support-installer.py'] = Path(__file__).read_bytes()
    return values


def install(root, inputs):
    root, inputs = Path(root), Path(inputs)
    if regular(root, 'cua-driver/UPSTREAM_REF').read_text().strip() != UPSTREAM:
        raise ValueError('Driver upstream revision differs')
    if sha256(regular(root, TEST_SOURCE).read_bytes()) != TEST_SHA256:
        raise ValueError('Driver compatibility test changed')
    planned = []
    for index, (name, expected) in enumerate(FILES.items()):
        data = regular(inputs, f'driver-support-{index}').read_bytes()
        if sha256(data) != expected:
            raise ValueError('Staged support input differs from its reviewed hash')
        path = regular(root, name, missing=name != HELPER)
        before = sha256(path.read_bytes()) if path.exists() else None
        accepted = (OLD_HELPER, expected) if name == HELPER else (None, expected)
        if before not in accepted:
            raise ValueError('Existing driver support differs from the reviewed original')
        planned.append((path, data, {'path': name, 'before': before, 'after': expected}))
    receipt = {'schema_version': 1, 'scope': 'driver-build-test-support-only',
               'upstream': UPSTREAM, 'compatibility_test_sha256': TEST_SHA256,
               'files': [item for _, _, item in planned]}
    target = inputs / 'driver-support-receipt.json'
    previous = None
    if target.exists():
        previous = json.loads(regular(inputs, target.name).read_bytes())
        if (previous.get('scope') != receipt['scope'] or previous.get('upstream') != UPSTREAM
                or previous.get('compatibility_test_sha256') != TEST_SHA256
                or {item['path']: item['after'] for item in previous['files']} != FILES):
            raise ValueError('Driver support receipt changed')
    for path, data, item in planned:
        if item['before'] != item['after']:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    if previous is not None:
        return previous
    with target.open('x') as handle:
        handle.write(json.dumps(receipt, sort_keys=True) + '\n')
    return receipt


class DriverSupportBackend(FleetSandboxBackend):
    def __init__(self, controller=None):
        self.controller = controller
        self.support_roots = set()
        self.transfer_roots = set()

    async def stage(self, sandbox, remote_root, files):
        driver = files.get('cua-driver', b'')
        if len(driver) > 16 * 1024 * 1024:
            identity = files.get('candidate.json', files.get('config.json'))
            if len(driver) > 64 * 1024 * 1024 or identity is None:
                raise ValueError('Oversized driver requires a bounded candidate or rollout identity')
            expected = json.loads(identity).get('driver_sha256')
            if sha256(driver) != expected or any(name.startswith('driver-transfer-') for name in files):
                raise ValueError('Driver transfer identity or staging names differ')
            chunks = {f'driver-transfer-{index:03d}': driver[offset:offset + 4 * 1024 * 1024]
                      for index, offset in enumerate(range(0, len(driver), 4 * 1024 * 1024))}
            await super().stage(sandbox, remote_root, {**{name: data for name, data in files.items()
                                                        if name != 'cua-driver'}, **chunks})
            program = ('import hashlib,json,os; from pathlib import Path; '
                       f'root=Path({remote_root!r}); names={list(chunks)!r}; '
                       'target=root/"driver-transfer-assembled"; '
                       'target.write_bytes(b"".join((root/name).read_bytes() for name in names)); '
                       f'assert target.stat().st_size=={len(driver)}; '
                       f'assert hashlib.sha256(target.read_bytes()).hexdigest()=={expected!r}; '
                       'os.replace(target,root/"cua-driver"); '
                       f'(root/"driver-transfer.json").write_text(json.dumps({{"sha256":{expected!r},'
                       f'"bytes":{len(driver)},"chunks":{len(chunks)}}})); '
                       '[(root/name).unlink() for name in names]')
            result = await sandbox.shell.run('python3 -c ' + shlex.quote(program), timeout=60)
            if not result.success:
                raise RuntimeError('Chunked driver assembly failed integrity verification')
            self.transfer_roots.add(remote_root)
            return
        if set(files) != {'proposal.json', 'candidate.patch'}:
            return await super().stage(sandbox, remote_root, files)
        await super().stage(sandbox, remote_root, {**files, **bundle(Path(__file__).resolve().parents[1])})
        command = ('/opt/gameworld-venv/bin/python ' + shlex.quote(remote_root + '/driver-support-installer.py')
                   + ' --root /opt/gameworld-autoresearch --inputs ' + shlex.quote(remote_root))
        result = await sandbox.shell.run(command, timeout=30)
        if not result.success:
            raise RuntimeError('Authenticated driver support installation failed: ' + result.stderr[-1000:])
        self.support_roots.add(remote_root)

    async def collect(self, sandbox, remote_root, output, maximum):
        if remote_root in self.transfer_roots:
            result = await sandbox.shell.run(
                f'cp {shlex.quote(remote_root + "/driver-transfer.json")} '
                f'{shlex.quote(remote_root + "/output/transport/driver-transfer.json")}', timeout=15)
            if not result.success:
                raise RuntimeError('Driver transfer receipt could not be preserved')
        needs_support = remote_root in self.support_roots
        if self.controller is not None:
            with self.controller.ledger.transaction() as connection:
                needs_support = self.controller._job(connection, Path(output).name)['kind'] == 'driver_build'
        if not needs_support:
            return await super().collect(sandbox, remote_root, output, maximum)
        source = shlex.quote(remote_root + '/driver-support-receipt.json')
        target = shlex.quote(remote_root + '/output/driver-support.json')
        result = await sandbox.shell.run(f'if test -f {source}; then cp {source} {target}; fi', timeout=15)
        if not result.success:
            raise RuntimeError('Driver support receipt could not be preserved')
        return await super().collect(sandbox, remote_root, output, maximum)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--inputs', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(install(args.root, args.inputs), sort_keys=True))
