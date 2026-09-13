"""Run one upstream GameWorld 2048 task with visual Qwen and native driver input."""

from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid

from fps_bench.gameworld_protocol import PROMPT, model_messages, parse_action
from fps_bench.qwen_baseline import ROOT, endpoint, request, sha256, source_manifest, write_json


def upstream_module(home: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, home / "env" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


async def driver_command(driver: str, socket: str, *arguments: str) -> dict:
    process = await asyncio.create_subprocess_exec(
        driver, *arguments, "--socket", socket,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), 30)
    except asyncio.TimeoutError:
        process.kill()
        await process.communicate()
        raise RuntimeError("driver request timed out") from None
    if process.returncode:
        raise RuntimeError(f"driver failed: {stderr.decode(errors='replace')[-1000:]}")
    if arguments[0] == "status":
        return {"status": "ready"}
    data = json.loads(stdout)
    if not isinstance(data, dict) or data.get("isError"):
        raise RuntimeError(f"driver tool error: {data}")
    return data


@asynccontextmanager
async def game_environment(config: dict, output: Path, driver: str):
    from playwright.async_api import async_playwright

    home = Path(os.environ.get("GAMEWORLD_HOME", "/opt/GameWorld"))
    launcher = upstream_module(home, "game_launcher").GameLauncher(config["game"])
    session = "gameworld-" + uuid.uuid4().hex
    with tempfile.TemporaryDirectory(prefix="gameworld-driver-") as directory:
        socket = str(Path(directory) / "driver.sock")
        with (output / "driver-server.log").open("w") as log:
            server = subprocess.Popen(
                [driver, "serve", "--socket", socket,
                 "--dangerously-bypass-approvals", "--no-permissions-gate"],
                stdout=log, stderr=subprocess.STDOUT,
            )
            try:
                for attempt in range(100):
                    if server.poll() is not None:
                        raise RuntimeError("driver daemon exited")
                    try:
                        await driver_command(driver, socket, "status")
                        break
                    except (RuntimeError, ValueError):
                        await asyncio.sleep(0.2)
                else:
                    raise RuntimeError("driver readiness timeout")

                async def call(tool: str, arguments: dict):
                    data = await driver_command(
                        driver, socket, "call", tool,
                        json.dumps({**arguments, "session": session}),
                    )
                    with (output / "driver-calls.jsonl").open("a") as handle:
                        handle.write(json.dumps({"tool": tool, "arguments": arguments,
                                                 "result": data}) + "\n")
                    return data

                url = launcher.start()
                async with async_playwright() as playwright:
                    browser = await playwright.chromium.launch(
                        headless=False, args=["--no-sandbox", "--disable-dev-shm-usage",
                                             "--window-position=0,0", "--window-size=1000,740"],
                    )
                    try:
                        context = await browser.new_context(viewport={"width": 980, "height": 620})
                        seed_script = (home / "env/browser_scripts/deterministic_random.js").read_text()
                        await context.add_init_script(seed_script.replace("__RANDOM_SEED__", str(config["seed"])))
                        page = await context.new_page()
                        for attempt in range(30):
                            try:
                                await page.goto(url, wait_until="load", timeout=10000)
                                break
                            except Exception:
                                if attempt == 29:
                                    raise
                                await asyncio.sleep(0.2)
                        await page.wait_for_function("Boolean(window.gameAPI && window.gameAPI.getState)")
                        initialization = await page.evaluate("seed => window.gameAPI.init({seed})", config["seed"])
                        if not initialization.get("ok"):
                            raise RuntimeError(f"GameWorld init failed: {initialization}")
                        write_json(output / "initialization.json", initialization)
                        title = f"GameWorld-{session}"
                        await page.evaluate("title => { document.title = title; }", title)
                        target = None
                        for attempt in range(50):
                            data = await call("list_windows", {})
                            windows = data.get("windows", data.get("structuredContent", {}).get("windows", []))
                            target = next((window for window in windows if title in window.get("title", "")), None)
                            if target:
                                break
                            await asyncio.sleep(0.1)
                        if not target:
                            raise RuntimeError("GameWorld browser window not found by driver")
                        arguments = {"pid": target["pid"], "window_id": target.get("window_id", target.get("id"))}
                        frame = target.get("frame") or target.get("bounds")
                        if not frame:
                            raise RuntimeError("driver window frame missing")
                        await call("click", {**arguments, "x": int(frame["x"] + frame["width"] / 2),
                                              "y": int(frame["y"] + frame["height"] / 2)})
                        await asyncio.sleep(0.5)
                        yield page, call, arguments
                    finally:
                        await browser.close()
            finally:
                launcher.stop()
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()


async def run(config: dict, output: Path, driver: str) -> dict:
    from PIL import ImageGrab
    import yaml

    home = Path(os.environ.get("GAMEWORLD_HOME", "/opt/GameWorld"))
    task_path = home / "catalog/tasks" / config["game"] / f'{config["task"]}.yaml'
    task = yaml.safe_load(task_path.read_text())
    evaluate = upstream_module(home, "task_evaluator").build_task_evaluator(
        task["evaluator_config"], max_steps=config["max_steps"],
    )
    base = endpoint()
    models = await asyncio.to_thread(request, base, "/models", config["request_timeout_seconds"])
    if config["served_model"] not in [model["id"] for model in models.get("data", [])]:
        raise RuntimeError("endpoint model does not match pinned configuration")
    history, metrics = [], {}
    invalid = 0
    usage = {"prompt_tokens": 0, "completion_tokens": 0}
    started = time.monotonic()
    (output / "prompt.txt").write_text(PROMPT)
    write_json(output / "task.json", task)
    async with game_environment(config, output, driver) as (page, call, target):
        for step in range(config["max_steps"]):
            before = await page.evaluate("window.gameAPI.getState()")
            image = output / f"{step:03d}.png"
            ImageGrab.grab(xdisplay=os.environ.get("DISPLAY", ":1")).save(image)
            payload = {"model": config["served_model"], "messages": model_messages(image, history),
                       "temperature": config["temperature"], "seed": config["seed"],
                       "max_tokens": config["max_tokens"]}
            response = await asyncio.to_thread(request, base, "/chat/completions",
                                               config["request_timeout_seconds"], payload)
            write_json(output / f"{step:03d}-response.json", response)
            text = response["choices"][0]["message"]["content"]
            action, error = None, None
            try:
                action = parse_action(text)
            except (ValueError, TypeError) as exception:
                invalid += 1
                error = str(exception)
            if action:
                await call("press_key", {**target, "key": action["key"], "hold_ms": config["hold_ms"]})
            await asyncio.sleep(config["settle_seconds"])
            after = await page.evaluate("window.gameAPI.getState()")
            evaluation = await evaluate(after, step + 1, metrics)
            metrics = evaluation.metrics
            history.append(text if isinstance(text, str) else "invalid empty response")
            for name in usage:
                usage[name] += (response.get("usage") or {}).get(name, 0) or 0
            with (output / "trajectory.jsonl").open("a") as handle:
                handle.write(json.dumps({"step": step, "observation": image.name,
                                        "observation_sha256": sha256(image), "response": text,
                                        "action": action, "invalid_action": error,
                                        "before": before, "after": after,
                                        "evaluation": asdict(evaluation)}) + "\n")
            print(json.dumps({"step": step + 1, "action": action,
                              "max_tile": after.get("metrics", {}).get("max_tile"),
                              "status": evaluation.status}), flush=True)
            if evaluation.status == "error":
                raise RuntimeError(f"GameWorld evaluator error: {evaluation.summary}")
            if evaluation.should_stop or evaluation.should_reset:
                break
        evaluation = await evaluate(after, step + 1, metrics, finalized=True)
        ImageGrab.grab(xdisplay=os.environ.get("DISPLAY", ":1")).save(output / "final.png")
        write_json(output / "final-state.json", after)
    return {"status": "complete", "success": evaluation.status == "success",
            "steps": step + 1, "invalid_actions": invalid, "usage": usage,
            "seconds": time.monotonic() - started, "evaluation": asdict(evaluation)}


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--driver", default="/usr/local/bin/cua-driver")
    args = parser.parse_args()
    config = json.loads((ROOT / "configs/qwen-gameworld-baseline.json").read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    home = Path(os.environ.get("GAMEWORLD_HOME", "/opt/GameWorld"))
    manifest = {"status": "running", "started_at": datetime.now(timezone.utc).isoformat(),
                "config": config, "source": source_manifest(), "driver_sha256": sha256(Path(args.driver)),
                "perception": "desktop screenshot and previous four responses; no evaluator state",
                "protocol_note": "custom cua-driver visual pilot, not the upstream published benchmark harness",
                "gameworld_revision": subprocess.check_output(["git", "-C", str(home), "rev-parse", "HEAD"]).decode().strip(),
                "games_revision": subprocess.check_output(["git", "-C", str(home / "games/gameworld-games"), "rev-parse", "HEAD"]).decode().strip()}
    write_json(args.output / "manifest.json", manifest)
    try:
        summary = asyncio.run(asyncio.wait_for(run(config, args.output, args.driver), config["timeout_seconds"]))
        write_json(args.output / "summary.json", summary)
        manifest["status"] = "complete"
        print(f'METRIC score={float(summary["success"]):.4f}')
    except BaseException as error:
        manifest.update(status="failed", error_type=type(error).__name__)
        raise
    finally:
        manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
        write_json(args.output / "manifest.json", manifest)


if __name__ == "__main__":
    main()
