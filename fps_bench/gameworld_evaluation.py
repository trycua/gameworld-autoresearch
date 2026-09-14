"""Freeze and verify the all-catalog GameWorld autoresearch evaluation contract."""

import argparse
import json
from pathlib import Path
import re

from fps_bench.evaluation_contract import canonical, digest, exclusive_write, safe_file, split_units, verify
from fps_bench.gameworld_research import DEFAULT_CATALOG, DEFAULT_POLICY, load_baseline, load_policy
from fps_bench.gameworld_suite_episode import DRIVER as BASELINE_DRIVER_SHA256


SOURCE_FILES = (
    "fps_bench/campaign_controller.py",
    "fps_bench/campaign_watchdog.py",
    "fps_bench/driver_candidate.py",
    "fps_bench/evaluation_contract.py",
    "fps_bench/fleet_provider.py",
    "fps_bench/gameworld_coordinator.py",
    "fps_bench/gameworld_evaluation.py",
    "fps_bench/gameworld_candidate_episode.py",
    "fps_bench/gameworld_fleet.py",
    "fps_bench/gameworld_grpo.py",
    "fps_bench/gameworld_modal.py",
    "fps_bench/gameworld_research.py",
    "fps_bench/gameworld_research_worker.py",
    "fps_bench/gameworld_rollout.py",
    "fps_bench/gameworld_runner.py",
    "fps_bench/gameworld_serving.py",
    "fps_bench/gameworld_suite_episode.py",
    "fps_bench/gameworld_training.py",
    "fps_bench/qwen_lora.py",
    "scripts/gameworld_driver_worker.py",
    "scripts/gameworld_model_worker.py",
    "configs/evaluation/gameworld-suite-v1.json",
    "configs/gameworld-autoresearch.json",
)
IMAGE = re.compile(r"^ghcr\.io/trycua/gameworld-autoresearch@sha256:[0-9a-f]{64}$")
RULES = {
    "primary": "macro_task_success_rate",
    "minimum_absolute_improvement": 0.125,
    "familywise_alpha": 0.05,
    "maximum_confirmations": 2,
    "maximum_infrastructure_failures": 0,
    "maximum_invalid_action_rate_increase": 0.05,
    "maximum_median_latency_ratio": 1.5,
    "automatic_retries": 0,
    "sealed_uses": 1,
}


def task_split(context, name, seed):
    return [{**context["assignments"][identity], "seed": seed}
            for identity in context["splits"][name]]


def build_contract(policy, context, baseline, image, source_hashes, seed=42):
    if not IMAGE.fullmatch(image):
        raise ValueError("GameWorld contract requires the immutable public Fleet image digest")
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("GameWorld evaluation seed must be uint32")
    if (not isinstance(source_hashes, dict) or set(source_hashes) != set(SOURCE_FILES)
            or any(not re.fullmatch(r"[0-9a-f]{64}", value) for value in source_hashes.values())):
        raise ValueError("Frozen GameWorld source inventory is incomplete")
    if (baseline.get("catalog_manifest_sha256") != context["catalog_manifest_sha256"]
            or baseline.get("totals", {}).get("assignments") != 170
            or not re.fullmatch(r"[0-9a-f]{64}", baseline.get("baseline_sha256", ""))):
        raise ValueError("Completed all-catalog baseline evidence is required")
    splits = {name: {"tasks": task_split(context, name, seed),
                     "repeats": policy["candidate_policy"]["development_repeats"] if name == "development" else 1}
              for name in ("train", "development", "confirmation", "sealed")}
    private = {"nonce": digest(canonical([baseline["baseline_sha256"], context["policy_sha256"], image])),
               "splits": {name: splits[name] for name in ("confirmation", "sealed")}}
    contract = {
        "spec": {
            "schema_version": 1,
            "suite_id": "gameworld-34x170-cua-qwen-v1",
            "description": "All 34 GameWorld games with task-disjoint train, development, confirmation and sealed splits",
            "assignment_kind": "gameworld-task",
            "catalog_manifest_sha256": context["catalog_manifest_sha256"],
            "policy_sha256": context["policy_sha256"],
            "baseline_sha256": baseline["baseline_sha256"],
            "baseline_driver_sha256": BASELINE_DRIVER_SHA256,
            "provenance": {
                "image": image,
                "gameworld_revision": context["manifest"]["gameworld_revision"],
                "games_revision": context["manifest"]["games_revision"],
            },
            "rules": RULES,
        },
        "episode_template": {
            "protocol": "gameworld-cua-qwen-v1",
            "model": policy["model"]["base_model"],
            "revision": policy["model"]["base_revision"],
            "served_model": "qwen3-vl-2b-instruct-89644892e4d8",
            "seed": seed,
            "max_steps": policy["model"]["maximum_trajectory_steps"],
            "max_tokens": 128,
            "temperature": 0,
            "top_p": 1,
            "delivery_mode": "foreground",
            "response_format": "catalog-semantic-action-json-v1",
            "perception": "desktop-screenshot-plus-four-responses",
        },
        "public_splits": {name: splits[name] for name in ("train", "development")},
        "private_split_commitment": digest(canonical(private)),
        "source_hashes": source_hashes,
    }
    return contract, private


def validate_contract(contract, expected_hash, private_path=None):
    if digest(canonical(contract)) != expected_hash:
        raise ValueError("GameWorld contract differs from its trust anchor")
    spec = contract.get("spec", {})
    if (spec.get("assignment_kind") != "gameworld-task" or spec.get("rules") != RULES
            or not IMAGE.fullmatch(spec.get("provenance", {}).get("image", ""))
            or not re.fullmatch(r"[0-9a-f]{64}", spec.get("baseline_driver_sha256", ""))
            or set(contract.get("public_splits", {})) != {"train", "development"}
            or set(contract.get("source_hashes", {})) != set(SOURCE_FILES)):
        raise ValueError("GameWorld evaluation contract schema changed")
    split_map = dict(contract["public_splits"])
    if private_path is not None:
        private = json.loads(Path(private_path).read_bytes())
        if digest(canonical(private)) != contract.get("private_split_commitment"):
            raise ValueError("GameWorld private split commitment mismatch")
        split_map.update(private["splits"])
    expected_counts = {"train": 68, "development": 34, "confirmation": 34, "sealed": 34}
    if set(split_map) not in ({"train", "development"}, set(expected_counts)):
        raise ValueError("Unexpected GameWorld split inventory")
    seen = set()
    for name, settings in split_map.items():
        axis, units = split_units(settings)
        if axis != "task_id" or len(units) != expected_counts[name] or len({unit["game"] for unit in units}) != 34:
            raise ValueError("GameWorld split lost balanced catalog coverage")
        identities = {unit["task_id"] for unit in units}
        if seen & identities:
            raise ValueError("GameWorld tasks leaked across evaluation splits")
        seen.update(identities)
    if private_path is not None and len(seen) != 170:
        raise ValueError("GameWorld contract does not cover all 170 tasks")
    return contract


def freeze(workspace, baseline_output, custody, image, policy_path=DEFAULT_POLICY,
           catalog_path=DEFAULT_CATALOG, seed=42):
    workspace, custody = Path(workspace).resolve(), Path(custody).resolve()
    if custody.is_relative_to(workspace):
        raise ValueError("GameWorld contract custody must be outside the researcher workspace")
    if custody.exists():
        raise FileExistsError("Refusing to overwrite an existing GameWorld contract")
    policy, context = load_policy(policy_path, catalog_path)
    baseline = load_baseline(baseline_output, catalog_path, context["catalog_manifest_sha256"])
    sources = {name: safe_file(workspace, name).read_bytes() for name in SOURCE_FILES}
    contract, private = build_contract(
        policy, context, baseline, image, {name: digest(data) for name, data in sources.items()}, seed)
    payload = canonical(contract)
    custody.mkdir(parents=True, mode=0o700)
    for name, data in sources.items():
        exclusive_write(custody / "controller-source" / name, data, 0o400)
    exclusive_write(custody / "baseline.json", canonical(baseline), 0o400)
    exclusive_write(custody / "private-splits.json", canonical(private), 0o400)
    exclusive_write(custody / "contract.json", payload, 0o400)
    exclusive_write(custody / "anchor.sha256", (digest(payload) + "\n").encode(), 0o400)
    validate_contract(contract, digest(payload), custody / "private-splits.json")
    return {"contract_sha256": digest(payload), "custody": str(custody),
            "suite_id": contract["spec"]["suite_id"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    create = commands.add_parser("freeze")
    create.add_argument("--workspace", type=Path, required=True)
    create.add_argument("--baseline", type=Path, required=True)
    create.add_argument("--custody", type=Path, required=True)
    create.add_argument("--image", required=True)
    create.add_argument("--seed", type=int, default=42)
    check = commands.add_parser("verify")
    check.add_argument("--contract", type=Path, required=True)
    check.add_argument("--expected-hash", required=True)
    check.add_argument("--private-splits", type=Path)
    check.add_argument("--workspace", type=Path)
    args = parser.parse_args()
    if args.operation == "freeze":
        result = freeze(args.workspace, args.baseline, args.custody, args.image, seed=args.seed)
    else:
        contract = verify(args.contract, args.expected_hash, workspace=args.workspace)
        validate_contract(contract, args.expected_hash, args.private_splits)
        result = {"verified": True, "suite_id": contract["spec"]["suite_id"]}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
