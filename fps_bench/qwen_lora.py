"""Bounded Qwen3-VL action-imitation compatibility slice, not a campaign launcher."""

import copy
import importlib.metadata
import json
import math
from pathlib import Path
import re
import time

from fps_bench.evaluation_contract import canonical, digest, exclusive_write, safe_file
from fps_bench.training_data import checked_bytes, verify_dataset

BASE_MODEL = "Qwen/Qwen3-VL-2B-Instruct"
BASE_REVISION = "89644892e4d85e24eaac8bacfd4f463576704203"
TARGETS = r".*language_model\.layers\.\d+\.self_attn\.(q_proj|v_proj)"


def action_batch(processor, sample, dataset_root, max_tokens=4096):
    import torch
    from PIL import Image

    messages = copy.deepcopy(sample["messages"])
    name = messages[1]["content"][1]["image"]
    with Image.open(safe_file(dataset_root, name)) as source:
        image = source.convert("RGB")
    prompt = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    full = processor.apply_chat_template(messages + sample["completion"], tokenize=False, add_generation_prompt=False)
    prompt_batch = processor(text=[prompt], images=[image], return_tensors="pt", padding=False)
    batch = processor(text=[full], images=[image], return_tensors="pt", padding=False)
    prefix = prompt_batch["input_ids"]
    tokens = batch["input_ids"]
    if (tokens.ndim != 2 or tokens.shape[0] != 1 or tokens.shape[1] > max_tokens
            or prefix.shape[1] >= tokens.shape[1] or not torch.equal(tokens[:, :prefix.shape[1]], prefix)):
        raise ValueError("Prompt is not an exact nonempty prefix, or multimodal context exceeds the limit")
    if "pixel_values" not in batch or "image_grid_thw" not in batch:
        raise ValueError("Training sample must carry image features")
    labels = tokens.clone()
    labels[:, :prefix.shape[1]] = -100
    labels[batch["attention_mask"] == 0] = -100
    image_token = getattr(processor, "image_token_id", None)
    if image_token is not None and torch.any(labels == image_token):
        raise ValueError("Image tokens must never be action targets")
    if not torch.any(labels != -100):
        raise ValueError("No assistant action tokens to supervise")
    batch["labels"] = labels
    return batch


def verify_adapter(root, expected_hash, base_model, base_revision, dataset_hash, contract_hash):
    manifest = json.loads(checked_bytes(root, "adapter-manifest.json", expected_hash))
    expected = {"schema_version": 1, "base_model": base_model, "base_revision": base_revision,
                "processor_revision": base_revision, "dataset_sha256": dataset_hash, "contract_sha256": contract_hash}
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise ValueError("Adapter provenance does not match the assigned candidate")
    files = manifest.get("files", {})
    if not {"adapter_config.json", "adapter_model.safetensors"} <= files.keys():
        raise ValueError("Adapter files are incomplete")
    if set(files) - {"adapter_config.json", "adapter_model.safetensors", "README.md"}:
        raise ValueError("Unexpected adapter payload")
    for name, expected_digest in files.items():
        checked_bytes(root, name, expected_digest)
    return manifest


def train_and_reload(base, fresh_base, batches, output, *, base_model, base_revision,
                     dataset_hash, contract_hash, steps=1, learning_rate=1e-4, seed=42, telemetry=None, experiment=None):
    import torch
    from peft import LoraConfig, PeftModel, get_peft_model

    if type(steps) is not int or not 1 <= steps <= 32 or not batches:
        raise ValueError("Compatibility slice requires 1..32 steps and image-bearing batches")
    if type(learning_rate) not in (int, float) or not math.isfinite(learning_rate) or not 0 < learning_rate <= 1e-3:
        raise ValueError("Learning rate outside compatibility bounds")
    for value in (dataset_hash, contract_hash):
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError("Immutable data and contract identities required")
    if telemetry is not None and (not isinstance(experiment, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", experiment)):
        raise ValueError("Telemetry requires an immutable bounded experiment identity")
    for batch in batches:
        if not {"input_ids", "labels", "pixel_values", "image_grid_thw"} <= batch.keys():
            raise ValueError("Image-bearing causal-LM batch required")
        if batch["input_ids"].shape[0] != 1 or batch["input_ids"].shape[1] > 4096:
            raise ValueError("Compatibility batch size or context exceeds bounds")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    torch.manual_seed(seed)
    base.config.use_cache = False
    model = get_peft_model(base, LoraConfig(r=8, lora_alpha=16, lora_dropout=0.0,
                                          target_modules=TARGETS, bias="none", task_type="CAUSAL_LM"))
    trainable = {name: parameter for name, parameter in model.named_parameters() if parameter.requires_grad}
    if not trainable or any("lora_" not in name or "language_model.layers." not in name for name in trainable):
        raise ValueError("Only language attention LoRA parameters may be trainable")
    initial = {name: parameter.detach().cpu().clone() for name, parameter in trainable.items()}
    optimizer = torch.optim.AdamW(trainable.values(), lr=learning_rate, weight_decay=0.0)
    device = next(model.parameters()).device
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    losses, telemetry_errors = [], []
    started = time.monotonic()
    for step in range(steps):
        model.train()
        batch = {key: value.to(device) for key, value in batches[step % len(batches)].items()}
        optimizer.zero_grad(set_to_none=True)
        loss = model(**batch, use_cache=False).loss
        if loss is None or not torch.isfinite(loss):
            raise ValueError("Nonfinite or missing training loss")
        loss.backward()
        gradients = [parameter.grad for parameter in trainable.values() if parameter.grad is not None]
        if not gradients or any(not torch.isfinite(gradient).all() for gradient in gradients):
            raise ValueError("Missing or nonfinite adapter gradients")
        if not any(torch.count_nonzero(gradient).item() for gradient in gradients):
            raise ValueError("No nonzero adapter gradient")
        norm = torch.nn.utils.clip_grad_norm_(trainable.values(), 1.0, error_if_nonfinite=True)
        optimizer.step()
        row = {"timestamp_ns": time.time_ns(), "step": step + 1, "loss": float(loss.detach()), "gradient_norm": float(norm),
               "supervised_tokens": int((batch["labels"] != -100).sum())}
        losses.append(row)
        with (output / "loss.jsonl").open("ab") as handle:
            handle.write(canonical(row))
        if telemetry is not None:
            try:
                telemetry.record(f"lora:{experiment}:{step + 1}", "gameworld-train",
                                 {"experiment": experiment, "phase": "train", "split": "train", "objective": "compatibility"},
                                 {"gameworld_train_loss": row["loss"], "gameworld_train_step": step + 1}, step=step + 1, timestamp_ns=row["timestamp_ns"])
            except Exception as error:
                telemetry_errors.append({"step": step + 1, "error_type": type(error).__name__})
    changed = [name for name, parameter in trainable.items() if not torch.equal(initial[name], parameter.detach().cpu())]
    if not changed or any(not torch.isfinite(parameter).all() for parameter in trainable.values()):
        raise ValueError("Adapter did not produce a finite parameter update")
    model.eval()
    probe = {key: value.to(device) for key, value in batches[0].items() if key != "labels"}
    with torch.no_grad():
        expected_logits = model(**probe, use_cache=False).logits.detach().float().cpu()
    adapter = output / "adapter"
    model.save_pretrained(adapter, safe_serialization=True)
    files = {path.name: digest(path.read_bytes()) for path in adapter.iterdir() if path.is_file()}
    manifest = {"schema_version": 1, "base_model": base_model, "base_revision": base_revision,
                "processor_revision": base_revision, "dataset_sha256": dataset_hash, "contract_sha256": contract_hash,
                "files": files, "hyperparameters": {"steps": steps, "learning_rate": learning_rate,
                "seed": seed, "rank": 8, "alpha": 16, "targets": TARGETS, "batch_size": 1},
                "versions": {name: importlib.metadata.version(name)
                             for name in ("torch", "transformers", "peft", "accelerate")}}
    manifest_hash = digest(canonical(manifest))
    exclusive_write(adapter / "adapter-manifest.json", canonical(manifest), 0o400)
    verify_adapter(adapter, manifest_hash, base_model, base_revision, dataset_hash, contract_hash)
    reloaded = PeftModel.from_pretrained(fresh_base(), str(adapter), is_trainable=False)
    reloaded.eval()
    reload_device = next(reloaded.parameters()).device
    with torch.no_grad():
        observed = reloaded(**{key: value.to(reload_device) for key, value in probe.items()}, use_cache=False).logits.float().cpu()
    error = float((observed - expected_logits).abs().max())
    if not torch.allclose(observed, expected_logits, atol=1e-4, rtol=1e-4):
        raise ValueError("Saved adapter reload changes logits")
    result = {"status": "complete", "steps": steps, "losses": losses, "adapter_manifest_sha256": manifest_hash,
              "updated_parameter_tensors": len(changed), "reload_max_logit_error": error,
              "seconds": time.monotonic() - started,
              "peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated(device) if device.type == "cuda" else None,
              "device": str(device), "telemetry_errors": telemetry_errors, "benchmark_improvement_claimed": False}
    exclusive_write(output / "result.json", canonical(result))
    return result


def run_verified_dataset(dataset_root, dataset_hash, contract_hash, output, steps=1, telemetry=None, experiment=None):
    import torch
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

    if type(steps) is not int or not 1 <= steps <= 32:
        raise ValueError("Compatibility slice requires 1..32 steps")
    if not torch.cuda.is_available():
        raise RuntimeError("The real 2B compatibility slice requires a budget-admitted GPU worker")
    _, samples = verify_dataset(dataset_root, dataset_hash, contract_hash)
    processor = AutoProcessor.from_pretrained(BASE_MODEL, revision=BASE_REVISION, trust_remote_code=False)
    batches = [action_batch(processor, sample, dataset_root) for sample in samples[:steps]]

    def load():
        return Qwen3VLForConditionalGeneration.from_pretrained(
            BASE_MODEL, revision=BASE_REVISION, torch_dtype=torch.bfloat16,
            attn_implementation="eager", trust_remote_code=False).to("cuda")

    return train_and_reload(load(), load, batches, output, base_model=BASE_MODEL, base_revision=BASE_REVISION,
                            dataset_hash=dataset_hash, contract_hash=contract_hash, steps=steps, telemetry=telemetry, experiment=experiment)
