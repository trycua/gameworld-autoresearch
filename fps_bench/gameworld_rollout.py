"""Collect fresh interactive GameWorld trajectories for an admitted GRPO group."""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import asyncio
import json
import os
from pathlib import Path
import time

from fps_bench.evaluation_contract import canonical, digest, exclusive_write
from fps_bench.gameworld_baseline import upstream_module
from fps_bench.gameworld_grpo import IDENTIFIER, SHA256, reward_components, validate_policy_identity, verify_rollout_dataset
from fps_bench.gameworld_research import load_policy
from fps_bench.gameworld_suite_episode import catalog_specs, execute, prompt, resolve_action, semantic_controls, suite_environment
from fps_bench.qwen_baseline import endpoint, request
from fps_bench.qwen_protocol import messages


def validate_assignment(assignment, policy, context):
    required = {"schema_version", "group_id", "game", "task", "seed", "members", "max_steps",
                "catalog_manifest_sha256", "driver_sha256"}
    identity = f"{assignment.get('game')}--{assignment.get('task')}" if isinstance(assignment, dict) else ""
    if (not isinstance(assignment, dict) or set(assignment) != required
            or assignment["schema_version"] != 1
            or not isinstance(assignment["group_id"], str) or not IDENTIFIER.fullmatch(assignment["group_id"])
            or identity not in set(context["splits"]["train"])
            or type(assignment["seed"]) is not int or not 0 <= assignment["seed"] <= 0xFFFFFFFF
            or type(assignment["members"]) is not int
            or not policy["model"]["minimum_grpo_group_size"] <= assignment["members"] <= policy["model"]["maximum_grpo_group_size"]
            or type(assignment["max_steps"]) is not int
            or not 1 <= assignment["max_steps"] <= policy["model"]["maximum_trajectory_steps"]
            or assignment["catalog_manifest_sha256"] != context["catalog_manifest_sha256"]
            or not SHA256.fullmatch(assignment["driver_sha256"])):
        raise ValueError("Invalid or non-training GameWorld rollout assignment")
    return assignment


def training_messages(system_prompt, history, image_name):
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": [
            {"type": "text", "text": "Recent responses (invalid responses do nothing):\n"
             + "\n".join(history[-4:]) + "\nChoose the next action from this screenshot."},
            {"type": "image", "image": image_name},
        ]},
    ]


def write_once(path, data, mode=0o400):
    path = Path(path)
    if path.exists():
        if path.is_symlink() or path.read_bytes() != data:
            raise ValueError(f"Immutable rollout artifact changed: {path}")
        return False
    exclusive_write(path, data, mode)
    return True


async def collect_member(assignment, policy_identity, driver, dataset, custody, member_index):
    from PIL import ImageGrab

    game_spec, task_spec = catalog_specs(Path(os.environ.get("GAMEWORLD_HOME", "/opt/GameWorld")),
                                         assignment["game"], assignment["task"])
    controls = semantic_controls(game_spec)
    system_prompt = prompt(game_spec, task_spec, controls)
    evaluator = upstream_module(Path(os.environ.get("GAMEWORLD_HOME", "/opt/GameWorld")),
                                "task_evaluator").build_task_evaluator(
                                    task_spec["evaluator_config"], max_steps=assignment["max_steps"])
    member_id = "trajectory-" + digest(canonical([assignment["group_id"], member_index]))[:24]
    runtime = custody / member_id
    runtime.mkdir(parents=True, exist_ok=False)
    config = {"game": assignment["game"], "task": assignment["task"], "seed": assignment["seed"]}
    history, rows, custody_rows = [], [], []
    invalid_actions, driver_errors, usage = 0, 0, {"prompt_tokens": 0, "completion_tokens": 0}
    started = time.monotonic()
    async with suite_environment(config, runtime, driver, task_spec.get("game_url_suffix")) as (page, call, target):
        initial = await page.evaluate("window.gameAPI.getState()")
        write_once(runtime / "initial-state.json", canonical(initial))
        evaluation = None
        before_state = initial
        for step in range(assignment["max_steps"]):
            screenshot = runtime / f"{step:03d}.png"
            ImageGrab.grab(xdisplay=os.environ.get("DISPLAY", ":1")).save(screenshot)
            image_data = screenshot.read_bytes()
            image_name = f"images/{digest(image_data)}.png"
            write_once(dataset / image_name, image_data)
            request_messages = messages(screenshot, history[-4:])
            request_messages[0]["content"] = system_prompt
            generation = policy_identity["generation"]
            payload = {"model": policy_identity["served_model"], "messages": request_messages,
                       "temperature": generation["temperature"], "top_p": generation["top_p"],
                       "max_tokens": generation["max_tokens"],
                       "seed": (assignment["seed"] + member_index * 1009 + step) & 0xFFFFFFFF}
            response = await asyncio.to_thread(request, endpoint(), "/chat/completions", 120, payload)
            write_once(runtime / f"{step:03d}-response.json", canonical(response))
            if response.get("model") != policy_identity["served_model"] or len(response.get("choices", [])) != 1:
                raise RuntimeError("Rollout response differs from the admitted serving identity")
            response_usage = response.get("usage") or {}
            for name in usage:
                usage[name] += int(response_usage.get(name, 0) or 0)
            text = response["choices"][0]["message"]["content"]
            action, invalid = None, None
            try:
                action = resolve_action(text, controls)
            except (ValueError, TypeError, json.JSONDecodeError) as error:
                invalid = str(error)
                invalid_actions += 1
            execution = {"status": "invalid_model_action", "driver_tools": []}
            if action is not None:
                try:
                    execution = await execute(call, target, action)
                except Exception as error:
                    execution = {"status": "driver_error", "driver_tools": [],
                                 "error_type": type(error).__name__, "message": str(error)[-500:]}
            if execution["status"] in {"driver_error", "unsupported_current_driver"}:
                driver_errors += 1
            await asyncio.sleep(0.3)
            state = await page.evaluate("window.gameAPI.getState()")
            evaluation = await evaluator(state, step + 1, {} if evaluation is None else evaluation.metrics)
            trainer_row = {"step": step,
                           "messages": training_messages(system_prompt, history, image_name),
                           "response": text, "observation": image_name,
                           "observation_sha256": digest(image_data), "action": action,
                           "invalid_action": invalid}
            rows.append(trainer_row)
            custody_rows.append({**trainer_row, "execution": execution, "before": before_state,
                                 "after": state, "evaluation": asdict(evaluation),
                                 "usage": {name: int(response_usage.get(name, 0) or 0) for name in usage}})
            history.append(text)
            before_state = state
            if evaluation.should_stop:
                break
        final = await evaluator(state, len(rows), evaluation.metrics, finalized=True)
        final_state = state
    write_once(runtime / "final-state.json", canonical(final_state))
    write_once(runtime / "evaluation.json", canonical(asdict(final)))
    trajectory = b"".join(canonical(row) for row in rows)
    trajectory_name = f"trajectories/{member_id}.jsonl"
    write_once(dataset / trajectory_name, trajectory)
    write_once(runtime / "trajectory.jsonl", b"".join(canonical(row) for row in custody_rows))
    summary = {"steps": len(rows), "success": final.status == "success",
               "progress": float(final.metrics.get("progress", 0) or 0),
               "invalid_actions": invalid_actions, "driver_errors": driver_errors}
    components = reward_components(summary, policy_identity["reward"])
    return {"id": member_id, "trajectory": trajectory_name, "trajectory_sha256": digest(trajectory),
            **summary, "reward_components": components, "reward": components["total"]}, {
                "id": member_id, "initial_state_sha256": digest(canonical(initial)), "usage": usage,
                "seconds": time.monotonic() - started,
            }


async def collect(assignment_path, policy_identity_path, output, driver):
    output = Path(output)
    policy, context = load_policy()
    assignment = validate_assignment(json.loads(Path(assignment_path).read_bytes()), policy, context)
    identity_bytes = Path(policy_identity_path).read_bytes()
    policy_identity = json.loads(identity_bytes)
    if canonical(policy_identity) != identity_bytes:
        raise ValueError("Rollout policy identity must use canonical encoding")
    validate_policy_identity(policy_identity, policy)
    policy_identity_sha256 = digest(identity_bytes)
    policy_identity = {**policy_identity, "reward": policy["model"]["grpo"]}
    if digest(endpoint().encode()) != policy_identity["deployment"]["endpoint_sha256"]:
        raise ValueError("Qwen endpoint differs from the admitted deployment")
    if digest(Path(driver).read_bytes()) != assignment["driver_sha256"]:
        raise ValueError("Rollout driver identity changed")
    models = await asyncio.to_thread(request, endpoint(), "/models", 900)
    if policy_identity["served_model"] not in [item.get("id") for item in models.get("data", [])]:
        raise ValueError("Rollout model is not served by the admitted deployment")
    output.mkdir(parents=True, exist_ok=False)
    dataset, custody = output / "dataset", output / "custody"
    (dataset / "images").mkdir(parents=True)
    (dataset / "trajectories").mkdir()
    custody.mkdir()
    members, metadata = [], []
    for index in range(assignment["members"]):
        member, current = await collect_member(assignment, policy_identity, driver, dataset, custody, index)
        members.append(member)
        metadata.append(current)
    initial_states = {item["initial_state_sha256"] for item in metadata}
    if len(initial_states) != 1:
        raise ValueError("Grouped rollouts did not share the same initial GameWorld state")
    files = {str(path.relative_to(dataset)): digest(path.read_bytes())
             for path in sorted(dataset.rglob("*")) if path.is_file()}
    manifest_policy = {key: policy_identity[key] for key in (
        "base_model", "base_revision", "adapter_sha256", "served_model", "deployment", "generation")}
    manifest = {"schema_version": 1, "purpose": "gameworld-interactive-grpo-v1",
                "catalog_manifest_sha256": context["catalog_manifest_sha256"],
                "policy": manifest_policy, "driver_sha256": assignment["driver_sha256"],
                "reward": policy["model"]["grpo"],
                "groups": [{"id": assignment["group_id"], "game": assignment["game"],
                            "task": assignment["task"], "seed": assignment["seed"],
                            "initial_state_sha256": next(iter(initial_states)), "members": members}],
                "files": files}
    manifest_bytes = canonical(manifest)
    write_once(dataset / "rollouts.json", manifest_bytes)
    dataset_hash = digest(manifest_bytes)
    verified = verify_rollout_dataset(dataset, dataset_hash, policy=policy, context=context,
                                      expected_policy=manifest_policy,
                                      expected_driver_sha256=manifest["driver_sha256"])
    custody_members = []
    for item in metadata:
        member_root = custody / item["id"]
        custody_members.append({**item, "files": {
            str(path.relative_to(member_root)): digest(path.read_bytes())
            for path in sorted(member_root.rglob("*")) if path.is_file()
        }})
    custody_manifest = {"schema_version": 1, "assignment": assignment,
                        "policy_identity_sha256": policy_identity_sha256,
                        "driver_sha256": assignment["driver_sha256"], "members": custody_members}
    write_once(output / "custody-manifest.json", canonical(custody_manifest))
    result = {"status": "complete", "dataset_sha256": dataset_hash,
              "groups": verified["groups"], "trajectories": verified["trajectories"],
              "zero_variance_groups": verified["zero_variance_groups"],
              "usage": {name: sum(item["usage"][name] for item in metadata) for name in ("prompt_tokens", "completion_tokens")},
              "seconds": sum(item["seconds"] for item in metadata),
              "custody_manifest_sha256": digest(canonical(custody_manifest)),
              "created_at": datetime.now(timezone.utc).isoformat()}
    write_once(output / "result.json", canonical(result))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assignment", type=Path, required=True)
    parser.add_argument("--policy-identity", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--driver", default="/usr/local/bin/cua-driver")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(collect(args.assignment, args.policy_identity, args.output, args.driver)), sort_keys=True))


if __name__ == "__main__":
    main()
