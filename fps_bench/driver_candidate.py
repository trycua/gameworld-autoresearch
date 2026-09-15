"""Validation and immutable artifacts for a GameWorld cua-driver candidate."""

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess
import time

from fps_bench.evaluation_contract import canonical, digest, exclusive_write


MAX_PATCH_BYTES = 1024 * 1024
PATCH_PATH = re.compile(r"^[A-Za-z0-9._/-]+$")
FORBIDDEN_HEADERS = (
    "GIT binary patch", "Binary files ", "new file mode ", "deleted file mode ",
    "rename from ", "rename to ", "copy from ", "copy to ", "old mode ", "new mode ",
)


def validate_patch(data, allowed_prefixes):
    if not isinstance(data, bytes) or not data or len(data) > MAX_PATCH_BYTES or b"\0" in data:
        raise ValueError("Driver patch must be nonempty text below 1 MiB")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Driver patch content must be valid UTF-8") from error
    prefixes = tuple(allowed_prefixes)
    if not prefixes:
        raise ValueError("Driver patch requires an allowlist")
    files = []
    current = None
    old_header = new_header = hunk = False
    for line in text.split("\n"):
        if len(line) > 20000:
            raise ValueError("Driver patch line exceeds the parser bound")
        if line.startswith(FORBIDDEN_HEADERS):
            raise ValueError("Driver patch may only modify existing text files")
        if line.startswith("diff --git "):
            if current is not None and not (old_header and new_header and hunk):
                raise ValueError("Driver patch file is missing canonical headers or hunks")
            parts = line.split(" ")
            if len(parts) != 4 or not parts[2].startswith("a/") or not parts[3].startswith("b/"):
                raise ValueError("Driver patch requires unquoted canonical paths")
            old, new = parts[2][2:], parts[3][2:]
            if old != new or not PATCH_PATH.fullmatch(old) or old.startswith("/") or ".." in Path(old).parts:
                raise ValueError("Driver patch path is invalid")
            if not old.startswith(prefixes):
                raise ValueError("Driver patch escaped the allowlisted source tree")
            if old in files:
                raise ValueError("Driver patch repeats a file")
            files.append(old)
            current, old_header, new_header, hunk = old, False, False, False
        elif line.startswith("--- "):
            if current is None or line != f"--- a/{current}":
                raise ValueError("Driver patch old path differs from its diff header")
            old_header = True
        elif line.startswith("+++ "):
            if current is None or line != f"+++ b/{current}":
                raise ValueError("Driver patch new path differs from its diff header")
            new_header = True
        elif line.startswith("@@ "):
            if current is None or not old_header or not new_header:
                raise ValueError("Driver patch hunk appears before file headers")
            hunk = True
        elif current is None and line.strip():
            raise ValueError("Driver patch must contain only a unified diff")
    if current is None or not (old_header and new_header and hunk):
        raise ValueError("Driver patch has no complete file hunks")
    return {"patch_sha256": digest(data), "paths": files, "bytes": len(data)}


def run_command(command, cwd, log, timeout):
    started = time.monotonic()
    with Path(log).open("wb") as handle:
        process = subprocess.run(command, cwd=cwd, stdout=handle, stderr=subprocess.STDOUT,
                                 timeout=timeout, check=False)
    result = {"command": command, "returncode": process.returncode,
              "seconds": time.monotonic() - started, "log": Path(log).name}
    if process.returncode != 0:
        tail = Path(log).read_bytes()[-4000:].decode(errors="replace")
        raise RuntimeError(f"Command failed ({process.returncode}): {' '.join(command)}\n{tail}")
    return result


def materialize_driver_candidate(proposal_path, proposal_sha256, patch_path, output, policy, root):
    proposal_path, patch_path, output, root = map(Path, (proposal_path, patch_path, output, root))
    proposal_bytes = proposal_path.read_bytes()
    proposal = json.loads(proposal_bytes)
    if canonical(proposal) != proposal_bytes or digest(proposal_bytes) != proposal_sha256:
        raise ValueError("Driver proposal bytes differ from the trusted supervisor identity")
    if proposal.get("track") != "driver" or proposal.get("experiment", {}).get("kind") != "driver":
        raise ValueError("Driver worker received a non-driver proposal")
    patch = patch_path.read_bytes()
    patch_manifest = validate_patch(patch, policy["driver"]["allowed_source_prefixes"])
    if set(patch_manifest["paths"]) != set(proposal["experiment"]["target_paths"]):
        raise ValueError("Materialized patch paths differ from the approved proposal")
    for name in patch_manifest["paths"]:
        source = root / name
        if not source.is_file() or source.is_symlink():
            raise ValueError("Driver patch may modify only existing regular source files")
    output.mkdir(parents=True, exist_ok=False)
    exclusive_write(output / "proposal.json", proposal_bytes, 0o400)
    exclusive_write(output / "candidate.patch", patch, 0o400)
    before = {name: digest((root / name).read_bytes()) for name in patch_manifest["paths"]}
    base_driver = digest(Path("/usr/local/bin/cua-driver").read_bytes())
    started = time.monotonic()
    tests = []
    try:
        tests.append(run_command(["git", "apply", "--check", str(output / "candidate.patch")], root,
                                 output / "patch-check.log", 60))
        tests.append(run_command(["git", "apply", str(output / "candidate.patch")], root,
                                 output / "patch-apply.log", 60))
        after = {name: digest((root / name).read_bytes()) for name in patch_manifest["paths"]}
        if any(before[name] == after[name] for name in before):
            raise ValueError("Every approved driver source file must change")
        tests.append(run_command(["bash", "image/rebuild_driver.sh"], root,
                                 output / "build.log", 900))
        driver_sha256 = digest(Path("/usr/local/bin/cua-driver").read_bytes())
        if driver_sha256 == base_driver:
            raise ValueError("Driver source patch did not change the installed binary")
        shutil.copyfile("/usr/local/bin/cua-driver", output / "cua-driver")
        (output / "cua-driver").chmod(0o500)
        rust = root / "cua-driver/rust"
        tests.append(run_command([
            "cargo", "test", "--offline", "--locked", "-p", "cua-driver-core",
            "--test", "contract_parity",
        ], rust, output / "contract-parity.log", 900))
        tests.append(run_command([
            "cargo", "test", "--offline", "--locked", "-p", "cua-driver",
            "--test", "compatibility_contract_test",
        ], rust, output / "compatibility-contract.log", 900))
        tests.append(run_command([
            "/opt/gameworld-venv/bin/python", "scripts/gameworld_driver_contract.py",
            "--output", str(output / "desktop-contract.json"),
        ], root, output / "desktop-contract.log", 180))
        desktop_contract = json.loads((output / "desktop-contract.json").read_bytes())
        if desktop_contract.get("status") != "passed" or set(desktop_contract.get("checks", {})) != {
                "focus", "held-keys", "key-release", "mouse-delivery"}:
            raise ValueError("Driver desktop contract did not report every required check")
        manifest = {
            "schema_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "proposal_id": proposal["id"],
            "proposal_sha256": proposal_sha256,
            "patch_sha256": patch_manifest["patch_sha256"],
            "paths": patch_manifest["paths"],
            "source_before": before,
            "source_after": after,
            "base_driver_sha256": base_driver,
            "driver_sha256": driver_sha256,
            "binary": {"path": "cua-driver", "sha256": driver_sha256},
            "tests": tests,
            "desktop_contract_sha256": digest((output / "desktop-contract.json").read_bytes()),
            "seconds": time.monotonic() - started,
        }
        manifest_bytes = canonical(manifest)
        exclusive_write(output / "driver-manifest.json", manifest_bytes, 0o400)
        result = {
            "status": "complete", "candidate_id": proposal["id"] + "-candidate",
            "proposal_sha256": proposal_sha256, "patch_sha256": patch_manifest["patch_sha256"],
            "driver_sha256": driver_sha256, "manifest_sha256": digest(manifest_bytes),
            "tests_passed": len(tests), "seconds": manifest["seconds"],
        }
        exclusive_write(output / "result.json", canonical(result), 0o400)
        return result
    except BaseException as error:
        exclusive_write(output / "error.json", canonical({
            "status": "failed", "error_type": type(error).__name__,
            "message": str(error)[-4000:], "seconds": time.monotonic() - started,
        }))
        raise
