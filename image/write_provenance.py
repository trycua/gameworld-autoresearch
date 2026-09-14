"""Record immutable runtime provenance without copying Git credentials/history."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fps_bench.qwen_baseline import ROOT, runtime_file_hashes, sha256


KNOWN_ROOTS = ("cua-driver", "fps_bench", "bench", "tasks", "configs", "infra",
               "scripts", "image", ".auto", "docs")
KNOWN_FILES = ("pyproject.toml", "README.md", ".gitignore")
REVISION = re.compile(r"[0-9a-f]{40}")


def git_revision(path):
    revision = subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
    if not REVISION.fullmatch(revision):
        raise ValueError(f"Invalid upstream revision at {path}")
    return revision


def build_manifest(revision, root=ROOT, driver=Path("/usr/local/bin/cua-driver"),
                   gameworld_home=Path("/opt/GameWorld"), require_gameworld=False,
                   revision_reader=git_revision):
    if not isinstance(revision, str) or not REVISION.fullmatch(revision):
        raise ValueError("SOURCE_REVISION must be the full source Git commit SHA")
    root, driver, gameworld_home = Path(root), Path(driver), Path(gameworld_home)
    source_roots = [name for name in KNOWN_ROOTS if (root / name).is_dir()]
    source_files = [name for name in KNOWN_FILES if (root / name).is_file()]
    if not driver.is_file() or driver.is_symlink():
        raise ValueError("Installed cua-driver binary is unavailable for provenance")
    upstream = {}
    gameworld_games = gameworld_home / "games/gameworld-games"
    if require_gameworld:
        upstream = {
            "gameworld_revision": revision_reader(gameworld_home),
            "games_revision": revision_reader(gameworld_games),
        }
    return {
        "schema_version": 2,
        "git_commit": revision,
        "source_roots": source_roots,
        "source_files": source_files,
        "files_sha256": runtime_file_hashes(root, source_roots, source_files),
        "artifacts": {"/usr/local/bin/cua-driver": sha256(driver)},
        "upstream": upstream,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("revision")
    parser.add_argument("--require-gameworld", action="store_true")
    args = parser.parse_args()
    manifest = build_manifest(args.revision, require_gameworld=args.require_gameworld)
    (ROOT / "image-source.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
