"""Trusted OODA state for joint GameWorld driver and model autoresearch."""

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import time
from urllib.parse import urlsplit

from fps_bench.campaign_ledger import BudgetRefused, CampaignLedger, LedgerConflict, LIMITS
from fps_bench.evaluation_contract import canonical, digest
from fps_bench.gameworld_suite_catalog import load as load_catalog
from fps_bench.telemetry import ResearchTelemetry


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "configs/gameworld-autoresearch.json"
DEFAULT_CATALOG = ROOT / "configs/evaluation/gameworld-suite-v1.json"
TRACKS = ("driver", "model")
SIGNALS = {
    "success", "task_failure", "low_progress", "invalid_model_action",
    "unsupported_current_driver", "driver_error", "episode_error", "game_init_failure",
}
CONTRACT_TESTS = {"build", "focus", "held-keys", "key-release", "mouse-delivery"}
IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
REVISION = re.compile(r"^[0-9a-f]{40}$")
TASK_ID = re.compile(r"^[0-9]{2}_[a-z0-9-]+--[0-9]{2}_[0-9]{2}$")


def _regular_file(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"Expected a regular immutable file: {path}")
    return path


def _json(path):
    return json.loads(_regular_file(path).read_bytes())


def _task_ordinal(task):
    return int(task.rsplit("_", 1)[1])


def catalog_assignments(manifest):
    return {
        f"{game['game']}--{task['task']}": {
            "id": f"{game['game']}--{task['task']}",
            "game": game["game"],
            "task": task["task"],
        }
        for game in manifest["games"]
        for task in game["tasks"]
    }


def load_policy(path=DEFAULT_POLICY, catalog_path=DEFAULT_CATALOG):
    policy = _json(path)
    required = {
        "schema_version", "id", "catalog_manifest_sha256", "baseline_phase",
        "split_policy", "candidate_policy", "driver", "model", "limits",
    }
    if not isinstance(policy, dict) or set(policy) != required:
        raise ValueError("Unexpected GameWorld autoresearch policy fields")
    manifest, summary = load_catalog(catalog_path)
    if (policy["schema_version"] != 1 or not IDENTIFIER.fullmatch(policy["id"])
            or policy["catalog_manifest_sha256"] != summary["manifest_sha256"]
            or policy["baseline_phase"] != "suite-baseline-v1"):
        raise ValueError("GameWorld autoresearch policy identity changed")
    split_policy = policy["split_policy"]
    if set(split_policy) != {
        "train_task_ordinals", "development_task_ordinals",
        "confirmation_task_ordinals", "sealed_task_ordinals",
    }:
        raise ValueError("Unexpected GameWorld split policy")
    assigned_ordinals = []
    for value in split_policy.values():
        if (not isinstance(value, list) or not value
                or any(type(item) is not int or not 1 <= item <= 5 for item in value)):
            raise ValueError("Each GameWorld split requires task ordinals 1..5")
        assigned_ordinals.extend(value)
    if sorted(assigned_ordinals) != [1, 2, 3, 4, 5]:
        raise ValueError("GameWorld task ordinals must belong to exactly one split")
    candidate = policy["candidate_policy"]
    if candidate != {
        "maximum_candidates": 10,
        "required_isolated_tracks": ["driver", "model"],
        "joint_comparison": "two-by-two-factorial",
        "development_repeats": 2,
    }:
        raise ValueError("Candidate policy differs from the approved pilot")
    driver = policy["driver"]
    if (set(driver) != {"allowed_source_prefixes", "required_contract_tests"}
            or not driver["allowed_source_prefixes"]
            or set(driver["required_contract_tests"]) != CONTRACT_TESTS):
        raise ValueError("Driver policy is incomplete")
    if any(not value.startswith("cua-driver/rust/crates/") or not value.endswith("/")
           for value in driver["allowed_source_prefixes"]):
        raise ValueError("Driver source scope escaped the vendored Rust tree")
    model = policy["model"]
    if (set(model) != {"base_model", "base_revision", "objectives", "minimum_grpo_group_size",
                       "maximum_grpo_group_size", "maximum_trajectory_steps", "maximum_optimizer_steps", "grpo"}
            or model["base_model"] != "Qwen/Qwen3-VL-2B-Instruct"
            or not REVISION.fullmatch(model["base_revision"])
            or model["objectives"] != ["sft", "grpo"]
            or not 2 <= model["minimum_grpo_group_size"] <= model["maximum_grpo_group_size"] <= 8
            or not 1 <= model["maximum_trajectory_steps"] <= 60
            or not 1 <= model["maximum_optimizer_steps"] <= 32):
        raise ValueError("Model policy differs from the pinned Qwen pilot")
    if model["grpo"] != {
        "reward_version": "gameworld-progress-v1",
        "terminal_success_weight": 1.0,
        "progress_weight": 0.25,
        "invalid_action_penalty": 0.1,
        "driver_error_penalty": 0.1,
        "clip_epsilon": 0.2,
        "reference_kl_beta": 0.01,
    }:
        raise ValueError("GRPO reward or optimization policy changed")
    limits = policy["limits"]
    expected_limits = {
        "modal_micro_usd_total": LIMITS["modal_micro_usd"][0],
        "modal_micro_usd_normal": LIMITS["modal_micro_usd"][1],
        "desktop_concurrency": 2,
        "training_concurrency": 1,
        "baseline_serving_micro_usd": 15_000_000,
        "minimum_serving_micro_usd": 15_000_000,
        "serving_seconds": 10800,
        "campaign_seconds": 21600,
    }
    if limits != expected_limits:
        raise ValueError("Autoresearch limits differ from the campaign ledger")
    splits = {name.removesuffix("_task_ordinals"): [] for name in split_policy}
    ordinal_split = {
        ordinal: name.removesuffix("_task_ordinals")
        for name, ordinals in split_policy.items()
        for ordinal in ordinals
    }
    for assignment in catalog_assignments(manifest).values():
        splits[ordinal_split[_task_ordinal(assignment["task"])]].append(assignment["id"])
    if {name: len(values) for name, values in splits.items()} != {
        "train": 68, "development": 34, "confirmation": 34, "sealed": 34,
    }:
        raise ValueError("Game-balanced task split is incomplete")
    return policy, {
        "policy_sha256": digest(canonical(policy)),
        "catalog_manifest_sha256": summary["manifest_sha256"],
        "manifest": manifest,
        "assignments": catalog_assignments(manifest),
        "splits": splits,
    }


def _summary_observation(identity, payload):
    summary = payload.get("summary")
    required = {
        "status", "success", "steps", "invalid_actions", "execution_status",
        "progress", "usage", "seconds", "evaluation",
    }
    if (not isinstance(summary, dict) or set(summary) != required
            or summary["status"] != "complete" or type(summary["success"]) is not bool
            or summary["steps"] != 1 or type(summary["invalid_actions"]) is not int
            or summary["invalid_actions"] < 0 or not isinstance(summary["execution_status"], str)
            or type(summary["progress"]) not in (int, float)
            or not math.isfinite(summary["progress"]) or not 0 <= summary["progress"] <= 1
            or not isinstance(summary["evaluation"], dict)
            or type(summary["seconds"]) not in (int, float) or not math.isfinite(summary["seconds"])
            or summary["seconds"] < 0 or not isinstance(summary["usage"], dict)
            or set(summary["usage"]) != {"prompt_tokens", "completion_tokens"}
            or any(type(value) is not int or value < 0 for value in summary["usage"].values())):
        raise ValueError(f"Invalid compatibility receipt summary: {identity}")
    signals = ["success"] if summary["success"] else ["task_failure"]
    if not summary["success"] and summary["progress"] < 1:
        signals.append("low_progress")
    if summary["invalid_actions"] or summary["execution_status"] == "invalid_model_action":
        signals.append("invalid_model_action")
    if summary["execution_status"] in {"unsupported_current_driver", "driver_error"}:
        signals.append(summary["execution_status"])
    return {
        "id": identity,
        "game": payload["game"],
        "task": payload["task"],
        "result": "receipt",
        "success": summary["success"],
        "progress": float(summary["progress"]),
        "invalid_actions": summary["invalid_actions"],
        "execution_status": summary["execution_status"],
        "signals": sorted(set(signals)),
    }


def load_baseline(output, catalog_path=DEFAULT_CATALOG, expected_manifest_hash=None):
    output = Path(output)
    manifest, catalog = load_catalog(catalog_path)
    expected_manifest_hash = expected_manifest_hash or catalog["manifest_sha256"]
    if catalog["manifest_sha256"] != expected_manifest_hash:
        raise ValueError("Baseline catalog hash differs from the supervisor policy")
    intent = _json(output / "intent.json")
    report_path = _regular_file(output / "report.json")
    report_bytes = report_path.read_bytes()
    report = json.loads(report_bytes)
    verification = _json(output / "completion-verification.json")
    if (intent.get("catalog_manifest_sha256") != expected_manifest_hash
            or intent.get("phase") != "all-catalog-one-step-compatibility-baseline"
            or report.get("assignments") != 170 or report.get("pending") != 0
            or report.get("completed", 0) + report.get("failed", 0) != 170
            or verification.get("status") != "complete"
            or verification.get("catalog") != {"games": 34, "assignments": 170}
            or verification.get("results", {}).get("report_sha256") != digest(report_bytes)):
        raise ValueError("Incomplete or mismatched GameWorld compatibility baseline")
    assignments = catalog_assignments(manifest)
    episode_root = output / "episodes"
    if (not episode_root.is_dir() or episode_root.is_symlink()
            or {path.name for path in episode_root.iterdir() if path.is_dir()} != set(assignments)):
        raise ValueError("Baseline episode inventory differs from the catalog")
    observations = []
    for identity, assignment in sorted(assignments.items()):
        root = episode_root / identity
        receipt_path, error_path = root / "receipt.json", root / "error.json"
        if receipt_path.is_file() == error_path.is_file():
            raise ValueError(f"Expected exactly one terminal record: {identity}")
        payload = _json(receipt_path if receipt_path.is_file() else error_path)
        if any(payload.get(key) != assignment[key] for key in ("id", "game", "task")):
            raise ValueError(f"Baseline task identity changed: {identity}")
        archive = _regular_file(root / "artifacts.tar.gz")
        if payload.get("archive_sha256") != digest(archive.read_bytes()):
            raise ValueError(f"Baseline archive hash changed: {identity}")
        if receipt_path.is_file():
            observations.append(_summary_observation(identity, payload))
        else:
            if type(payload.get("returncode")) is not int or payload["returncode"] == 0:
                raise ValueError(f"Invalid failed episode record: {identity}")
            stderr = payload.get("stderr", "")
            signals = ["episode_error"]
            if isinstance(stderr, str) and "GameWorld init failed" in stderr:
                signals.append("game_init_failure")
            observations.append({
                "id": identity, "game": payload["game"], "task": payload["task"],
                "result": "error", "success": False, "progress": 0.0,
                "invalid_actions": 0, "execution_status": "episode_error",
                "signals": sorted(signals),
            })
    totals = {
        "assignments": len(observations),
        "receipts": sum(item["result"] == "receipt" for item in observations),
        "errors": sum(item["result"] == "error" for item in observations),
        "successes": sum(item["success"] for item in observations),
        "invalid_actions": sum(item["invalid_actions"] for item in observations),
        "mean_progress": sum(item["progress"] for item in observations) / len(observations),
        "signals": {signal: sum(signal in item["signals"] for item in observations) for signal in sorted(SIGNALS)},
    }
    result = {
        "schema_version": 1,
        "catalog_manifest_sha256": expected_manifest_hash,
        "intent_sha256": digest(canonical(intent)),
        "report_sha256": digest(report_bytes),
        "observations": observations,
        "totals": totals,
    }
    result["baseline_sha256"] = digest(canonical(result))
    return result


def _https_reference(reference):
    if not isinstance(reference, dict) or set(reference) != {"url", "retrieved_at", "note"}:
        raise ValueError("Research references require url, retrieved_at and note")
    parsed = urlsplit(reference["url"])
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Research references require credential-free HTTPS URLs")
    try:
        retrieved = datetime.fromisoformat(reference["retrieved_at"].replace("Z", "+00:00"))
    except (AttributeError, ValueError) as error:
        raise ValueError("Research reference timestamp is invalid") from error
    if retrieved.tzinfo is None or retrieved.timestamp() > time.time() + 300:
        raise ValueError("Research reference timestamp must be timezone-aware and nonfuture")
    if not isinstance(reference["note"], str) or not reference["note"].strip() or len(reference["note"]) > 2000:
        raise ValueError("Research reference evidence note is required")


def validate_proposal(proposal, policy, context, baseline):
    required = {"id", "track", "hypothesis", "evidence", "references", "experiment", "budget"}
    if not isinstance(proposal, dict) or set(proposal) != required:
        raise ValueError("Unexpected autoresearch proposal fields")
    if not IDENTIFIER.fullmatch(proposal["id"]) or proposal["track"] not in TRACKS:
        raise ValueError("Invalid proposal identity or track")
    if (not isinstance(proposal["hypothesis"], str) or not proposal["hypothesis"].strip()
            or len(proposal["hypothesis"]) > 4000):
        raise ValueError("A bounded falsifiable hypothesis is required")
    if not isinstance(proposal["evidence"], list) or not 1 <= len(proposal["evidence"]) <= 20:
        raise ValueError("Proposal requires bounded baseline evidence")
    observations = {item["id"]: item for item in baseline["observations"]}
    evidence_keys = set()
    for evidence in proposal["evidence"]:
        if (not isinstance(evidence, dict) or set(evidence) != {"task_id", "signal"}
                or evidence["task_id"] not in observations or evidence["signal"] not in SIGNALS
                or evidence["signal"] not in observations[evidence["task_id"]]["signals"]):
            raise ValueError("Proposal cites unobserved baseline evidence")
        evidence_keys.add((evidence["task_id"], evidence["signal"]))
    if len(evidence_keys) != len(proposal["evidence"]):
        raise ValueError("Proposal repeats baseline evidence")
    if not isinstance(proposal["references"], list) or not 1 <= len(proposal["references"]) <= 8:
        raise ValueError("Proposal requires bounded primary-source research")
    for reference in proposal["references"]:
        _https_reference(reference)
    if len({reference["url"] for reference in proposal["references"]}) != len(proposal["references"]):
        raise ValueError("Proposal repeats a research source")
    budget = proposal["budget"]
    if (not isinstance(budget, dict)
            or set(budget) != {"modal_micro_usd", "modal_training_micro_usd",
                               "modal_serving_micro_usd",
                               "desktop_episodes", "timeout_seconds"}
            or any(type(value) is not int or value < 0 for value in budget.values())
            or not 1 <= budget["desktop_episodes"] <= 136
            or not 60 <= budget["timeout_seconds"] <= 1800
            or budget["modal_micro_usd"] > policy["limits"]["modal_micro_usd_normal"]):
        raise ValueError("Proposal budget is outside campaign bounds")
    experiment = proposal["experiment"]
    development = set(context["splits"]["development"])
    if proposal["track"] == "driver":
        if (not isinstance(experiment, dict)
                or set(experiment) != {"kind", "target_paths", "contract_tests", "evaluation_tasks"}
                or experiment["kind"] != "driver"
                or any(budget[name] != 0 for name in (
                    "modal_micro_usd", "modal_training_micro_usd", "modal_serving_micro_usd"))):
            raise ValueError("Driver proposal changed the model budget or schema")
        paths = experiment["target_paths"]
        if not isinstance(paths, list) or not 1 <= len(paths) <= 8 or len(paths) != len(set(paths)):
            raise ValueError("Driver proposal requires unique target paths")
        prefixes = tuple(policy["driver"]["allowed_source_prefixes"])
        if any(not isinstance(path, str) or path.startswith("/") or ".." in Path(path).parts
               or not path.startswith(prefixes) for path in paths):
            raise ValueError("Driver proposal escaped the allowlisted source tree")
        tests = experiment["contract_tests"]
        if not isinstance(tests, list) or set(tests) != CONTRACT_TESTS:
            raise ValueError("Driver proposal must retain every input contract test")
    else:
        expected = {"kind", "objective", "training_tasks", "evaluation_tasks", "rollouts_per_task",
                    "max_trajectory_steps", "optimizer_steps", "sft_source_id"}
        if not isinstance(experiment, dict) or set(experiment) != expected or experiment["kind"] != "model":
            raise ValueError("Unexpected model experiment schema")
        if (experiment["objective"] not in policy["model"]["objectives"]
                or budget["modal_training_micro_usd"] <= 0
                or budget["modal_serving_micro_usd"] < policy["limits"]["minimum_serving_micro_usd"]
                or budget["modal_micro_usd"] != (
                    budget["modal_training_micro_usd"] + budget["modal_serving_micro_usd"])):
            raise ValueError("Model objective requires a bounded Modal reservation")
        training = experiment["training_tasks"]
        if (not isinstance(training, list) or not training or len(training) != len(set(training))
                or not set(training) <= set(context["splits"]["train"])):
            raise ValueError("Model training may use only registered train tasks")
        group = experiment["rollouts_per_task"]
        minimum = 1 if experiment["objective"] == "sft" else policy["model"]["minimum_grpo_group_size"]
        maximum = 1 if experiment["objective"] == "sft" else policy["model"]["maximum_grpo_group_size"]
        if type(group) is not int or not minimum <= group <= maximum:
            raise ValueError("Rollout group size differs from the selected objective")
        source_id = experiment["sft_source_id"]
        if ((experiment["objective"] == "sft" and not isinstance(source_id, str))
                or (isinstance(source_id, str) and not IDENTIFIER.fullmatch(source_id))
                or (experiment["objective"] == "grpo" and source_id is not None)):
            raise ValueError("SFT source identity differs from the selected objective")
        if (type(experiment["max_trajectory_steps"]) is not int
                or not 1 <= experiment["max_trajectory_steps"] <= policy["model"]["maximum_trajectory_steps"]
                or type(experiment["optimizer_steps"]) is not int
                or not 1 <= experiment["optimizer_steps"] <= policy["model"]["maximum_optimizer_steps"]):
            raise ValueError("Model trajectory or optimizer steps exceed pilot bounds")
    evaluation = experiment["evaluation_tasks"]
    if (not isinstance(evaluation, list) or len(evaluation) != len(set(evaluation))
            or set(evaluation) != development
            or budget["desktop_episodes"] != len(evaluation) * policy["candidate_policy"]["development_repeats"]):
        raise ValueError("Candidate evaluation must cover the full game-balanced development split")
    return proposal


class GameWorldResearchSupervisor:
    def __init__(self, database, baseline_output, policy_path=DEFAULT_POLICY, catalog_path=DEFAULT_CATALOG,
                 telemetry_path=None):
        self.ledger = CampaignLedger(database)
        self.policy, self.context = load_policy(policy_path, catalog_path)
        self.baseline = load_baseline(baseline_output, catalog_path, self.context["catalog_manifest_sha256"])
        self.telemetry_path = telemetry_path
        self.telemetry = None

    @staticmethod
    def _migrate_actions(connection):
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(gameworld_actions)")}
        additions = {
            "deadline": "INTEGER NOT NULL DEFAULT 0",
            "reservations": "TEXT NOT NULL DEFAULT '{}'",
            "provider_id": "TEXT",
            "cleanup_receipt": "TEXT",
        }
        for name, definition in additions.items():
            if name not in columns:
                connection.execute(f"ALTER TABLE gameworld_actions ADD COLUMN {name} {definition}")
        now = int(time.time())
        connection.execute("UPDATE gameworld_actions SET deadline=? WHERE deadline=0", (now,))
        connection.execute("UPDATE gameworld_actions SET state='dispatching' WHERE state='running' AND provider_id IS NULL")
        connection.execute("UPDATE gameworld_actions SET state='cleanup_pending' WHERE state='complete'")

    def _ensure_telemetry(self):
        if self.telemetry is None and self.telemetry_path is not None:
            campaign = self.ledger.snapshot()["campaign"]["id"]
            self.telemetry = ResearchTelemetry(self.telemetry_path, campaign)

    def initialize(self, campaign):
        self.ledger.initialize(campaign)
        self.ledger.remove_token_budget()
        with self.ledger.transaction() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS gameworld_research ("
                "singleton INTEGER PRIMARY KEY CHECK(singleton=1), policy_sha256 TEXT NOT NULL, "
                "baseline_sha256 TEXT NOT NULL, created INTEGER NOT NULL, deadline INTEGER NOT NULL, state TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS gameworld_hypotheses ("
                "id TEXT PRIMARY KEY, round INTEGER NOT NULL UNIQUE, track TEXT NOT NULL, manifest TEXT NOT NULL, "
                "manifest_sha256 TEXT NOT NULL UNIQUE, state TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS gameworld_actions ("
                "id TEXT PRIMARY KEY, hypothesis TEXT NOT NULL REFERENCES gameworld_hypotheses(id), "
                "kind TEXT NOT NULL, deadline INTEGER NOT NULL, reservations TEXT NOT NULL, state TEXT NOT NULL, "
                "provider_id TEXT, result TEXT, cleanup_receipt TEXT)"
            )
            self._migrate_actions(connection)
            current = connection.execute("SELECT * FROM gameworld_research").fetchone()
            if current:
                if (current["policy_sha256"] != self.context["policy_sha256"]
                        or current["baseline_sha256"] != self.baseline["baseline_sha256"]):
                    raise LedgerConflict("GameWorld supervisor identity changed")
            else:
                now = int(time.time())
                connection.execute(
                    "INSERT INTO gameworld_research VALUES (1,?,?,?,?,?)",
                    (self.context["policy_sha256"], self.baseline["baseline_sha256"], now,
                     now + self.policy["limits"]["campaign_seconds"], "running"),
                )
                self.ledger._event(connection, "gameworld_research_initialized", {
                    "policy_sha256": self.context["policy_sha256"],
                    "baseline_sha256": self.baseline["baseline_sha256"],
                    "catalog_manifest_sha256": self.context["catalog_manifest_sha256"],
                })
        self._ensure_telemetry()

    def _emit(self, event_id, values, outcome):
        if self.telemetry_path is None:
            return None
        try:
            self._ensure_telemetry()
            self.telemetry.record(event_id, "gameworld-research",
                                  {"experiment": "joint-supervisor", "phase": "research", "task": "all",
                                   "change_class": "joint", "outcome": outcome}, values)
            return self.telemetry.flush()
        except Exception as error:
            return {"metrics": False, "logs": False, "errors": [{"type": type(error).__name__}]}

    def _settings(self, connection, admission=False):
        row = connection.execute("SELECT * FROM gameworld_research").fetchone()
        if row is None:
            raise LedgerConflict("GameWorld supervisor is not initialized")
        if admission:
            campaign = connection.execute("SELECT * FROM campaign").fetchone()
            if row["state"] != "running" or campaign["frozen"] or int(time.time()) >= row["deadline"]:
                raise BudgetRefused("GameWorld supervisor is stopped, frozen or expired")
        return row

    def register(self, proposal):
        proposal = validate_proposal(proposal, self.policy, self.context, self.baseline)
        payload = canonical(proposal).decode()
        payload_hash = digest(payload.encode())
        with self.ledger.transaction() as connection:
            self._settings(connection, admission=True)
            existing = connection.execute("SELECT * FROM gameworld_hypotheses WHERE id=?", (proposal["id"],)).fetchone()
            if existing:
                if existing["manifest"] != payload:
                    raise LedgerConflict("Hypothesis identity reused with different content")
                return dict(existing)
            maximum = self.policy["candidate_policy"]["maximum_candidates"]
            if connection.execute("SELECT COUNT(*) FROM gameworld_hypotheses").fetchone()[0] >= maximum:
                raise BudgetRefused("GameWorld candidate limit reached")
            round_id = connection.execute("SELECT COALESCE(MAX(round),0)+1 FROM gameworld_hypotheses").fetchone()[0]
            connection.execute(
                "INSERT INTO gameworld_hypotheses VALUES (?,?,?,?,?,'queued')",
                (proposal["id"], round_id, proposal["track"], payload, payload_hash),
            )
            self.ledger._event(connection, "gameworld_hypothesis_registered", {
                "id": proposal["id"], "round": round_id, "track": proposal["track"],
                "manifest_sha256": payload_hash,
            })
            result = dict(connection.execute("SELECT * FROM gameworld_hypotheses WHERE id=?", (proposal["id"],)).fetchone())
        self._emit(f"research-round-{round_id}", {"gameworld_research_round": round_id}, "queued")
        return result

    @staticmethod
    def _next_row(connection):
        rows = connection.execute(
            "SELECT * FROM gameworld_hypotheses WHERE state='queued' ORDER BY round"
        ).fetchall()
        if not rows:
            return None
        attempted = {
            track: connection.execute(
                "SELECT COUNT(*) FROM gameworld_hypotheses WHERE track=? AND state!='queued'", (track,)
            ).fetchone()[0]
            for track in TRACKS
        }
        minimum = min(attempted.values())
        preferred = {track for track, count in attempted.items() if count == minimum}
        return next((row for row in rows if row["track"] in preferred), rows[0])

    def next(self):
        with self.ledger.transaction() as connection:
            self._settings(connection, admission=True)
            row = self._next_row(connection)
            return None if row is None else json.loads(row["manifest"])

    def begin(self, hypothesis, action_id):
        if not IDENTIFIER.fullmatch(action_id):
            raise ValueError("Invalid GameWorld action identity")
        with self.ledger.transaction() as connection:
            self._settings(connection, admission=True)
            existing = connection.execute("SELECT * FROM gameworld_actions WHERE id=?", (action_id,)).fetchone()
            if existing:
                if existing["hypothesis"] != hypothesis:
                    raise LedgerConflict("Action identity reused for another hypothesis")
                return dict(existing)
            selected = self._next_row(connection)
            if selected is None or selected["id"] != hypothesis:
                raise LedgerConflict("Only the supervisor-selected hypothesis may start")
            kind = "driver_build" if selected["track"] == "driver" else "training"
            settings = self._settings(connection)
            deadline = settings["deadline"]
            reservations = {}
            connection.execute("INSERT INTO gameworld_actions VALUES (?,?,?,?,?,'dispatching',NULL,NULL,NULL)",
                               (action_id, hypothesis, kind, deadline, canonical(reservations).decode()))
            connection.execute("UPDATE gameworld_hypotheses SET state='running' WHERE id=?", (hypothesis,))
            self.ledger._event(connection, "gameworld_action_started", {
                "id": action_id, "hypothesis": hypothesis, "kind": kind,
            })
            return dict(connection.execute("SELECT * FROM gameworld_actions WHERE id=?", (action_id,)).fetchone())

    def provider_started(self, action_id, provider_id):
        if not isinstance(provider_id, str) or not provider_id.strip() or len(provider_id) > 256:
            raise ValueError("Bounded provider identity required")
        with self.ledger.transaction() as connection:
            self._settings(connection)
            action = connection.execute("SELECT * FROM gameworld_actions WHERE id=?", (action_id,)).fetchone()
            if action is None:
                raise LedgerConflict("Unknown GameWorld action")
            if action["state"] == "running" and action["provider_id"] == provider_id:
                return
            if action["state"] != "dispatching" or action["provider_id"] is not None:
                raise LedgerConflict("Provider acknowledgement differs from action state")
            connection.execute("UPDATE gameworld_actions SET state='running',provider_id=? WHERE id=?",
                               (provider_id, action_id))
            self.ledger._event(connection, "gameworld_provider_started", {
                "id": action_id, "provider_id": provider_id,
            })

    def finish(self, action_id, result):
        required = {"candidate_id", "qualified", "artifact_sha256", "metrics"}
        if (not isinstance(result, dict) or set(result) != required
                or not IDENTIFIER.fullmatch(result["candidate_id"])
                or type(result["qualified"]) is not bool
                or not SHA256.fullmatch(result["artifact_sha256"])
                or not isinstance(result["metrics"], dict)):
            raise ValueError("Invalid GameWorld action result")
        payload = canonical(result).decode()
        with self.ledger.transaction() as connection:
            self._settings(connection)
            action = connection.execute("SELECT * FROM gameworld_actions WHERE id=?", (action_id,)).fetchone()
            if action is None:
                raise LedgerConflict("Unknown GameWorld action")
            if action["state"] in ("cleanup_pending", "cleaned"):
                if action["result"] != payload:
                    raise LedgerConflict("Action result is immutable")
                return
            if action["state"] != "running":
                raise LedgerConflict("Only a running action can finish")
            connection.execute("UPDATE gameworld_actions SET state='cleanup_pending',result=? WHERE id=?",
                               (payload, action_id))
            self.ledger._event(connection, "gameworld_action_finished", {
                "id": action_id, "hypothesis": action["hypothesis"], "candidate": result["candidate_id"],
                "qualified": result["qualified"], "artifact_sha256": result["artifact_sha256"],
            })

    def cleanup_confirmed(self, action_id, receipt):
        if not isinstance(receipt, str) or not receipt.strip() or len(receipt) > 1000:
            raise ValueError("Bounded cleanup receipt required")
        with self.ledger.transaction() as connection:
            self._settings(connection)
            action = connection.execute("SELECT * FROM gameworld_actions WHERE id=?", (action_id,)).fetchone()
            if action is None:
                raise LedgerConflict("Unknown GameWorld action")
            if action["state"] == "cleaned":
                if action["cleanup_receipt"] != receipt:
                    raise LedgerConflict("Cleanup receipt is immutable")
                return
            if action["state"] != "cleanup_pending" or action["result"] is None:
                raise LedgerConflict("Only a completed provider action can be cleaned")
            result = json.loads(action["result"])
            hypothesis_state = "qualified" if result["qualified"] else "rejected"
            connection.execute("UPDATE gameworld_actions SET state='cleaned',cleanup_receipt=? WHERE id=?",
                               (receipt, action_id))
            connection.execute("UPDATE gameworld_hypotheses SET state=? WHERE id=?",
                               (hypothesis_state, action["hypothesis"]))
            self.ledger._event(connection, "gameworld_cleanup_confirmed", {
                "id": action_id, "receipt": receipt, "billing_reconciled": False,
            })
        self._emit(f"candidate-{result['candidate_id']}", {
            "gameworld_candidate_qualified": int(result["qualified"]),
        }, hypothesis_state)

    def recovery_actions(self):
        with self.ledger.transaction() as connection:
            self._settings(connection)
            rows = connection.execute(
                "SELECT id,hypothesis,kind,state,provider_id,deadline,reservations FROM gameworld_actions "
                "WHERE state!='cleaned' ORDER BY id"
            ).fetchall()
            actions = []
            for row in rows:
                coordinator = str(row["provider_id"] or "").startswith("coordinator:")
                action = ({
                    "dispatching": "reconcile-coordinator-claim",
                    "running": "resume-coordinator-workflow",
                    "cleanup_pending": "finalize-coordinator-workflow",
                } if coordinator else {
                    "dispatching": "reconcile-provider-submission",
                    "running": "inspect-export-and-request-cleanup",
                    "cleanup_pending": "release-provider-and-record-receipt",
                }).get(row["state"], "inspect")
                actions.append({**dict(row), "reservations": json.loads(row["reservations"]),
                                "action": action})
            return actions

    def snapshot(self):
        with self.ledger.transaction() as connection:
            settings = dict(self._settings(connection))
            hypotheses = [dict(row) for row in connection.execute(
                "SELECT id,round,track,manifest_sha256,state FROM gameworld_hypotheses ORDER BY round"
            )]
            actions = [dict(row) for row in connection.execute(
                "SELECT id,hypothesis,kind,deadline,reservations,state,provider_id,cleanup_receipt "
                "FROM gameworld_actions ORDER BY id"
            )]
            for action in actions:
                action["reservations"] = json.loads(action["reservations"])
            qualified = {}
            for track in TRACKS:
                row = connection.execute(
                    "SELECT id FROM gameworld_hypotheses WHERE track=? AND state='qualified' ORDER BY round DESC LIMIT 1",
                    (track,),
                ).fetchone()
                qualified[track] = None if row is None else row["id"]
            selected = self._next_row(connection)
        return {
            "supervisor": settings,
            "policy": {
                "id": self.policy["id"],
                "policy_sha256": self.context["policy_sha256"],
                "catalog_manifest_sha256": self.context["catalog_manifest_sha256"],
                "split_counts": {name: len(values) for name, values in self.context["splits"].items()},
            },
            "baseline": {key: self.baseline[key] for key in ("baseline_sha256", "totals")},
            "hypotheses": hypotheses,
            "actions": actions,
            "recovery": self.recovery_actions(),
            "next": None if selected is None else selected["id"],
            "qualified_tracks": qualified,
            "joint_ready": all(qualified.values()),
            "budget": self.ledger.snapshot(),
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["initialize", "status", "register", "next", "begin", "provider", "finish", "cleanup", "recovery"])
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--campaign")
    parser.add_argument("--proposal", type=Path)
    parser.add_argument("--hypothesis")
    parser.add_argument("--action")
    parser.add_argument("--result", type=Path)
    parser.add_argument("--provider-id")
    parser.add_argument("--receipt")
    parser.add_argument("--telemetry", type=Path)
    args = parser.parse_args()
    supervisor = GameWorldResearchSupervisor(args.database, args.baseline, args.policy, args.catalog, args.telemetry)
    if args.operation == "initialize":
        if not args.campaign:
            parser.error("initialize requires --campaign")
        supervisor.initialize(args.campaign)
        value = supervisor.snapshot()
    elif args.operation == "register":
        if not args.proposal:
            parser.error("register requires --proposal")
        value = supervisor.register(_json(args.proposal))
    elif args.operation == "next":
        value = supervisor.next()
    elif args.operation == "begin":
        if not args.hypothesis or not args.action:
            parser.error("begin requires --hypothesis and --action")
        value = supervisor.begin(args.hypothesis, args.action)
    elif args.operation == "finish":
        if not args.action or not args.result:
            parser.error("finish requires --action and --result")
        supervisor.finish(args.action, _json(args.result))
        value = supervisor.snapshot()
    elif args.operation == "provider":
        if not args.action or not args.provider_id:
            parser.error("provider requires --action and --provider-id")
        supervisor.provider_started(args.action, args.provider_id)
        value = supervisor.snapshot()
    elif args.operation == "cleanup":
        if not args.action or not args.receipt:
            parser.error("cleanup requires --action and --receipt")
        supervisor.cleanup_confirmed(args.action, args.receipt)
        value = supervisor.snapshot()
    elif args.operation == "recovery":
        value = supervisor.recovery_actions()
    else:
        value = supervisor.snapshot()
    print(json.dumps(value, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
