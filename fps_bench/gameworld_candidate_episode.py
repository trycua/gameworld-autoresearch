"""Run one frozen multi-step GameWorld candidate evaluation inside a Fleet desktop."""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import asyncio
import json
import math
import os
from pathlib import Path
import re
import time

from fps_bench.evaluation_contract import canonical, digest, exclusive_write, split_for_controller, split_units, verify
from fps_bench.gameworld_baseline import upstream_module
from fps_bench.gameworld_evaluation import validate_contract
from fps_bench.gameworld_grpo import validate_policy_identity
from fps_bench.gameworld_suite_episode import catalog_specs, execute, prompt, resolve_action, response_format, semantic_controls, suite_environment
from fps_bench.qwen_baseline import endpoint, request
from fps_bench.qwen_protocol import messages


IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


def validate_inputs(contract, contract_hash, assignment, candidate, policy_identity, driver):
    validate_contract(contract, contract_hash)
    settings = split_for_controller(contract, assignment.get("split"))
    axis, units = split_units(settings)
    matches = [unit for unit in units if unit[axis] == assignment.get(axis)]
    required = {"split", "repeat", "comparison"} | {name for unit in units for name in unit}
    if (set(assignment) != required or len(matches) != 1
            or any(assignment[name] != value for name, value in matches[0].items())
            or not IDENTIFIER.fullmatch(assignment["comparison"])
            or type(assignment["repeat"]) is not int
            or not 0 <= assignment["repeat"] < settings["repeats"]):
        raise ValueError("Candidate episode differs from the frozen task assignment")
    if (candidate.get("contract_hash") != contract_hash or candidate.get("image") != contract["spec"]["provenance"]["image"]
            or candidate.get("driver_sha256") != digest(Path(driver).read_bytes())
            or candidate.get("policy_sha256") != digest(canonical(policy_identity))
            or candidate.get("model", {}).get("base_model") != policy_identity.get("base_model")
            or candidate.get("model", {}).get("base_revision") != policy_identity.get("base_revision")
            or candidate.get("model", {}).get("adapter_sha256") != policy_identity.get("adapter_sha256")
            or candidate.get("model", {}).get("served_model") != policy_identity.get("served_model")):
        raise ValueError("Candidate runtime identity differs from the controller manifest")
    validate_policy_identity(policy_identity, {"model": {
        "base_model": contract["episode_template"]["model"],
        "base_revision": contract["episode_template"]["revision"],
    }})
    if digest(endpoint().encode()) != policy_identity["deployment"]["endpoint_sha256"]:
        raise ValueError("Candidate evaluation endpoint differs from the deployment identity")
    return assignment


async def run(contract, contract_hash, assignment, candidate, policy_identity, output, driver):
    from PIL import ImageGrab

    validate_inputs(contract, contract_hash, assignment, candidate, policy_identity, driver)
    home = Path(os.environ.get("GAMEWORLD_HOME", "/opt/GameWorld"))
    game_spec, task_spec = catalog_specs(home, assignment["game"], assignment["task"])
    controls = semantic_controls(game_spec)
    system_prompt = prompt(game_spec, task_spec, controls)
    max_steps = contract["episode_template"]["max_steps"]
    evaluator = upstream_module(home, "task_evaluator").build_task_evaluator(
        task_spec["evaluator_config"], max_steps=max_steps)
    models = await asyncio.to_thread(request, endpoint(), "/models", 120)
    if policy_identity["served_model"] not in {item.get("id") for item in models.get("data", [])}:
        raise RuntimeError("Candidate serving endpoint does not advertise the admitted model")
    history, rows, invalid_actions, driver_errors = [], [], 0, 0
    usage = {"prompt_tokens": 0, "completion_tokens": 0}
    started = time.monotonic()
    config = {"game": assignment["game"], "task": assignment["task"], "seed": assignment["seed"]}
    async with suite_environment(config, output, driver, task_spec.get("game_url_suffix")) as (page, call, target):
        evaluation = None
        before = await page.evaluate("window.gameAPI.getState()")
        for step in range(max_steps):
            screenshot = output / f"{step:03d}.png"
            ImageGrab.grab(xdisplay=os.environ.get("DISPLAY", ":1")).save(screenshot)
            request_messages = messages(screenshot, history[-4:])
            request_messages[0]["content"] = system_prompt
            payload = {"model": policy_identity["served_model"], "messages": request_messages,
                       "temperature": 0, "top_p": 1, "max_tokens": contract["episode_template"]["max_tokens"],
                       "seed": (assignment["seed"] + step) & 0xFFFFFFFF,
                       "response_format": response_format(controls)}
            response = await asyncio.to_thread(request, endpoint(), "/chat/completions", 120, payload)
            exclusive_write(output / f"{step:03d}-response.json", canonical(response), 0o400)
            response_usage = response.get("usage") or {}
            for name in usage:
                usage[name] += int(response_usage.get(name, 0) or 0)
            text = response["choices"][0]["message"]["content"]
            action, invalid = None, None
            try:
                action = resolve_action(text, controls)
            except (ValueError, TypeError, json.JSONDecodeError) as error:
                invalid, invalid_actions = str(error), invalid_actions + 1
            execution = {"status": "invalid_model_action", "driver_tools": []}
            if action is not None:
                try:
                    execution = await execute(call, target, action)
                except Exception as error:
                    execution = {"status": "driver_error", "driver_tools": [],
                                 "error_type": type(error).__name__, "message": str(error)[-500:]}
            if execution["status"] in ("driver_error", "unsupported_current_driver"):
                driver_errors += 1
            await asyncio.sleep(0.3)
            after = await page.evaluate("window.gameAPI.getState()")
            evaluation = await evaluator(after, step + 1, {} if evaluation is None else evaluation.metrics)
            rows.append({"step": step, "observation": screenshot.name,
                         "observation_sha256": digest(screenshot.read_bytes()), "response": text,
                         "action": action, "invalid_action": invalid, "execution": execution,
                         "before": before, "after": after, "evaluation": asdict(evaluation)})
            history.append(text)
            before = after
            if evaluation.should_stop:
                break
        final = await evaluator(before, len(rows), evaluation.metrics, finalized=True)
    trajectory = b"".join(canonical(row) for row in rows)
    exclusive_write(output / "trajectory.jsonl", trajectory, 0o400)
    summary = {"status": "complete", "success": final.status == "success", "steps": len(rows),
               "invalid_actions": invalid_actions, "driver_errors": driver_errors,
               "progress": float(final.metrics.get("progress", 0) or 0),
               "seconds": time.monotonic() - started, "usage": usage, "evaluation": asdict(final)}
    exclusive_write(output / "summary.json", canonical(summary), 0o400)
    files = {str(path.relative_to(output)): digest(path.read_bytes())
             for path in sorted(output.iterdir()) if path.is_file() and path.name not in ("manifest.json", "result.json")}
    manifest = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
                "contract_sha256": contract_hash, "assignment": assignment,
                "candidate_sha256": digest(canonical(candidate)),
                "policy_sha256": digest(canonical(policy_identity)),
                "driver_sha256": candidate["driver_sha256"], "files": files}
    exclusive_write(output / "manifest.json", canonical(manifest), 0o400)
    execution_statuses = [row["execution"]["status"] for row in rows]
    result = {**assignment, "candidate": candidate["id"], "contract_sha256": contract_hash,
              "status": "complete", "success": summary["success"], "steps": summary["steps"],
              "invalid_actions": invalid_actions, "driver_errors": driver_errors,
              "execution_status": "driver_error" if driver_errors else (
                  "invalid_model_action" if invalid_actions else "executed"),
              "progress": summary["progress"], "seconds": summary["seconds"], "usage": usage,
              "manifest_sha256": digest(canonical(manifest)),
              "execution_statuses": execution_statuses}
    exclusive_write(output / "result.json", canonical(result), 0o400)
    return result


def verify_artifacts(root, contract_hash, assignment, candidate, policy_identity):
    root = Path(root)
    manifest_data = (root / "manifest.json").read_bytes()
    result_data = (root / "result.json").read_bytes()
    manifest, result = json.loads(manifest_data), json.loads(result_data)
    if (canonical(manifest) != manifest_data or canonical(result) != result_data
            or manifest.get("contract_sha256") != contract_hash or manifest.get("assignment") != assignment
            or manifest.get("candidate_sha256") != digest(canonical(candidate))
            or manifest.get("policy_sha256") != digest(canonical(policy_identity))
            or result.get("manifest_sha256") != digest(manifest_data)
            or any(result.get(key) != value for key, value in {**assignment, "candidate": candidate["id"],
                                                               "contract_sha256": contract_hash}.items())):
        raise ValueError("Candidate evaluation artifacts differ from admitted identities")
    for name, expected in manifest.get("files", {}).items():
        path = root / name
        if Path(name).is_absolute() or ".." in Path(name).parts or not path.is_file() or path.is_symlink() or digest(path.read_bytes()) != expected:
            raise ValueError("Candidate evaluation artifact inventory changed")
    actual = {str(path.relative_to(root)) for path in root.iterdir()
              if path.is_file() and path.name not in ("manifest.json", "result.json", "artifact-receipt.json",
                                                       "provider-result.json")}
    if actual != set(manifest.get("files", {})):
        raise ValueError("Candidate evaluation contains unregistered artifacts")
    summary = json.loads((root / "summary.json").read_bytes())
    if (result.get("status") != "complete" or summary.get("status") != "complete"
            or result.get("success") != summary.get("success") or result.get("steps") != summary.get("steps")
            or result.get("invalid_actions") != summary.get("invalid_actions")
            or result.get("driver_errors") != summary.get("driver_errors")
            or result.get("progress") != summary.get("progress")
            or type(result.get("success")) is not bool
            or type(result.get("steps")) is not int or not 1 <= result["steps"] <= 60
            or any(type(result.get(name)) is not int or not 0 <= result[name] <= result["steps"]
                   for name in ("invalid_actions", "driver_errors"))
            or type(result.get("progress")) not in (int, float) or not math.isfinite(result["progress"])
            or not 0 <= result["progress"] <= 1
            or type(result.get("seconds")) not in (int, float) or not math.isfinite(result["seconds"])
            or result["seconds"] <= 0):
        raise ValueError("Candidate evaluation summary and result disagree")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--contract-sha256", required=True)
    parser.add_argument("--assignment", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--policy-identity", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--driver", default="/usr/local/bin/cua-driver")
    args = parser.parse_args()
    contract = verify(args.contract, args.contract_sha256)
    assignment = json.loads(args.assignment.read_bytes())
    candidate = json.loads(args.candidate.read_bytes())
    policy_identity = json.loads(args.policy_identity.read_bytes())
    if any(canonical(value) != path.read_bytes() for value, path in (
            (assignment, args.assignment), (candidate, args.candidate), (policy_identity, args.policy_identity))):
        raise ValueError("Candidate evaluation inputs require canonical encoding")
    args.output.mkdir(parents=True, exist_ok=False)
    result = asyncio.run(asyncio.wait_for(
        run(contract, args.contract_sha256, assignment, candidate, policy_identity, args.output, args.driver),
        contract["episode_template"]["max_steps"] * 150))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
