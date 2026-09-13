"""Collect a screenshot-only Qwen baseline inside a dedicated X11 game desktop.

python -m fps_bench.qwen_baseline doctor
python -m fps_bench.qwen_baseline run --driver /path/to/cua-driver
"""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import hashlib
import importlib.util
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import tempfile
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fps_bench.qwen_protocol import PROMPT, messages, parse_action

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/qwen-lplatform-baseline.json"


def write_json(path: Path, data: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n")
    temporary.replace(path)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def request(base: str, route: str, timeout: float, payload: Any = None) -> dict:
    headers = {"Authorization": f"Bearer {os.environ['QWEN_API_KEY']}"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode()
    req = urllib.request.Request(base + route, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def endpoint() -> str:
    base = os.environ.get("QWEN_BASE_URL", "").rstrip("/")
    parsed = urlsplit(base)
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("QWEN_BASE_URL must be a plain server URL ending in /v1")
    if parsed.scheme != "https" and not (
        parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1")
    ):
        raise ValueError("use HTTPS except for a localhost inference server")
    if not parsed.path.endswith("/v1"):
        raise ValueError("QWEN_BASE_URL must end in /v1")
    if not os.environ.get("QWEN_API_KEY"):
        raise ValueError("set QWEN_API_KEY")
    return base


def preflight(args, config) -> tuple[list[str], str | None]:
    problems = []
    driver = shutil.which(args.driver)
    if not driver:
        problems.append(f"driver not found: {args.driver}")
    for module in ("cua_bench", "bench_ui", "PIL"):
        if importlib.util.find_spec(module) is None:
            problems.append(f"missing Python package: {module}")
    if not os.environ.get("DISPLAY"):
        problems.append("set DISPLAY to the dedicated game desktop (usually :1)")
    elif importlib.util.find_spec("PIL"):
        try:
            from PIL import ImageGrab
            ImageGrab.grab(xdisplay=os.environ["DISPLAY"])
        except Exception as error:
            problems.append(f"X11 screenshot failed: {type(error).__name__}")
    try:
        base = endpoint()
        models = request(base, "/models", config["request_timeout_seconds"])
        if config["served_model"] not in [item["id"] for item in models.get("data", [])]:
            problems.append("endpoint does not advertise the configured served_model")
    except Exception as error:
        problems.append(f"inference preflight: {type(error).__name__}: {error}")
    return problems, driver


def source_file_hashes() -> dict[str, str]:
    paths = [ROOT / "fps_bench", ROOT / "bench", ROOT / "tasks/fps_lshape", ROOT / "configs",
             ROOT / "infra", ROOT / "cua-driver"]
    return {
        str(path.relative_to(ROOT)): sha256(path)
        for directory in paths for path in directory.rglob("*")
        if path.is_file() and "target" not in path.relative_to(ROOT).parts
        and "__pycache__" not in path.parts
        and path.suffix in (".py", ".json", ".html", ".js", ".sh", ".rs", ".toml", ".lock")
    }


def source_manifest() -> dict:
    hashes = source_file_hashes()
    if not (ROOT / ".git").exists():
        recorded = json.loads((ROOT / "image-source.json").read_text())
        return {"git_commit": recorded["git_commit"], "git_status": None,
                "tracked_diff_sha256": None, "files_sha256": hashes,
                "image_source_modified": hashes != recorded["files_sha256"]}

    def git(*arguments):
        return subprocess.check_output(["git", *arguments], cwd=ROOT).decode()

    return {"git_commit": git("rev-parse", "HEAD").strip(),
            "git_status": git("status", "--short"),
            "tracked_diff_sha256": hashlib.sha256(git("diff", "HEAD").encode()).hexdigest(),
            "files_sha256": hashes}


async def collect(args, config, driver: str, output: Path) -> dict:
    from PIL import ImageGrab
    from bench.run_in_sandbox import LocalSession
    from fps_bench.agent import CuaDriverAgent, RAD_PER_PX
    from bench.run_in_sandbox import task_module

    session = LocalSession(display=os.environ["DISPLAY"])
    base = endpoint()
    session_id = "qwen-" + uuid.uuid4().hex
    episode_results = []
    with tempfile.TemporaryDirectory(prefix="qwen-driver-") as temporary:
        socket_path = str(Path(temporary) / "driver.sock")
        with (output / "driver-server.log").open("w") as server_log:
            server = subprocess.Popen(
                [driver, "serve", "--socket", socket_path,
                 "--dangerously-bypass-approvals", "--no-permissions-gate"],
                stdout=server_log, stderr=subprocess.STDOUT,
            )
            try:
                for attempt in range(100):
                    if server.poll() is not None:
                        raise RuntimeError("driver daemon exited; see driver-server.log")
                    result = await asyncio.create_subprocess_exec(
                        driver, "status", "--socket", socket_path,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                    if await asyncio.wait_for(result.wait(), 5) == 0:
                        break
                    await asyncio.sleep(0.2)
                else:
                    raise RuntimeError("driver daemon readiness timeout")

                class PilotDriver(CuaDriverAgent):
                    async def _call(self, session, tool, arguments):
                        payload = {**arguments, "session": session_id}
                        process = await asyncio.create_subprocess_exec(
                            driver, "call", tool, json.dumps(payload), "--socket", socket_path,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        )
                        try:
                            stdout, stderr = await asyncio.wait_for(process.communicate(), 30)
                        except asyncio.TimeoutError:
                            process.kill()
                            await process.communicate()
                            raise RuntimeError(f"driver {tool} timed out") from None
                        text = stdout.decode(errors="replace")
                        try:
                            data = json.loads(text)
                        except ValueError:
                            data = None
                        info = {"tool": tool, "args": arguments, "rc": process.returncode,
                                "json": data, "err": stderr.decode(errors="replace")[-1000:]}
                        with (output / "driver-calls.jsonl").open("a") as log:
                            log.write(json.dumps(info) + "\n")
                        if process.returncode or not isinstance(data, dict) or data.get("isError"):
                            raise RuntimeError(f"driver {tool} failed; see driver-calls.jsonl")
                        return info

                for episode in range(config["episodes"]):
                    folder = output / f"episode-{episode:03d}"
                    folder.mkdir()
                    agent = PilotDriver(window_title=f"L-Platform-{session_id}-{episode}")
                    html = task_module.game_html().replace(
                        "</head>", "<style>#hud { display: none !important; }</style></head>", 1
                    )
                    pid = await session.launch_window(
                        html=html, title=agent.window_title,
                        width=task_module.WINDOW_W, height=task_module.WINDOW_H,
                    )
                    started = time.monotonic()
                    history = []
                    invalid_actions = 0
                    usage = {"prompt_tokens": 0, "completion_tokens": 0}
                    try:
                        for attempt in range(100):
                            ready = await session.execute_javascript(pid, "Boolean(window.__state && window.__progress)")
                            if ready:
                                break
                            await asyncio.sleep(0.1)
                        else:
                            raise RuntimeError("game readiness timeout")
                        hud_display = await session.execute_javascript(
                            pid, "getComputedStyle(document.querySelector('#hud')).display"
                        )
                        if hud_display != "none":
                            raise RuntimeError("debug HUD is visible; refusing privileged visual leakage")
                        await agent._call(session, "start_session", {})
                        await agent._screen_size(session)
                        target = await agent._resolve_window(session)
                        if not target.get("pid") or not target.get("frame"):
                            raise RuntimeError("cannot resolve game window and frame")
                        await agent._focus(session, target)
                        await asyncio.sleep(config["settle_ms"] / 1000)
                        write_json(folder / "target.json", target)
                        steps = 0
                        termination = "max_steps"
                        for step in range(config["max_steps"]):
                            before = await agent._state(session, pid)
                            if before["reached"]:
                                termination = "success"
                                break
                            if time.monotonic() - started > config["episode_timeout_seconds"]:
                                termination = "timeout"
                                break
                            frame = target["frame"]
                            left, top = int(frame["x"]), int(frame["y"])
                            width, height = int(frame["width"]), int(frame["height"])
                            if width <= 0 or height <= 0:
                                raise RuntimeError("invalid game window bounds")
                            screenshot = folder / f"{step:03d}.png"
                            desktop = ImageGrab.grab(xdisplay=os.environ["DISPLAY"])
                            if left < 0 or top < 0 or left + width > desktop.size[0] or top + height > desktop.size[1]:
                                raise RuntimeError("game window is not fully inside the captured desktop")
                            desktop.crop(
                                (left, top, left + width, top + height)
                            ).save(screenshot)
                            previous = history[-config["history_actions"]:]
                            payload = {"model": config["served_model"],
                                       "messages": messages(screenshot, previous),
                                       "temperature": config["temperature"], "seed": config["seed"],
                                       "max_tokens": config["max_tokens"]}
                            write_json(folder / f"{step:03d}-input.json", {
                                "observation": screenshot.name, "previous_responses": previous,
                                "evaluator_before": before,
                            })
                            requested = time.monotonic()
                            response = await asyncio.to_thread(
                                request, base, "/chat/completions", config["request_timeout_seconds"], payload
                            )
                            latency = time.monotonic() - requested
                            text = response["choices"][0]["message"]["content"]
                            if not isinstance(text, str):
                                raise RuntimeError("inference returned non-text content")
                            write_json(folder / f"{step:03d}-response.json", response)
                            action = None
                            error = None
                            try:
                                action = parse_action(text)
                            except (ValueError, TypeError) as invalid:
                                error = str(invalid)
                                invalid_actions += 1
                            if action:
                                if action["action"] == "key":
                                    await agent._call(session, "press_key", {
                                        "key": action["key"], "hold_ms": action["hold_ms"],
                                        **agent._target_args(target),
                                    })
                                elif action["action"] == "turn":
                                    await agent._turn(session, -action["dx"] * RAD_PER_PX, target)
                                else:
                                    await asyncio.sleep(action["ms"] / 1000)
                            await asyncio.sleep(config["settle_ms"] / 1000)
                            after = await agent._state(session, pid)
                            progress = float(await session.execute_javascript(pid, "window.__progress()"))
                            row = {"episode": episode, "step": step,
                                   "observation": screenshot.name, "observation_sha256": sha256(screenshot),
                                   "previous_responses": previous, "response": text,
                                   "action": action, "invalid_action": error,
                                   "inference_seconds": latency, "usage": response.get("usage", {}),
                                   "evaluator": {"before": before, "after": after, "progress": progress},
                                   "reward": float(bool(after["reached"])), "done": bool(after["reached"])}
                            with (folder / "trajectory.jsonl").open("a") as log:
                                log.write(json.dumps(row) + "\n")
                            for key in usage:
                                usage[key] += response.get("usage", {}).get(key, 0)
                            history.append(text)
                            steps += 1
                            if after["reached"]:
                                termination = "success"
                                break
                        final_state = await agent._state(session, pid)
                        result = {"episode": episode, "success": bool(final_state["reached"]),
                                  "progress": float(await session.execute_javascript(pid, "window.__progress()")),
                                  "falls": int(final_state["falls"]), "steps": steps,
                                  "invalid_actions": invalid_actions, "usage": usage,
                                  "seconds": time.monotonic() - started, "termination": termination}
                        write_json(folder / "result.json", result)
                        episode_results.append(result)
                        print(json.dumps(result), flush=True)
                    finally:
                        try:
                            await agent._call(session, "end_session", {})
                        finally:
                            await session.close_window(pid)
            finally:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()
    count = len(episode_results)
    score = sum(item["success"] for item in episode_results) / count
    return {"status": "complete", "episodes": count, "score": score,
            "mean_progress": sum(item["progress"] for item in episode_results) / count,
            "invalid_actions": sum(item["invalid_actions"] for item in episode_results),
            "records": episode_results}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("doctor", "run"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--driver", default=os.environ.get("CUA_DRIVER_BIN", "cua-driver"))
    parser.add_argument("--episodes", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if args.episodes is not None:
        config["episodes"] = args.episodes
    for name in ("episodes", "max_steps", "episode_timeout_seconds", "request_timeout_seconds", "history_actions"):
        if type(config[name]) is not int or config[name] <= 0:
            parser.error(f"{name} must be a positive integer")
    problems, driver = preflight(args, config)
    if problems:
        print(json.dumps({"status": "blocked", "problems": problems}, indent=2))
        return 2
    if args.command == "doctor":
        print("Preflight passed: desktop capture, Python packages, driver path, model endpoint.")
        return 0
    lock = Path(tempfile.gettempdir()) / f"fps-qwen-{os.getuid()}.lock"
    with lock.open("w") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        output = args.output or ROOT / "results/runs" / (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-qwen-" + uuid.uuid4().hex[:8]
        )
        output.mkdir(parents=True, exist_ok=False)
        manifest = {"status": "running", "started_at": datetime.now(timezone.utc).isoformat(),
                    "config": config, "endpoint": endpoint(), "source": source_manifest(),
                    "driver": str(Path(driver).resolve()), "driver_sha256": sha256(Path(driver)),
                    "python": platform.python_version(), "platform": platform.platform(),
                    "packages": {name: importlib.metadata.version(name)
                                 for name in ("cua-bench", "cua-bench-ui", "pywebview", "Pillow")},
                    "display": os.environ["DISPLAY"], "prompt_sha256": hashlib.sha256(PROMPT.encode()).hexdigest(),
                    "perception": "window screenshot, debug HUD hidden; evaluator state never sent to model",
                    "timing": "real-time game, no pause during inference", "initial_state": "fixed task default"}
        (output / "prompt.txt").write_text(PROMPT)
        write_json(output / "manifest.json", manifest)
        print(f"Artifacts: {output.resolve()}", flush=True)
        try:
            summary = asyncio.run(collect(args, config, driver, output))
            write_json(output / "summary.json", summary)
            manifest["status"] = "complete"
            print(f"METRIC score={summary['score']:.4f}")
            print(f"METRIC mean_progress={summary['mean_progress']:.4f}")
        except BaseException as error:
            manifest["status"] = "failed"
            manifest["error"] = f"{type(error).__name__}: {error}"
            raise
        finally:
            manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
            write_json(output / "manifest.json", manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
