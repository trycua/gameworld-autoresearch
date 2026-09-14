"""Trusted train-only trajectory export; receipt hashes must come from the controller."""

import argparse
import io
import json
from pathlib import Path
import re

from fps_bench.evaluation_contract import canonical, digest, exclusive_write, safe_file, verify
from fps_bench.gameworld_protocol import model_messages, parse_action

HASH = re.compile(r"^[0-9a-f]{64}$")
MAX_FILE_BYTES = 16 * 1024 * 1024


class ImageBytes:
    def __init__(self, data):
        self.data = data

    def read_bytes(self):
        return self.data


def checked_bytes(root, name, expected):
    if not isinstance(expected, str) or not HASH.fullmatch(expected):
        raise ValueError("Invalid controller artifact hash")
    path = safe_file(root, name)
    with path.open("rb") as handle:
        data = handle.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES or digest(data) != expected:
        raise ValueError("Artifact size or digest mismatch")
    return data


def episode_records(root, receipt, contract, contract_hash):
    from PIL import Image

    required = {"episode_id", "split", "seed", "contract_sha256", "driver_sha256", "served_model", "files"}
    if not isinstance(receipt, dict) or set(receipt) != required:
        raise ValueError("Incomplete trusted episode receipt")
    if (receipt["split"] != "train" or type(receipt["seed"]) is not int
            or receipt["seed"] not in contract["public_splits"]["train"]["seeds"]
            or receipt["contract_sha256"] != contract_hash):
        raise ValueError("Only assigned train seeds under this contract may be exported")
    if not isinstance(receipt["episode_id"], str) or not re.fullmatch(r"[a-z0-9_-]{1,64}", receipt["episode_id"]):
        raise ValueError("Invalid episode identity")
    if not isinstance(receipt["driver_sha256"], str) or not HASH.fullmatch(receipt["driver_sha256"]):
        raise ValueError("Invalid driver identity")
    if not isinstance(receipt["served_model"], str) or not receipt["served_model"]:
        raise ValueError("Missing serving identity")
    files = receipt["files"]
    if not isinstance(files, dict) or not {"manifest.json", "summary.json", "trajectory.jsonl"} <= files.keys():
        raise ValueError("Missing controller artifact digests")
    manifest = json.loads(checked_bytes(root, "manifest.json", files["manifest.json"]))
    summary = json.loads(checked_bytes(root, "summary.json", files["summary.json"]))
    config = {**contract["episode_template"], "seed": receipt["seed"], "served_model": receipt["served_model"]}
    if (manifest.get("status") != "complete" or summary.get("status") != "complete"
            or manifest.get("contract_sha256") != contract_hash
            or manifest.get("config") != config or manifest.get("config_sha256") != digest(canonical(config))
            or manifest.get("driver_sha256") != receipt["driver_sha256"]
            or manifest.get("source", {}).get("frozen_hashes") != contract["source_hashes"]):
        raise ValueError("Episode provenance does not match trusted assignment")
    for name in ("gameworld_revision", "games_revision"):
        if manifest.get(name) != contract["spec"]["provenance"][name]:
            raise ValueError("Upstream revision mismatch")
    rows = [json.loads(line) for line in checked_bytes(root, "trajectory.jsonl", files["trajectory.jsonl"]).splitlines()]
    if (type(summary.get("steps")) is not int or not 1 <= len(rows) <= config["max_steps"]
            or summary["steps"] != len(rows) or type(summary.get("success")) is not bool
            or type(summary.get("invalid_actions")) is not int):
        raise ValueError("Incomplete episode summary or trajectory")
    history, records, images = [], [], {}
    invalid, image_bytes = 0, 0
    for index, row in enumerate(rows):
        name = f"{index:03d}.png"
        if (type(row.get("step")) is not int or row["step"] != index or row.get("observation") != name
                or name not in files or row.get("observation_sha256") != files[name]):
            raise ValueError("Trajectory ordering or screenshot identity mismatch")
        data = checked_bytes(root, name, files[name])
        image_bytes += len(data)
        if image_bytes > 64 * 1024 * 1024:
            raise ValueError("Episode screenshots exceed the pilot export limit")
        with Image.open(io.BytesIO(data)) as image:
            if image.format != "PNG" or list(image.size) != contract["spec"]["geometry"]["desktop"]:
                raise ValueError("Screenshot format or geometry mismatch")
            image.verify()
        text = row.get("response")
        if text is not None and (not isinstance(text, str) or len(text.encode()) > 65536):
            raise ValueError("Invalid response representation")
        try:
            action = parse_action(text)
        except (ValueError, TypeError):
            action = None
        if row.get("action") != action or (action is None) != (row.get("invalid_action") is not None):
            raise ValueError("Response/action validity mismatch")
        if action is None:
            invalid += 1
        else:
            messages = model_messages(ImageBytes(data), history)
            image_name = f"images/{digest(data)}.png"
            messages[-1]["content"][-1] = {"type": "image", "image": image_name}
            records.append({"id": f"{receipt['episode_id']}:{index}", "messages": messages,
                            "completion": [{"role": "assistant", "content": text}]})
            images[image_name] = data
        history.append(text if isinstance(text, str) else "invalid empty response")
    if summary["invalid_actions"] != invalid:
        raise ValueError("Invalid action total mismatch")
    return records, images, {"episode_id": receipt["episode_id"], "seed": receipt["seed"],
                             "steps": len(rows), "invalid_actions": invalid, "success": summary["success"],
                             "receipt_sha256": digest(canonical(receipt))}


def export_dataset(contract_path, contract_hash, episodes, output):
    contract = verify(contract_path, contract_hash)
    if not 1 <= len(episodes) <= 256:
        raise ValueError("Expected 1..256 trusted episode receipts")
    records, images, provenance = [], {}, []
    identifiers, seeds = set(), set()
    for root, receipt in episodes:
        current, screenshots, metadata = episode_records(root, receipt, contract, contract_hash)
        if metadata["episode_id"] in identifiers or metadata["seed"] in seeds:
            raise ValueError("Duplicate train episode or seed")
        identifiers.add(metadata["episode_id"])
        seeds.add(metadata["seed"])
        records.extend(current)
        images.update(screenshots)
        if sum(map(len, images.values())) > 256 * 1024 * 1024:
            raise ValueError("Dataset screenshots exceed the pilot export limit")
        provenance.append(metadata)
    if not records:
        raise ValueError("No valid action targets; refusing an empty training dataset")
    payload = b"".join(canonical(record) for record in records)
    if len(payload) > MAX_FILE_BYTES:
        raise ValueError("Dataset text exceeds the pilot export limit")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "images").mkdir()
    exclusive_write(output / "samples.jsonl", payload, 0o400)
    for name, data in images.items():
        exclusive_write(output / name, data, 0o400)
    manifest = {"schema_version": 1, "purpose": "train-only-action-imitation", "contract_sha256": contract_hash,
                "samples": len(records), "episodes": provenance,
                "files": {"samples.jsonl": digest(payload), **{name: digest(data) for name, data in images.items()}}}
    exclusive_write(output / "dataset.json", canonical(manifest), 0o400)
    return {"dataset_sha256": digest(canonical(manifest)), "samples": len(records), "seeds": sorted(seeds)}


def verify_dataset(root, expected_hash, contract_hash):
    """Check copied training inputs against the controller's external dataset identity."""
    manifest = json.loads(checked_bytes(root, "dataset.json", expected_hash))
    if (manifest.get("schema_version") != 1 or manifest.get("purpose") != "train-only-action-imitation"
            or manifest.get("contract_sha256") != contract_hash):
        raise ValueError("Training dataset purpose or contract mismatch")
    files = manifest.get("files", {})
    if not isinstance(files, dict) or "samples.jsonl" not in files:
        raise ValueError("Missing dataset file inventory")
    for name in files:
        if name != "samples.jsonl" and not re.fullmatch(r"images/[0-9a-f]{64}\.png", name):
            raise ValueError("Unexpected training dataset file")
    samples = [json.loads(line) for line in checked_bytes(root, "samples.jsonl", files["samples.jsonl"]).splitlines()]
    if type(manifest.get("samples")) is not int or not samples or len(samples) != manifest["samples"]:
        raise ValueError("Training sample count mismatch")
    for name, expected in files.items():
        if name != "samples.jsonl":
            if Path(name).stem != expected:
                raise ValueError("Image filename differs from content hash")
            checked_bytes(root, name, expected)
    referenced = set()
    for sample in samples:
        if not isinstance(sample, dict) or set(sample) != {"id", "messages", "completion"}:
            raise ValueError("Unexpected training sample fields")
        try:
            name = sample["messages"][1]["content"][1]["image"]
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError("Missing sample screenshot") from error
        if name not in files or name == "samples.jsonl":
            raise ValueError("Screenshot is outside the verified dataset")
        referenced.add(name)
    if referenced != set(files) - {"samples.jsonl"}:
        raise ValueError("Unreferenced dataset images")
    return manifest, samples


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--contract-sha256", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--receipt-sha256", required=True)
    parser.add_argument("--episode", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = json.loads(checked_bytes(args.receipt.parent, args.receipt.name, args.receipt_sha256))
    print(json.dumps(export_dataset(args.contract, args.contract_sha256, [(args.episode, receipt)], args.output)))


if __name__ == "__main__":
    main()
