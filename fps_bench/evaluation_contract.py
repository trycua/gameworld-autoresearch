"""Freeze and verify the controller's independent GameWorld evaluation contract."""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import secrets
import statistics


SOURCE_FILES = (
    "fps_bench/__init__.py", "fps_bench/gameworld_baseline.py",
    "fps_bench/gameworld_protocol.py", "fps_bench/qwen_baseline.py",
    "fps_bench/qwen_protocol.py", "fps_bench/evaluation_contract.py",
    "configs/qwen-gameworld-baseline.json", "configs/evaluation/gameworld-2048-v2.json",
)
UPSTREAM_FILES = ("env/task_evaluator.py", "env/browser_scripts/deterministic_random.js",
                  "catalog/tasks/01_2048/01_01.yaml")


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def exclusive_write(path, data, mode=0o600):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def safe_file(root, relative):
    root = Path(root).resolve()
    path = root / relative
    if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError("Unsafe contract path")
    if not path.resolve().is_relative_to(root):
        raise ValueError("Contract path escapes its root")
    current = path
    while current != root:
        if current.is_symlink():
            raise ValueError("Symlinks are not accepted in frozen source trees")
        current = current.parent
    return path


def validate_episode_config(config):
    if not isinstance(config, dict):
        raise ValueError("Expected an episode configuration object")
    if config.get("protocol") != "gameworld-2048-cua-qwen-v2" or config.get("game") != "01_2048" or config.get("task") != "01_01":
        raise ValueError("Only the v2 2048 task is supported")
    if type(config.get("seed")) is not int or not 0 <= config["seed"] < 2**32:
        raise ValueError("Seed must be a uint32")
    for field in ("max_steps", "max_tokens", "timeout_seconds", "request_timeout_seconds", "hold_ms"):
        if type(config.get(field)) is not int or config[field] <= 0:
            raise ValueError(f"{field} must be a positive integer")
    for field in ("temperature", "settle_seconds"):
        if type(config.get(field)) not in (float, int) or not math.isfinite(config[field]) or config[field] < 0:
            raise ValueError(f"Invalid {field}")
    if config.get("delivery_mode") != "foreground" or config.get("response_format") != "json_schema":
        raise ValueError("Unsupported delivery or response format")
    for field in ("model", "revision", "served_model"):
        if not isinstance(config.get(field), str) or not config[field].strip():
            raise ValueError(f"Missing {field}")
    return config


def freeze(workspace, upstream, custody, games):
    workspace, upstream, custody = Path(workspace).resolve(), Path(upstream).resolve(), Path(custody).resolve()
    if custody.is_relative_to(workspace):
        raise ValueError("Custody must be outside the researcher workspace")
    if custody.exists():
        raise FileExistsError("Refusing to overwrite an existing frozen contract")
    spec = json.loads(safe_file(workspace, "configs/evaluation/gameworld-2048-v2.json").read_bytes())
    template = validate_episode_config(json.loads(safe_file(workspace, spec["episode_config"]).read_bytes()))
    template = {key: value for key, value in template.items() if key != "seed"}
    files = {name: safe_file(workspace, name).read_bytes() for name in SOURCE_FILES}
    upstream_files = {name: safe_file(upstream, name).read_bytes() for name in UPSTREAM_FILES}
    game_files = {str(path.relative_to(games)): safe_file(games, str(path.relative_to(games))).read_bytes()
                  for path in sorted((Path(games) / "benchmark/01_2048").rglob("*")) if path.is_file()}
    if not game_files or "benchmark/01_2048/index.html" not in game_files:
        raise ValueError("Missing 2048 game assets")
    used = {spec["known_pilot_seed"]}
    splits = {}
    for name, settings in spec["splits"].items():
        seeds = [spec["known_pilot_seed"]] if name == "train" else []
        while len(seeds) < settings["count"]:
            seed = secrets.randbelow(2**32)
            if seed not in used:
                used.add(seed)
                seeds.append(seed)
        splits[name] = {"seeds": seeds, "repeats": settings["repeats"]}
    private = {"nonce": secrets.token_hex(32), "splits": {
        name: splits[name] for name in ("confirmation", "sealed")}}
    contract = {"spec": spec, "episode_template": template,
                "public_splits": {name: splits[name] for name in ("train", "development")},
                "private_split_commitment": digest(canonical(private)),
                "source_hashes": {name: digest(data) for name, data in files.items()},
                "upstream_hashes": {name: digest(data) for name, data in upstream_files.items()},
                "game_hashes": {name: digest(data) for name, data in game_files.items()}}
    payload = canonical(contract)
    custody.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, data in files.items():
        exclusive_write(custody / "evaluator" / name, data, 0o400)
    for name, data in upstream_files.items():
        exclusive_write(custody / "upstream" / name, data, 0o400)
    for name, data in game_files.items():
        exclusive_write(custody / "games" / name, data, 0o400)
    exclusive_write(custody / "private-splits.json", canonical(private), 0o400)
    exclusive_write(custody / "contract.json", payload, 0o400)
    exclusive_write(custody / "anchor.sha256", (digest(payload) + "\n").encode(), 0o400)
    return {"contract_sha256": digest(payload), "custody": str(custody), "suite_id": spec["suite_id"]}


def verify(contract_path, expected_hash, workspace=None, upstream=None, games=None):
    payload = Path(contract_path).read_bytes()
    if not isinstance(expected_hash, str) or len(expected_hash) != 64 or digest(payload) != expected_hash:
        raise ValueError("Contract does not match the controller trust anchor")
    contract = json.loads(payload)
    for root, field in ((workspace, "source_hashes"), (upstream, "upstream_hashes"), (games, "game_hashes")):
        if root is not None:
            for name, expected in contract[field].items():
                if digest(safe_file(root, name).read_bytes()) != expected:
                    raise ValueError(f"Frozen evaluator mismatch: {name}")
    return contract


def split_for_controller(contract, name, private_path=None):
    if name in contract["public_splits"]:
        return contract["public_splits"][name]
    if name not in ("confirmation", "sealed") or private_path is None:
        raise ValueError("Private split custody is required")
    private = json.loads(Path(private_path).read_bytes())
    if digest(canonical(private)) != contract["private_split_commitment"]:
        raise ValueError("Private split commitment mismatch")
    return private["splits"][name]


def schedule(contract, split, candidates, randomization_seed, private_path=None):
    if not isinstance(candidates, list) or len(candidates) not in (1, 2, 4) or len(set(candidates)) != len(candidates):
        raise ValueError("Provide one baseline, two paired, or four factorial candidate IDs")
    if any(not isinstance(name, str) or not name for name in candidates):
        raise ValueError("Candidate IDs must be nonempty")
    settings = split_for_controller(contract, split, private_path)
    generator = random.Random(randomization_seed)
    seeds = list(settings["seeds"])
    generator.shuffle(seeds)
    runs = []
    for repeat in range(settings["repeats"]):
        for seed in seeds:
            order = list(candidates)
            generator.shuffle(order)
            for candidate in order:
                runs.append({"candidate": candidate, "split": split, "seed": seed, "repeat": repeat,
                             "episode_id": digest(canonical([contract["spec"]["suite_id"], split,
                                                            candidate, seed, repeat]))[:24]})
    return runs


def paired_decision(contract, split, rows, baseline, candidate, private_path=None):
    if baseline == candidate:
        raise ValueError("Baseline and candidate must differ")
    if split not in ("development", "confirmation"):
        raise ValueError("Training and sealed results cannot select a candidate")
    settings = split_for_controller(contract, split, private_path)
    expected = {(seed, repeat, name) for seed in settings["seeds"]
                for repeat in range(settings["repeats"]) for name in (baseline, candidate)}
    records = {}
    for row in rows:
        if row.get("contract_sha256") != digest(canonical(contract)):
            raise ValueError("Episode belongs to another evaluation contract")
        key = (row["seed"], row["repeat"], row["candidate"])
        if row.get("split") != split or key not in expected or key in records:
            raise ValueError("Unexpected, cross-split or duplicate episode")
        records[key] = row
    if set(records) != expected:
        return {"decision": "incomplete", "missing_episodes": len(expected - set(records))}
    failures = [row for row in rows if row.get("status") != "complete"]
    if failures:
        return {"decision": "infrastructure_failure", "failed_episodes": len(failures),
                "success_rate": None}
    for row in rows:
        if type(row.get("success")) is not bool:
            raise ValueError("Completed episodes need a boolean outcome")
        if type(row.get("steps")) is not int or not 1 <= row["steps"] <= contract["episode_template"]["max_steps"]:
            raise ValueError("Invalid step count")
        if type(row.get("invalid_actions")) is not int or not 0 <= row["invalid_actions"] <= row["steps"]:
            raise ValueError("Invalid action count")
        if type(row.get("seconds")) not in (int, float) or not math.isfinite(row["seconds"]) or row["seconds"] <= 0:
            raise ValueError("Invalid episode duration")
    groups = {name: [row for row in rows if row["candidate"] == name] for name in (baseline, candidate)}
    rates = {name: statistics.mean(row["success"] for row in group) for name, group in groups.items()}
    delta = rates[candidate] - rates[baseline]
    seed_deltas = [statistics.mean(
        int(records[(seed, repeat, candidate)]["success"]) - int(records[(seed, repeat, baseline)]["success"])
        for repeat in range(settings["repeats"])) for seed in settings["seeds"]]
    positive, negative = sum(value > 0 for value in seed_deltas), sum(value < 0 for value in seed_deltas)
    discordant = positive + negative
    probability = sum(math.comb(discordant, index) for index in range(positive, discordant + 1)) / 2**discordant
    rules = contract["spec"]["rules"]
    invalid = {name: sum(row["invalid_actions"] for row in group) / sum(row["steps"] for row in group)
               for name, group in groups.items()}
    latency_ratio = statistics.median(row["seconds"] for row in groups[candidate]) / statistics.median(
        row["seconds"] for row in groups[baseline])
    margin = math.sqrt(2 * math.log(2 / rules["familywise_alpha"]) / len(seed_deltas))
    result = {"paired_difference_hoeffding_interval": [max(-1, delta - margin), min(1, delta + margin)],
              "baseline_success_rate": rates[baseline], "candidate_success_rate": rates[candidate],
              "absolute_improvement": delta, "independent_seeds": len(settings["seeds"]),
              "episodes_per_candidate": len(groups[baseline]), "positive_seeds": positive,
              "negative_seeds": negative, "one_sided_sign_p": probability,
              "invalid_action_rate_increase": invalid[candidate] - invalid[baseline],
              "median_latency_ratio": latency_ratio}
    if (result["invalid_action_rate_increase"] > rules["maximum_invalid_action_rate_increase"]
            or latency_ratio > rules["maximum_median_latency_ratio"]):
        result["decision"] = "regression"
    elif delta < rules["minimum_absolute_improvement"]:
        result["decision"] = "no_improvement"
    elif split == "development":
        result["decision"] = "nominate"
    elif probability <= rules["familywise_alpha"] / rules["maximum_confirmations"]:
        result["decision"] = "confirmation_pass"
    else:
        result["decision"] = "inconclusive"
    return result



def write_development_plan(contract_path, expected_hash, output, candidates, randomization_seed):
    contract = verify(contract_path, expected_hash)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    runs = schedule(contract, "development", candidates, randomization_seed)
    for run in runs:
        run["contract_sha256"] = expected_hash
        run["config_file"] = run["episode_id"] + ".json"
        configuration = {**contract["episode_template"], "seed": run["seed"]}
        exclusive_write(output / run["config_file"], canonical(configuration))
    plan = {"contract_sha256": expected_hash, "split": "development", "runs": runs,
            "randomization_seed": randomization_seed, "execution_status": "not_started",
            "note": "Assignments only; provider admission and candidate identities required before dispatch"}
    exclusive_write(output / "plan.json", canonical(plan))
    return {"plan_sha256": digest(canonical(plan)), "episodes": len(runs), "output": str(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    create = commands.add_parser("freeze")
    for name in ("workspace", "upstream", "custody", "games"):
        create.add_argument(f"--{name}", type=Path, required=True)
    check = commands.add_parser("verify")
    check.add_argument("--contract", type=Path, required=True)
    check.add_argument("--expected-hash", required=True)
    check.add_argument("--workspace", type=Path)
    check.add_argument("--upstream", type=Path)
    check.add_argument("--games", type=Path)
    planning = commands.add_parser("plan-development")
    planning.add_argument("--contract", type=Path, required=True)
    planning.add_argument("--expected-hash", required=True)
    planning.add_argument("--output", type=Path, required=True)
    planning.add_argument("--candidates", nargs="+", default=["baseline"])
    planning.add_argument("--randomization-seed", type=int, default=20260913)
    args = parser.parse_args()
    if args.operation == "plan-development":
        result = write_development_plan(args.contract, args.expected_hash, args.output,
                                        args.candidates, args.randomization_seed)
    elif args.operation == "freeze":
        result = freeze(args.workspace, args.upstream, args.custody, args.games)
    else:
        contract = verify(args.contract, args.expected_hash, args.workspace, args.upstream, args.games)
        result = {"verified": True, "suite_id": contract["spec"]["suite_id"]}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
