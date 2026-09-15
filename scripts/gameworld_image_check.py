"""Static checks for the public GameWorld Fleet image contract."""

import json
from pathlib import Path
import re
import shlex
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fps_bench.qwen_baseline import sha256
from image.write_provenance import build_manifest


COPIED = {
    "cua-driver/", "fps_bench/", "configs/",
    "scripts/gameworld_driver_contract.py", "scripts/gameworld_driver_worker.py",
    "scripts/gameworld_rollout_worker.py", "image/rebuild_driver.sh",
    "image/smoke_gameworld.py", "image/write_provenance.py",
    ".auto/gameworld-prompt.md", ".auto/measure_gameworld.sh",
    "docs/GAMEWORLD_FLEET.md",
}
TRIGGERS = {
    ".github/workflows/gameworld-image.yml", ".dockerignore", "image/**",
    "cua-driver/**", "fps_bench/**", "configs/**",
    "scripts/gameworld_driver_contract.py", "scripts/gameworld_driver_worker.py",
    "scripts/gameworld_image_check.py", "scripts/gameworld_rollout_worker.py",
    ".auto/gameworld-prompt.md", ".auto/measure_gameworld.sh",
    "docs/GAMEWORLD_FLEET.md", "README.md",
}


def copied_sources(dockerfile):
    normalized = dockerfile.replace("\\\n", " ")
    copied = set()
    for line in normalized.splitlines():
        if line.startswith("COPY "):
            fields = shlex.split(line)
            copied.update(fields[1:-1])
    return copied


def workflow_paths(workflow):
    section = workflow.split("    paths:\n", 1)[1]
    section = section.split("\n\npermissions:", 1)[0]
    return {line.strip()[2:] for line in section.splitlines() if line.strip().startswith("- ")}


def check_manifest():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "repo"
        driver = Path(directory) / "cua-driver"
        gameworld = Path(directory) / "GameWorld"
        for folder in (root / "fps_bench", root / "scripts", root / ".auto",
                       gameworld / "games/gameworld-games"):
            folder.mkdir(parents=True)
        (root / "fps_bench/runtime.py").write_text("VALUE = 1\n")
        (root / "scripts/worker.py").write_text("print('ready')\n")
        (root / ".auto/prompt.md").write_text("# Research\n")
        (root / "README.md").write_text("# Image\n")
        driver.write_bytes(b"native-driver")
        revisions = {gameworld: "b" * 40, gameworld / "games/gameworld-games": "c" * 40}
        manifest = build_manifest(
            "a" * 40, root=root, driver=driver, gameworld_home=gameworld,
            require_gameworld=True, revision_reader=revisions.__getitem__)
        assert manifest["schema_version"] == 2
        assert manifest["artifacts"] == {"/usr/local/bin/cua-driver": sha256(driver)}
        assert manifest["upstream"] == {
            "gameworld_revision": "b" * 40, "games_revision": "c" * 40}
        assert set(manifest["files_sha256"]) == {
            "fps_bench/runtime.py", "scripts/worker.py", ".auto/prompt.md", "README.md"}
        json.dumps(manifest, sort_keys=True)


def main():
    dockerfile = (ROOT / "image/Dockerfile.gameworld").read_text()
    workflow = (ROOT / ".github/workflows/gameworld-image.yml").read_text()
    assert re.search(r"^ARG WORKER_BASE=ghcr\.io/trycua/gameworld-autoresearch@sha256:[0-9a-f]{64}$",
                     dockerfile, re.MULTILINE)
    assert copied_sources(dockerfile) == COPIED, copied_sources(dockerfile) ^ COPIED
    assert all((ROOT / name.rstrip("/")).exists() for name in COPIED)
    assert "image/write_provenance.py \"$SOURCE_REVISION\" --require-gameworld" in dockerfile
    assert TRIGGERS <= workflow_paths(workflow), TRIGGERS - workflow_paths(workflow)
    assert "python3 scripts/gameworld_image_check.py" in workflow
    assert "PYTHONPATH=/opt/gameworld-autoresearch" in dockerfile
    assert "RUN cd /tmp" in dockerfile
    for worker in ("rollout", "driver"):
        assert f"/opt/gameworld-autoresearch/scripts/gameworld_{worker}_worker.py --help" in dockerfile
    for package, target in (("cua-driver-core", "contract_parity"),
                            ("cua-driver", "compatibility_contract_test")):
        assert f"cargo test --offline --locked -p {package} --test {target} --no-run" in dockerfile
    for name, expected in {
        "cli.json": "00d16fae4f44ebdbe1331b7b572764c069f0373090ab110b80536a690b52e194",
        "mcp.json": "5579eb51178f08c69fbb6b28a63a59f253a600858505ea80f5df94c105c387cb",
    }.items():
        assert sha256(ROOT / "cua-driver/compat-fixtures" / name) == expected
    check_manifest()
    print("Validated GameWorld COPY inputs, rebuild triggers, and schema-v2 runtime provenance")


if __name__ == "__main__":
    main()
