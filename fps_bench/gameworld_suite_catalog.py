"""Pinned GameWorld catalog inventory for the broad auto-research scope."""

import json
from pathlib import Path
import re
import subprocess

from fps_bench.evaluation_contract import canonical, digest


GAMEWORLD_REVISION = "3c26bdab436800fd61ef40543b64ca40d12c7e4a"
GAMES_REVISION = "55322928fa8bd51cb1719bd3807a32634aa5d3cb"
GAME = re.compile(r"^[0-9]{2}_[a-z0-9-]+$")
TASK = re.compile(r"^[0-9]{2}_[0-9]{2}$")


def revision(root):
    return subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()


def discover(upstream, games):
    upstream, games = Path(upstream), Path(games)
    if revision(upstream) != GAMEWORLD_REVISION or revision(games) != GAMES_REVISION:
        raise ValueError("GameWorld source revisions differ from the Fleet image pins")
    game_files = sorted((upstream / "catalog/games").glob("[0-9][0-9]_*.yaml"))
    catalog = []
    for game_file in game_files:
        game = game_file.stem
        if not GAME.fullmatch(game):
            raise ValueError("Invalid game identity")
        task_files = sorted((upstream / "catalog/tasks" / game).glob("*.yaml"))
        tasks = [path.stem for path in task_files]
        if len(tasks) != 5 or any(not TASK.fullmatch(task) for task in tasks):
            raise ValueError(f"Expected five canonical tasks for {game}")
        game_root = games / "benchmark" / game
        if not (game_root / "index.html").is_file():
            raise ValueError(f"Missing packaged game entrypoint for {game}")
        catalog.append({
            "game": game,
            "game_spec_sha256": digest(game_file.read_bytes()),
            "tasks": [
                {"task": path.stem, "task_spec_sha256": digest(path.read_bytes())}
                for path in task_files
            ],
        })
    manifest = {
        "schema_version": 1,
        "gameworld_revision": GAMEWORLD_REVISION,
        "games_revision": GAMES_REVISION,
        "scope": "all-gameworld-catalog-tasks",
        "games": catalog,
        "game_count": len(catalog),
        "task_count": sum(len(item["tasks"]) for item in catalog),
        "pilot": {
            "protocol": "existing-frozen-2048-v2",
            "game": "01_2048",
            "task": "01_01",
            "note": "The initial live test uses current settings; broader action support is research work.",
        },
    }
    validate(manifest)
    return manifest


def validate(manifest):
    required = {
        "schema_version", "gameworld_revision", "games_revision", "scope",
        "games", "game_count", "task_count", "pilot",
    }
    if not isinstance(manifest, dict) or set(manifest) != required:
        raise ValueError("Unexpected suite manifest fields")
    if (manifest["schema_version"] != 1
            or manifest["gameworld_revision"] != GAMEWORLD_REVISION
            or manifest["games_revision"] != GAMES_REVISION
            or manifest["scope"] != "all-gameworld-catalog-tasks"):
        raise ValueError("Suite identity or source revisions changed")
    games, tasks = set(), set()
    for item in manifest["games"]:
        if set(item) != {"game", "game_spec_sha256", "tasks"} or not GAME.fullmatch(item["game"]):
            raise ValueError("Invalid suite game record")
        if item["game"] in games or not re.fullmatch(r"[0-9a-f]{64}", item["game_spec_sha256"]):
            raise ValueError("Duplicate game or invalid game specification hash")
        games.add(item["game"])
        if len(item["tasks"]) != 5:
            raise ValueError("Every catalog game must retain all five tasks")
        for task in item["tasks"]:
            identity = (item["game"], task.get("task"))
            if (set(task) != {"task", "task_spec_sha256"} or not TASK.fullmatch(task["task"])
                    or identity in tasks or not re.fullmatch(r"[0-9a-f]{64}", task["task_spec_sha256"])):
                raise ValueError("Invalid or duplicate suite task record")
            tasks.add(identity)
    if manifest["game_count"] != 34 or len(games) != 34:
        raise ValueError("The auto-research scope must include all 34 games")
    if manifest["task_count"] != 170 or len(tasks) != 170:
        raise ValueError("The auto-research scope must include all 170 tasks")
    if manifest["pilot"] != {
        "protocol": "existing-frozen-2048-v2",
        "game": "01_2048",
        "task": "01_01",
        "note": "The initial live test uses current settings; broader action support is research work.",
    }:
        raise ValueError("Current pilot boundary changed")
    return {"game_count": len(games), "task_count": len(tasks),
            "manifest_sha256": digest(canonical(manifest))}


def load(path):
    manifest = json.loads(Path(path).read_bytes())
    return manifest, validate(manifest)
