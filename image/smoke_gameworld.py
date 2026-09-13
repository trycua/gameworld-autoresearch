"""Verify the real GameWorld renderer and native driver key delivery without Qwen."""

import asyncio
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fps_bench.gameworld_baseline import game_environment
from fps_bench.qwen_baseline import ROOT


async def main():
    config = json.loads((ROOT / "configs/qwen-gameworld-baseline.json").read_text())
    with tempfile.TemporaryDirectory(prefix="gameworld-smoke-") as directory:
        async with game_environment(config, Path(directory), "/usr/local/bin/cua-driver") as (page, call, target):
            await page.evaluate("""() => {
                window.__driverProbe = [];
                document.addEventListener('keydown', event => window.__driverProbe.push({
                    key: event.key, trusted: event.isTrusted
                }));
            }""")
            before = await page.evaluate("window.gameAPI.getState()")
            for key in ("left", "down", "right", "up"):
                await call("press_key", {**target, "key": key, "hold_ms": 80})
                await asyncio.sleep(0.3)
            after = await page.evaluate("window.gameAPI.getState()")
            events = await page.evaluate("window.__driverProbe")
            expected = {"ArrowLeft", "ArrowDown", "ArrowRight", "ArrowUp"}
            assert {event["key"] for event in events if event["trusted"]} == expected, events
            assert before["game_state"] != after["game_state"], "native actions did not change game state"
            print(json.dumps({"status": "ready", "game": config["game"],
                              "trusted_keys": len(events), "max_tile": after["metrics"]["max_tile"]}))


asyncio.run(main())
