"""One measured GameWorld catalog step using current Qwen and Cua Driver behavior."""

from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import asyncio
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import uuid

from fps_bench.gameworld_baseline import GameServer, driver_command, upstream_module
from fps_bench.qwen_baseline import endpoint, request, sha256, write_json
from fps_bench.qwen_protocol import messages


MODEL = "Qwen/Qwen3-VL-2B-Instruct"
REVISION = "89644892e4d85e24eaac8bacfd4f463576704203"
SERVED_MODEL = "qwen3-vl-2b-instruct-89644892e4d8"
DRIVER = "37f78e4db6f96e5b36a6dc2912ca6b1539bf938569967aaade99ab5fc81e0ec4"
GAMEWORLD_REVISION = "3c26bdab436800fd61ef40543b64ca40d12c7e4a"
GAMES_REVISION = "55322928fa8bd51cb1719bd3807a32634aa5d3cb"
CATALOG_MANIFEST_SHA256 = "8e1c68c9680fe50b0dd71e581aef7ce8670b730e8b5bf83dc14c686dea0372a2"


def validate_assignment(config):
    required = {"game", "task", "seed", "served_model", "catalog_manifest_sha256"}
    if not isinstance(config, dict) or set(config) != required:
        raise ValueError("Unexpected suite episode assignment")
    if (not re.fullmatch(r"[0-9]{2}_[a-z0-9-]+", config["game"])
            or not re.fullmatch(r"[0-9]{2}_[0-9]{2}", config["task"])
            or config["game"][:2] != config["task"][:2]
            or type(config["seed"]) is not int or not 0 <= config["seed"] <= 0xFFFFFFFF
            or config["served_model"] != SERVED_MODEL
            or config["catalog_manifest_sha256"] != CATALOG_MANIFEST_SHA256):
        raise ValueError("Suite episode assignment differs from the pinned campaign")
    return config


def catalog_specs(home, game, task):
    import yaml

    game_spec = yaml.safe_load((home / "catalog/games" / f"{game}.yaml").read_text())
    task_spec = yaml.safe_load((home / "catalog/tasks" / game / f"{task}.yaml").read_text())
    return game_spec, task_spec


def semantic_controls(game_spec):
    roles = game_spec["game_roles"]
    controls = {}
    for role in roles:
        for control in role["semantic_controls"]:
            name = control["id"] if len(roles) == 1 else role["name"] + "." + control["id"]
            if name in controls:
                raise ValueError("Duplicate semantic control identity")
            controls[name] = {
                "description": control["description"],
                "parameters": control.get("parameters", {}),
                "required": control.get("required", []),
                "binding": control["binding"],
            }
    if not controls:
        raise ValueError("Game has no semantic controls")
    return controls


def prompt(game_spec, task_spec, controls):
    roles = "\n\n".join(role["prompt"]["role_section"].strip()
                           for role in game_spec["game_roles"])
    actions = []
    for name, control in controls.items():
        arguments = ", ".join(control["required"])
        suffix = f" Required arguments: {arguments}." if arguments else " Arguments must be empty."
        actions.append(f"- {name}: {control['description'].strip()}{suffix}")
    return "\n\n".join([
        game_spec["game_rules"].strip(),
        "TASK\n" + task_spec["task_prompt"].strip(),
        roles,
        "REGISTERED ACTIONS\nChoose exactly one action this step.\n" + "\n".join(actions),
        "Return only JSON with exactly tool_name and arguments, for example: "
        '{"tool_name":"wait","arguments":{}}. Do not expose game state or add prose.',
    ])


def response_format(controls):
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "gameworld_semantic_action",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "tool_name": {"type": "string", "enum": sorted(controls)},
                    "arguments": {
                        "type": "object",
                        "properties": {
                            "cell": {"type": "string", "maxLength": 3},
                            "text": {"type": "string", "maxLength": 16},
                        },
                        "additionalProperties": False,
                    },
                },
                "required": ["tool_name", "arguments"],
                "additionalProperties": False,
            },
        },
    }


def resolve_action(text, controls):
    raw = json.loads(text)
    if not isinstance(raw, dict) or set(raw) != {"tool_name", "arguments"}:
        raise ValueError("Expected exactly tool_name and arguments")
    name, arguments = raw["tool_name"], raw["arguments"]
    if name not in controls or not isinstance(arguments, dict):
        raise ValueError("Unknown semantic control or invalid arguments")
    control = controls[name]
    parameters, required = control["parameters"], set(control["required"])
    if set(arguments) != required or set(arguments) - set(parameters):
        raise ValueError("Semantic control arguments differ from the catalog")
    for key, value in arguments.items():
        if parameters[key].get("type") == "string" and (not isinstance(value, str) or not value):
            raise ValueError("Semantic string argument must be nonempty")
    binding = dict(control["binding"])
    if binding.pop("cell_param", False):
        cells = binding.pop("cell_bindings", {})
        cell = arguments["cell"].lower()
        if cell not in cells:
            raise ValueError("Cell argument is outside the catalog binding")
        binding.update(cells[cell])
    for key, value in arguments.items():
        binding.setdefault(key, value)
    return {"semantic_control": name, "arguments": arguments, "binding": binding}


def driver_key(key):
    aliases = {"ArrowUp": "up", "ArrowDown": "down", "ArrowLeft": "left",
               "ArrowRight": "right", "Space": "space", "Enter": "enter",
               "Backspace": "backspace", "Shift": "shift"}
    return aliases.get(key, key.lower() if len(key) == 1 else key)


async def execute(call, target, action):
    binding = action["binding"]
    kind = binding["action"]
    duration = min(2.0, max(0.0, float(binding.get("duration", 0.4))))
    if kind == "wait":
        await asyncio.sleep(duration)
        return {"status": "executed", "driver_tools": []}
    if kind == "press_key":
        await call("press_key", {**target, "key": driver_key(binding["key"]),
                                 "hold_ms": round(duration * 1000)})
        return {"status": "executed", "driver_tools": ["press_key"]}
    if kind == "press_keys":
        return {"status": "unsupported_current_driver", "driver_tools": [],
                "reason": "Cua Driver has no arbitrary simultaneous non-modifier key primitive"}
    if kind == "click":
        tool = "right_click" if binding.get("button") == "right" else "click"
        await call(tool, {**target, "x": binding["x"], "y": binding["y"]})
        return {"status": "executed", "driver_tools": [tool]}
    if kind == "click_hold":
        arguments = {**target, "x": binding["x"], "y": binding["y"],
                     "button": binding.get("button", "left")}
        await call("mouse_button_down", arguments)
        try:
            await asyncio.sleep(duration)
        finally:
            await call("mouse_button_up", target)
        return {"status": "executed", "driver_tools": ["mouse_button_down", "mouse_button_up"]}
    if kind == "mouse_move":
        tools = []
        if "from_x" in binding:
            await call("move_cursor", {"x": binding["from_x"], "y": binding["from_y"],
                                       "scope": "desktop"})
            tools.append("move_cursor")
        await call("move_cursor", {"x": binding["x"], "y": binding["y"], "scope": "desktop"})
        tools.append("move_cursor")
        await asyncio.sleep(duration)
        return {"status": "executed", "driver_tools": tools,
                "limitation": "absolute desktop pointer motion is not relative pointer-lock input"}
    if kind == "type":
        await call("type_text", {**target, "text": binding["text"]})
        return {"status": "executed", "driver_tools": ["type_text"]}
    return {"status": "unsupported_current_driver", "driver_tools": [],
            "reason": f"No current Cua Driver mapping for {kind}"}


@asynccontextmanager
async def suite_environment(config, output, driver, suffix):
    from playwright.async_api import async_playwright
    from PIL import ImageGrab

    home = Path(os.environ.get("GAMEWORLD_HOME", "/opt/GameWorld"))
    for _ in range(60):
        try:
            ImageGrab.grab(xdisplay=os.environ.get("DISPLAY", ":1"))
            break
        except OSError:
            await asyncio.sleep(0.5)
    else:
        raise RuntimeError("X11 desktop did not become ready")
    launcher = GameServer(home, config["game"])
    session = "suite-" + uuid.uuid4().hex
    with tempfile.TemporaryDirectory(prefix="suite-driver-") as directory:
        socket = str(Path(directory) / "driver.sock")
        with (output / "driver-server.log").open("w") as log:
            server = subprocess.Popen([driver, "serve", "--socket", socket,
                "--dangerously-bypass-approvals", "--no-permissions-gate"],
                stdout=log, stderr=subprocess.STDOUT)
            try:
                for _ in range(100):
                    if server.poll() is not None:
                        raise RuntimeError("driver daemon exited")
                    try:
                        await driver_command(driver, socket, "status")
                        break
                    except (RuntimeError, ValueError):
                        await asyncio.sleep(0.2)
                else:
                    raise RuntimeError("driver readiness timeout")

                async def call(tool, arguments):
                    data = await driver_command(driver, socket, "call", tool,
                                                json.dumps({**arguments, "session": session}))
                    with (output / "driver-calls.jsonl").open("a") as handle:
                        handle.write(json.dumps({"tool": tool, "arguments": arguments,
                                                 "result": data}) + "\n")
                    return data

                url = launcher.start() + (suffix or "")
                async with async_playwright() as playwright:
                    browser = await playwright.chromium.launch(headless=False, args=[
                        "--no-sandbox", "--disable-dev-shm-usage", "--window-position=0,0",
                        "--window-size=1000,740"])
                    try:
                        context = await browser.new_context(viewport={"width": 980, "height": 620})
                        seed_script = (home / "env/browser_scripts/deterministic_random.js").read_text()
                        await context.add_init_script(seed_script.replace("__RANDOM_SEED__", str(config["seed"])))
                        page = await context.new_page()
                        await page.goto(url, wait_until="load", timeout=30000)
                        await page.wait_for_function("Boolean(window.gameAPI && window.gameAPI.getState)")
                        initialization = await page.evaluate("seed => window.gameAPI.init({seed})", config["seed"])
                        if not initialization.get("ok"):
                            raise RuntimeError("GameWorld init failed")
                        write_json(output / "initialization.json", initialization)
                        title = "GameWorld-" + session
                        await page.evaluate("title => { document.title = title; }", title)
                        target = None
                        for _ in range(50):
                            data = await call("list_windows", {})
                            windows = data.get("windows", data.get("structuredContent", {}).get("windows", []))
                            target = next((window for window in windows if title in window.get("title", "")), None)
                            if target:
                                break
                            await asyncio.sleep(0.1)
                        if not target:
                            raise RuntimeError("GameWorld browser window not found by driver")
                        target = {"pid": target["pid"], "window_id": target.get("window_id", target.get("id")),
                                  "delivery_mode": "foreground"}
                        yield page, call, target
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


async def run(config, output, driver):
    from PIL import ImageGrab

    home = Path(os.environ.get("GAMEWORLD_HOME", "/opt/GameWorld"))
    game_spec, task_spec = catalog_specs(home, config["game"], config["task"])
    controls = semantic_controls(game_spec)
    system_prompt = prompt(game_spec, task_spec, controls)
    evaluator = upstream_module(home, "task_evaluator").build_task_evaluator(
        task_spec["evaluator_config"], max_steps=1)
    base = endpoint()
    models = await asyncio.to_thread(request, base, "/models", 120)
    if config["served_model"] not in [model["id"] for model in models.get("data", [])]:
        raise RuntimeError("Serving model identity differs from assignment")
    started = time.monotonic()
    async with suite_environment(config, output, driver, task_spec.get("game_url_suffix")) as (page, call, target):
        before = await page.evaluate("window.gameAPI.getState()")
        image = output / "000.png"
        ImageGrab.grab(xdisplay=os.environ.get("DISPLAY", ":1")).save(image)
        model_messages = messages(image, [])
        model_messages[0]["content"] = system_prompt
        payload = {"model": config["served_model"], "messages": model_messages,
                   "temperature": 0, "seed": config["seed"], "max_tokens": 128,
                   "response_format": response_format(controls)}
        response = await asyncio.to_thread(request, base, "/chat/completions", 120, payload)
        write_json(output / "000-response.json", response)
        text = response["choices"][0]["message"]["content"]
        action, invalid = None, None
        try:
            action = resolve_action(text, controls)
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            invalid = str(error)
        execution = {"status": "invalid_model_action", "driver_tools": []} if action is None else None
        if action is not None:
            try:
                execution = await execute(call, target, action)
            except Exception as error:
                execution = {"status": "driver_error", "driver_tools": [],
                             "error_type": type(error).__name__, "message": str(error)[-500:]}
        await asyncio.sleep(0.3)
        after = await page.evaluate("window.gameAPI.getState()")
        evaluation = await evaluator(after, 1, {})
        final = await evaluator(after, 1, evaluation.metrics, finalized=True)
        usage = response.get("usage") or {}
        row = {"step": 0, "observation": image.name, "observation_sha256": sha256(image),
               "response": text, "action": action, "invalid_action": invalid,
               "execution": execution, "before": before, "after": after,
               "evaluation": asdict(final)}
        (output / "trajectory.jsonl").write_text(json.dumps(row) + "\n")
        write_json(output / "final-state.json", after)
        ImageGrab.grab(xdisplay=os.environ.get("DISPLAY", ":1")).save(output / "final.png")
    return {"status": "complete", "success": final.status == "success", "steps": 1,
            "invalid_actions": int(invalid is not None), "execution_status": execution["status"],
            "progress": float(final.metrics.get("progress", 0) or 0),
            "usage": {"prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
                      "completion_tokens": int(usage.get("completion_tokens", 0) or 0)},
            "seconds": time.monotonic() - started, "evaluation": asdict(final)}


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--driver", default="/usr/local/bin/cua-driver")
    args = parser.parse_args()
    config = validate_assignment(json.loads(args.config.read_bytes()))
    args.output.mkdir(parents=True, exist_ok=False)
    home = Path(os.environ.get("GAMEWORLD_HOME", "/opt/GameWorld"))
    manifest = {"status": "running", "started_at": datetime.now(timezone.utc).isoformat(),
                "config": config, "driver_sha256": sha256(Path(args.driver)),
                "gameworld_revision": subprocess.check_output(
                    ["git", "-C", str(home), "rev-parse", "HEAD"], text=True).strip(),
                "games_revision": subprocess.check_output(
                    ["git", "-C", str(home / "games/gameworld-games"), "rev-parse", "HEAD"], text=True).strip(),
                "protocol": "one-step-current-driver-compatibility-v1",
                "perception": "desktop screenshot only; evaluator state is not sent to Qwen"}
    if (manifest["driver_sha256"] != DRIVER or manifest["gameworld_revision"] != GAMEWORLD_REVISION
            or manifest["games_revision"] != GAMES_REVISION):
        raise ValueError("Runtime provenance differs from the compatibility campaign")
    write_json(args.output / "manifest.json", manifest)
    try:
        summary = asyncio.run(asyncio.wait_for(run(config, args.output, args.driver), 180))
        write_json(args.output / "summary.json", summary)
        manifest["status"] = "complete"
    except BaseException as error:
        manifest.update(status="failed", error_type=type(error).__name__, error=str(error)[-500:])
        raise
    finally:
        manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
        write_json(args.output / "manifest.json", manifest)


if __name__ == "__main__":
    main()
