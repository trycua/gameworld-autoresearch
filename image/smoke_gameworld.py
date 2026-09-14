"""Verify the real GameWorld renderer and native driver key delivery without Qwen."""

import asyncio
import hashlib
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fps_bench.gameworld_baseline import game_environment
from fps_bench.gameworld_suite_catalog import GAMEWORLD_REVISION, GAMES_REVISION
from fps_bench.gameworld_suite_episode import DRIVER
from fps_bench.qwen_baseline import ROOT


async def main():
    config = json.loads((ROOT / "configs/qwen-gameworld-baseline.json").read_text())
    driver_path = Path("/usr/local/bin/cua-driver")
    driver_sha256 = hashlib.sha256(driver_path.read_bytes()).hexdigest()
    provenance = json.loads((ROOT / "image-source.json").read_text())
    assert driver_sha256 == DRIVER
    assert provenance["schema_version"] == 2
    assert provenance["artifacts"] == {str(driver_path): driver_sha256}
    assert provenance["upstream"] == {
        "gameworld_revision": GAMEWORLD_REVISION, "games_revision": GAMES_REVISION}
    with tempfile.TemporaryDirectory(prefix="gameworld-smoke-") as directory:
        async with game_environment(config, Path(directory), "/usr/local/bin/cua-driver") as (page, call, target):
            await page.evaluate("""() => {
                window.__driverProbe = [];
                document.addEventListener('keydown', event => window.__driverProbe.push({
                    key: event.key, trusted: event.isTrusted
                }));
            }""")
            from PIL import ImageGrab

            screenshot = ImageGrab.grab(xdisplay=":1")
            assert min(screenshot.size) > 100
            assert await page.locator(".tile").count() >= 2
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
