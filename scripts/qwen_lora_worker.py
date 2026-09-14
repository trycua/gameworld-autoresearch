"""Offline, one-shot worker entrypoint for a prebuilt budget-admitted Modal sandbox."""

import argparse
import json
from pathlib import Path

from fps_bench.evaluation_contract import canonical, digest, exclusive_write
from fps_bench.qwen_lora import run_verified_dataset
from fps_bench.telemetry import ResearchTelemetry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-sha256", required=True)
    parser.add_argument("--contract-sha256", required=True)
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--experiment", required=True)
    args = parser.parse_args()
    output = Path("/output")
    output.mkdir(exist_ok=True)
    (output / "attempt-started").mkdir(exist_ok=False)
    try:
        telemetry = ResearchTelemetry(output / "telemetry.sqlite", args.campaign)
        result = run_verified_dataset(Path("/dataset"), args.dataset_sha256, args.contract_sha256,
                                      output / "training", steps=1, telemetry=telemetry, experiment=args.experiment)
        exclusive_write(output / "worker-finished.json", canonical({
            "job_id": args.experiment, "campaign": args.campaign,
            "dataset_sha256": args.dataset_sha256, "contract_sha256": args.contract_sha256,
            "result_sha256": digest((output / "training" / "result.json").read_bytes())}))
        print(json.dumps({"status": result["status"], "adapter_manifest_sha256": result["adapter_manifest_sha256"]}))
    except BaseException as error:
        exclusive_write(output / "worker-error.json", canonical({"error_type": type(error).__name__}))
        raise


if __name__ == "__main__":
    main()
