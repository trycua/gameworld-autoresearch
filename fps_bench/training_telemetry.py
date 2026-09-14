"""Import loss scalars from verified exports, never a worker's SQLite database."""

import json
import math
from pathlib import Path
import time

from fps_bench.evaluation_contract import canonical
from fps_bench.telemetry import LABEL
from fps_bench.training_data import checked_bytes


def import_training_losses(artifacts, job_id, telemetry):
    job, _, plan = artifacts.lifecycle.stored(job_id)
    if (job["kind"] != "training" or telemetry.campaign != plan["tags"]["campaign"]
            or not LABEL.fullmatch(job_id)):
        raise ValueError("Training telemetry destination must match its admitted job")
    receipt = artifacts.reconcile_export(job_id)
    root = Path(receipt["output"])
    result = json.loads(checked_bytes(root, "result.json", receipt["files"]["result.json"]))
    rows = [json.loads(line) for line in checked_bytes(root, "loss.jsonl", receipt["files"]["loss.jsonl"]).splitlines()]
    if (result.get("status") != "complete" or type(result.get("steps")) is not int
            or not 1 <= result["steps"] <= 32 or len(rows) != result["steps"]
            or canonical(rows) != canonical(result.get("losses"))):
        raise ValueError("Loss log differs from completed training result")
    previous = 0
    now = time.time_ns()
    for step, row in enumerate(rows, 1):
        if (not isinstance(row, dict) or set(row) != {"timestamp_ns", "step", "loss", "gradient_norm", "supervised_tokens"}
                or type(row["step"]) is not int or row["step"] != step
                or type(row["timestamp_ns"]) is not int
                or not previous < row["timestamp_ns"] <= min(now, job["deadline"] * 1_000_000_000)
                or type(row["supervised_tokens"]) is not int or row["supervised_tokens"] <= 0):
            raise ValueError("Invalid optimizer step metadata")
        for name in ("loss", "gradient_norm"):
            if type(row[name]) not in (int, float) or not math.isfinite(row[name]):
                raise ValueError("Invalid optimizer scalar")
        if row["gradient_norm"] < 0:
            raise ValueError("Negative gradient norm")
        previous = row["timestamp_ns"]
    inserted = 0
    for row in rows:
        inserted += telemetry.record(
            f"lora:{job_id}:{row['step']}", "gameworld-train",
            {"experiment": job_id, "phase": "train", "split": "train", "objective": "compatibility"},
            {"gameworld_train_loss": row["loss"], "gameworld_train_step": row["step"]},
            step=row["step"], timestamp_ns=row["timestamp_ns"])
    return {"job_id": job_id, "steps": len(rows), "inserted": inserted,
            "adapter_manifest_sha256": receipt["adapter_manifest_sha256"]}
