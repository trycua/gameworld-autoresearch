"""One pretrained GPU update on a historical GameWorld pair, not frozen campaign data."""

import json
from pathlib import Path
import subprocess

import torch
from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

from fps_bench.evaluation_contract import canonical, digest, exclusive_write
from fps_bench.gameworld_protocol import PROMPT, parse_action
from fps_bench.qwen_lora import BASE_MODEL, BASE_REVISION, action_batch, train_and_reload


def main():
    root = Path("/input")
    output = Path("/output")
    subprocess.run(["python", "/app/image/qwen-training/smoke.py"], check=True)
    output.mkdir(exist_ok=False)
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable")
    torch.set_num_threads(4)
    source = json.loads((root / "input.json").read_bytes())
    if digest((root / "000.png").read_bytes()) != source["image_sha256"]:
        raise ValueError("Historical observation hash mismatch")
    parse_action(source["response"])
    contract = {"purpose": "historical-pre-freeze-gpu-compatibility", "steps": 1,
                "base_model": BASE_MODEL, "base_revision": BASE_REVISION, "frozen_campaign_data": False}
    sample = {"messages": [{"role": "system", "content": PROMPT}, {"role": "user", "content": [
        {"type": "text", "text": "Recent responses (invalid responses do nothing):\n\nChoose the next action from this screenshot."},
        {"type": "image", "image": "000.png"}]}],
        "completion": [{"role": "assistant", "content": source["response"]}]}
    processor = AutoProcessor.from_pretrained(BASE_MODEL, revision=BASE_REVISION, local_files_only=True, trust_remote_code=False)
    batch = action_batch(processor, sample, root)

    def load():
        return Qwen3VLForConditionalGeneration.from_pretrained(
            BASE_MODEL, revision=BASE_REVISION, local_files_only=True, trust_remote_code=False,
            torch_dtype=torch.bfloat16, attn_implementation="eager").to("cuda")

    device = {"name": torch.cuda.get_device_name(), "torch": torch.__version__, "cuda": torch.version.cuda,
              "capability": list(torch.cuda.get_device_capability())}
    print(json.dumps({"status": "training", "device": device}), flush=True)
    result = train_and_reload(load(), load, [batch], output / "training", base_model=BASE_MODEL,
                              base_revision=BASE_REVISION, dataset_hash=digest(canonical(source)),
                              contract_hash=digest(canonical(contract)), steps=1)
    report = {"scope": "historical pre-freeze GameWorld pair; GPU compatibility, not benchmark improvement",
              "source": source, "contract": contract, "device": device, "training": result,
              "worker_sha256": digest(Path(__file__).read_bytes()), "image_manifest_sha256": digest(Path("/app/training-image.json").read_bytes())}
    exclusive_write(output / "probe.json", canonical(report))
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
