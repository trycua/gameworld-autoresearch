"""Run one admitted GameWorld SFT or GRPO model update in an offline Modal sandbox."""

import argparse
import json
from pathlib import Path

from fps_bench.evaluation_contract import canonical, digest, exclusive_write
from fps_bench.gameworld_grpo import train_grpo_dataset
from fps_bench.gameworld_research import load_policy
from fps_bench.qwen_lora import run_verified_dataset
from fps_bench.telemetry import ResearchTelemetry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--objective", choices=["sft", "grpo"], required=True)
    parser.add_argument("--dataset", type=Path, default=Path("/dataset"))
    parser.add_argument("--dataset-sha256", required=True)
    parser.add_argument("--contract-sha256")
    parser.add_argument("--evaluation-contract-sha256", required=True)
    parser.add_argument("--policy-identity", type=Path)
    parser.add_argument("--driver-sha256")
    parser.add_argument("--parent-adapter", type=Path)
    parser.add_argument("--steps", type=int, required=True)
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--output", type=Path, default=Path("/output"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "attempt-started").mkdir(exist_ok=False)
    telemetry = ResearchTelemetry(args.output / "telemetry.sqlite", args.campaign)
    try:
        if args.objective == "sft":
            if not args.contract_sha256 or args.policy_identity or args.driver_sha256 or args.parent_adapter:
                raise ValueError("SFT requires only the frozen imitation contract identity")
            result = run_verified_dataset(args.dataset, args.dataset_sha256, args.contract_sha256,
                                          args.output / "training", steps=args.steps,
                                          telemetry=telemetry, experiment=args.experiment)
        else:
            if not args.policy_identity or not args.driver_sha256 or args.contract_sha256:
                raise ValueError("GRPO requires rollout policy and driver identities")
            identity_bytes = args.policy_identity.read_bytes()
            identity = json.loads(identity_bytes)
            if canonical(identity) != identity_bytes:
                raise ValueError("Rollout policy identity must use canonical encoding")
            policy, context = load_policy(
                Path("/app/configs/gameworld-autoresearch.json"),
                Path("/app/configs/evaluation/gameworld-suite-v1.json"),
            )
            result = train_grpo_dataset(
                args.dataset, args.dataset_sha256, policy=policy, context=context,
                expected_policy=identity, expected_driver_sha256=args.driver_sha256,
                output=args.output / "training", steps=args.steps,
                parent_adapter=args.parent_adapter, telemetry=telemetry, experiment=args.experiment)
        exclusive_write(args.output / "worker-finished.json", canonical({
            "job_id": args.experiment, "campaign": args.campaign, "experiment": args.experiment,
            "objective": args.objective, "contract_sha256": args.evaluation_contract_sha256,
            "dataset_sha256": args.dataset_sha256,
            "result_sha256": digest((args.output / "training/result.json").read_bytes()),
            "adapter_manifest_sha256": result["adapter_manifest_sha256"],
        }))
        print(json.dumps({"status": result["status"], "objective": args.objective,
                          "adapter_manifest_sha256": result["adapter_manifest_sha256"]}, sort_keys=True))
    except BaseException as error:
        exclusive_write(args.output / "worker-error.json", canonical({"error_type": type(error).__name__}))
        raise


if __name__ == "__main__":
    main()
