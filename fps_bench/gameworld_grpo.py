"""Immutable interactive rollout data and a bounded multimodal GRPO objective."""

import copy
import importlib.metadata
import json
import math
from pathlib import Path
import re
import time

from fps_bench.evaluation_contract import canonical, digest, exclusive_write, safe_file
from fps_bench.qwen_lora import TARGETS


SHA256 = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
IMAGE = re.compile(r"^images/[0-9a-f]{64}\.png$")
TRAJECTORY = re.compile(r"^trajectories/[a-z][a-z0-9_-]{0,63}\.jsonl$")
FORBIDDEN_MESSAGE_KEYS = {"before", "after", "evaluation", "game_state", "metrics", "reward"}
MAX_DATASET_BYTES = 512 * 1024 * 1024
POLICY_FIELDS = {"base_model", "base_revision", "adapter_sha256", "served_model", "generation"}


def reward_components(summary, settings):
    required = {"steps", "success", "progress", "invalid_actions", "driver_errors"}
    if (not isinstance(summary, dict) or set(summary) != required
            or type(summary["steps"]) is not int or not 1 <= summary["steps"] <= 60
            or type(summary["success"]) is not bool
            or type(summary["progress"]) not in (int, float) or not math.isfinite(summary["progress"])
            or not 0 <= summary["progress"] <= 1
            or any(type(summary[name]) is not int or not 0 <= summary[name] <= summary["steps"]
                   for name in ("invalid_actions", "driver_errors"))):
        raise ValueError("Invalid rollout reward summary")
    components = {
        "terminal_success": settings["terminal_success_weight"] * int(summary["success"]),
        "progress": settings["progress_weight"] * summary["progress"],
        "invalid_action": -settings["invalid_action_penalty"] * summary["invalid_actions"] / summary["steps"],
        "driver_error": -settings["driver_error_penalty"] * summary["driver_errors"] / summary["steps"],
    }
    return {**components, "total": sum(components.values())}


def group_advantages(rewards):
    if (not isinstance(rewards, list) or not 2 <= len(rewards) <= 8
            or any(type(value) not in (int, float) or not math.isfinite(value) for value in rewards)):
        raise ValueError("GRPO rewards require a finite group of two to eight")
    mean = sum(rewards) / len(rewards)
    variance = sum((value - mean) ** 2 for value in rewards) / len(rewards)
    if variance <= 1e-12:
        return {"advantages": [0.0] * len(rewards), "mean": mean, "std": 0.0, "zero_variance": True}
    std = math.sqrt(variance)
    return {"advantages": [(value - mean) / std for value in rewards],
            "mean": mean, "std": std, "zero_variance": False}


def grpo_loss(current_logps, old_logps, reference_logps, mask, advantages, *, clip_epsilon, beta):
    import torch

    if (current_logps.shape != old_logps.shape or current_logps.shape != reference_logps.shape
            or current_logps.shape != mask.shape or current_logps.ndim != 2
            or advantages.ndim != 1 or advantages.shape[0] != current_logps.shape[0]
            or mask.dtype != torch.bool or not torch.any(mask)
            or any(tensor.requires_grad for tensor in (old_logps, reference_logps, advantages))
            or not 0 < clip_epsilon <= 0.5 or not 0 <= beta <= 1):
        raise ValueError("Invalid tensors or bounds for the GRPO objective")
    for tensor in (current_logps, old_logps, reference_logps, advantages):
        if not torch.isfinite(tensor).all():
            raise ValueError("GRPO tensors must be finite")
    ratio = torch.exp(current_logps - old_logps)
    expanded_advantages = advantages[:, None]
    unclipped = ratio * expanded_advantages
    clipped = torch.clamp(ratio, 1 - clip_epsilon, 1 + clip_epsilon) * expanded_advantages
    reverse_delta = reference_logps - current_logps
    per_token_kl = torch.exp(reverse_delta) - reverse_delta - 1
    per_token_loss = -(torch.minimum(unclipped, clipped) - beta * per_token_kl)
    weights = mask.to(per_token_loss.dtype)
    sequence_loss = (per_token_loss * weights).sum(dim=1) / weights.sum(dim=1).clamp_min(1)
    loss = sequence_loss.mean()
    return loss, {
        "policy_loss": float((-(torch.minimum(unclipped, clipped)) * weights).sum().detach()
                             / weights.sum().detach()),
        "reference_kl": float((per_token_kl * weights).sum().detach() / weights.sum().detach()),
        "clip_fraction": float((((ratio < 1 - clip_epsilon) | (ratio > 1 + clip_epsilon)) & mask)
                               .to(torch.float32).sum().detach() / mask.sum().detach()),
    }


def _checked_file(root, name, expected):
    if not isinstance(name, str) or name.startswith("/") or ".." in Path(name).parts or not SHA256.fullmatch(expected):
        raise ValueError("Invalid rollout file identity")
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Rollout dataset contains a missing or linked file")
    data = path.read_bytes()
    if digest(data) != expected:
        raise ValueError("Rollout dataset file hash changed")
    return data


def _message_images(messages):
    if not isinstance(messages, list) or len(messages) < 2:
        raise ValueError("Rollout step requires a complete model conversation")
    images = []
    for message in messages:
        if (not isinstance(message, dict) or set(message) != {"role", "content"}
                or message["role"] not in {"system", "user", "assistant"}):
            raise ValueError("Unexpected rollout message schema")
        content = message["content"]
        if isinstance(content, str):
            if len(content.encode()) > 65536:
                raise ValueError("Rollout message text exceeds the bound")
            continue
        if not isinstance(content, list):
            raise ValueError("Rollout message content must be text or multimodal parts")
        for part in content:
            if not isinstance(part, dict) or set(part) not in ({"type", "text"}, {"type", "image"}):
                raise ValueError("Unexpected rollout message part")
            if part["type"] == "text":
                if not isinstance(part["text"], str) or len(part["text"].encode()) > 65536:
                    raise ValueError("Invalid rollout message text")
            elif not isinstance(part["image"], str) or not IMAGE.fullmatch(part["image"]):
                raise ValueError("Rollout message references an invalid image")
            else:
                images.append(part["image"])
    return images


def _has_forbidden_key(value):
    if isinstance(value, dict):
        return bool(set(value) & FORBIDDEN_MESSAGE_KEYS) or any(_has_forbidden_key(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_forbidden_key(item) for item in value)
    return False


def _trajectory(data, files):
    rows = [json.loads(line) for line in data.splitlines() if line.strip()]
    if not rows:
        raise ValueError("Rollout trajectory is empty")
    images = []
    for index, row in enumerate(rows):
        required = {"step", "messages", "response", "observation", "observation_sha256", "action", "invalid_action"}
        if (not isinstance(row, dict) or set(row) != required or row["step"] != index
                or not isinstance(row["response"], str) or len(row["response"].encode()) > 65536
                or not IMAGE.fullmatch(row["observation"])
                or row["observation_sha256"] != files.get(row["observation"])
                or (row["action"] is None) == (row["invalid_action"] is None)
                or (row["action"] is not None and not isinstance(row["action"], dict))
                or (row["invalid_action"] is not None and not isinstance(row["invalid_action"], str))):
            raise ValueError("Invalid rollout trajectory step")
        referenced = _message_images(row["messages"])
        if row["observation"] not in referenced:
            raise ValueError("Rollout conversation omits its current observation")
        if _has_forbidden_key(row["messages"]):
            raise ValueError("Privileged evaluator data leaked into rollout messages")
        images.extend(referenced)
    return rows, images


def policy_core(identity):
    if not isinstance(identity, dict) or set(identity) not in (POLICY_FIELDS, POLICY_FIELDS | {"deployment"}):
        raise ValueError("Rollout policy identity is incomplete")
    return {name: identity[name] for name in sorted(POLICY_FIELDS)}


def policy_digest(identity):
    return digest(canonical(policy_core(identity)))


def validate_policy_core(expected_policy, policy):
    core = policy_core(expected_policy)
    if (core["base_model"] != policy["model"]["base_model"]
            or core["base_revision"] != policy["model"]["base_revision"]
            or (core["adapter_sha256"] is not None and not SHA256.fullmatch(core["adapter_sha256"]))
            or not isinstance(core["served_model"], str)
            or not 1 <= len(core["served_model"]) <= 128):
        raise ValueError("Rollout serving policy identity is incomplete")
    generation = core["generation"]
    if (not isinstance(generation, dict)
            or set(generation) != {"temperature", "top_p", "max_tokens", "response_format"}
            or type(generation["temperature"]) not in (int, float) or not 0 < generation["temperature"] <= 2
            or type(generation["top_p"]) not in (int, float) or not 0 < generation["top_p"] <= 1
            or type(generation["max_tokens"]) is not int or not 1 <= generation["max_tokens"] <= 512
            or generation["response_format"] != "unconstrained-json-text"):
        raise ValueError("GRPO rollouts require stochastic unconstrained policy sampling")
    return core


def validate_policy_identity(expected_policy, policy):
    validate_policy_core(expected_policy, policy)
    if "deployment" not in expected_policy:
        raise ValueError("Rollout deployment identity is incomplete")
    deployment = expected_policy["deployment"]
    function = isinstance(deployment, dict) and set(deployment) == {
        "app_id", "function_id", "image_id", "endpoint_sha256"}
    sandbox = isinstance(deployment, dict) and set(deployment) == {
        "app_id", "sandbox_id", "image_id", "endpoint_sha256"}
    if (not (function or sandbox)
            or not re.fullmatch(r"ap-[A-Za-z0-9]+", deployment["app_id"])
            or function and not re.fullmatch(r"fu-[A-Za-z0-9]+", deployment["function_id"])
            or sandbox and not re.fullmatch(r"sb-[A-Za-z0-9]+", deployment["sandbox_id"])
            or not re.fullmatch(r"im-[A-Za-z0-9]+", deployment["image_id"])
            or not SHA256.fullmatch(deployment["endpoint_sha256"])):
        raise ValueError("Rollout deployment identity is incomplete")
    return expected_policy


def verify_rollout_dataset(root, expected_hash, *, policy, context, expected_policy, expected_driver_sha256):
    root = Path(root)
    manifest_path = root / "rollouts.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise ValueError("Missing rollout manifest")
    manifest_bytes = manifest_path.read_bytes()
    if digest(manifest_bytes) != expected_hash:
        raise ValueError("Rollout manifest identity changed")
    manifest = json.loads(manifest_bytes)
    if canonical(manifest) != manifest_bytes:
        raise ValueError("Rollout manifest must use canonical encoding")
    validate_policy_identity(expected_policy, policy)
    required = {"schema_version", "purpose", "catalog_manifest_sha256", "policy", "driver_sha256",
                "reward", "groups", "files"}
    if (not isinstance(manifest, dict) or set(manifest) != required
            or manifest["schema_version"] != 1 or manifest["purpose"] != "gameworld-interactive-grpo-v1"
            or manifest["catalog_manifest_sha256"] != context["catalog_manifest_sha256"]
            or manifest["policy"] != expected_policy or manifest["driver_sha256"] != expected_driver_sha256
            or not SHA256.fullmatch(manifest["driver_sha256"])
            or manifest["reward"] != policy["model"]["grpo"]
            or not isinstance(manifest["groups"], list) or not manifest["groups"]
            or not isinstance(manifest["files"], dict)):
        raise ValueError("Rollout manifest differs from its admitted identities")
    total_bytes = 0
    file_bytes = {}
    for name, expected in manifest["files"].items():
        if not (IMAGE.fullmatch(name) or TRAJECTORY.fullmatch(name)):
            raise ValueError("Unexpected rollout dataset file")
        data = _checked_file(root, name, expected)
        total_bytes += len(data)
        if total_bytes > MAX_DATASET_BYTES:
            raise ValueError("Rollout dataset exceeds the bounded transfer size")
        file_bytes[name] = data
    train = set(context["splits"]["train"])
    group_ids, trajectory_ids, used_files = set(), set(), set()
    zero_variance_groups = 0
    for group in manifest["groups"]:
        if (not isinstance(group, dict)
                or set(group) != {"id", "game", "task", "seed", "initial_state_sha256", "members"}
                or not IDENTIFIER.fullmatch(group["id"])
                or f"{group['game']}--{group['task']}" not in train
                or type(group["seed"]) is not int or not 0 <= group["seed"] <= 0xFFFFFFFF
                or not SHA256.fullmatch(group["initial_state_sha256"])
                or not isinstance(group["members"], list)
                or not policy["model"]["minimum_grpo_group_size"] <= len(group["members"]) <= policy["model"]["maximum_grpo_group_size"]
                or group["id"] in group_ids):
            raise ValueError("Invalid or duplicate rollout group")
        group_ids.add(group["id"])
        rewards = []
        for member in group["members"]:
            required_member = {"id", "trajectory", "trajectory_sha256", "steps", "success", "progress",
                               "invalid_actions", "driver_errors", "reward_components", "reward"}
            if (not isinstance(member, dict) or set(member) != required_member
                    or not IDENTIFIER.fullmatch(member["id"]) or member["id"] in trajectory_ids
                    or not TRAJECTORY.fullmatch(member["trajectory"])
                    or member["trajectory_sha256"] != manifest["files"].get(member["trajectory"])):
                raise ValueError("Invalid or duplicate rollout trajectory identity")
            rows, images = _trajectory(file_bytes[member["trajectory"]], manifest["files"])
            summary = {name: member[name] for name in ("steps", "success", "progress", "invalid_actions", "driver_errors")}
            components = reward_components(summary, policy["model"]["grpo"])
            if (len(rows) != member["steps"] or member["reward_components"] != components
                    or type(member["reward"]) not in (int, float) or not math.isclose(member["reward"], components["total"], abs_tol=1e-12)):
                raise ValueError("Rollout reward or step count cannot be reproduced")
            trajectory_ids.add(member["id"])
            used_files.add(member["trajectory"])
            used_files.update(images)
            rewards.append(member["reward"])
        zero_variance_groups += int(group_advantages(rewards)["zero_variance"])
    if used_files != set(manifest["files"]):
        raise ValueError("Rollout manifest contains unused or missing files")
    return {"manifest": manifest, "groups": len(group_ids), "trajectories": len(trajectory_ids),
            "zero_variance_groups": zero_variance_groups}


def rollout_batch(processor, row, root, max_tokens=8192):
    import torch
    from PIL import Image as PillowImage

    messages = copy.deepcopy(row["messages"])
    image_names = _message_images(messages)
    images = []
    for name in image_names:
        with PillowImage.open(safe_file(root, name)) as source:
            images.append(source.convert("RGB").copy())
    completion = {"role": "assistant", "content": row["response"]}
    prompt = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    full = processor.apply_chat_template(messages + [completion], tokenize=False, add_generation_prompt=False)
    prompt_batch = processor(text=[prompt], images=images, return_tensors="pt", padding=False)
    batch = processor(text=[full], images=images, return_tensors="pt", padding=False)
    prefix, tokens = prompt_batch["input_ids"], batch["input_ids"]
    if (tokens.ndim != 2 or tokens.shape[0] != 1 or tokens.shape[1] > max_tokens
            or prefix.shape[1] >= tokens.shape[1] or not torch.equal(tokens[:, :prefix.shape[1]], prefix)):
        raise ValueError("Rollout completion is not an exact bounded prompt continuation")
    completion_mask = torch.zeros_like(tokens, dtype=torch.bool)
    completion_mask[:, prefix.shape[1]:] = batch["attention_mask"][:, prefix.shape[1]:].bool()
    if not torch.any(completion_mask):
        raise ValueError("Rollout contains no generated action tokens")
    batch["completion_mask"] = completion_mask
    return batch


def completion_logps(model, batch):
    import torch

    inputs = {name: value for name, value in batch.items() if name != "completion_mask"}
    logits = model(**inputs, use_cache=False).logits[:, :-1].float()
    targets = batch["input_ids"][:, 1:]
    logps = torch.log_softmax(logits, dim=-1).gather(-1, targets.unsqueeze(-1)).squeeze(-1)
    mask = batch["completion_mask"][:, 1:]
    if logps.shape != mask.shape or not torch.any(mask):
        raise ValueError("Completion token log-probability alignment failed")
    return logps, mask


def verify_grpo_adapter(root, expected_hash, policy_identity, dataset_hash, driver_sha256):
    root = Path(root)
    manifest_path = root / "adapter-manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise ValueError("GRPO adapter manifest is missing")
    data = manifest_path.read_bytes()
    if digest(data) != expected_hash or canonical(json.loads(data)) != data:
        raise ValueError("GRPO adapter manifest identity changed")
    manifest = json.loads(data)
    required = {"schema_version", "objective", "base_model", "base_revision", "processor_revision",
                "parent_adapter_sha256", "rollout_dataset_sha256", "driver_sha256", "files",
                "hyperparameters", "versions"}
    if (set(manifest) != required or manifest["schema_version"] != 1 or manifest["objective"] != "grpo"
            or manifest["base_model"] != policy_identity["base_model"]
            or manifest["base_revision"] != policy_identity["base_revision"]
            or manifest["processor_revision"] != policy_identity["base_revision"]
            or manifest["parent_adapter_sha256"] != policy_identity["adapter_sha256"]
            or manifest["rollout_dataset_sha256"] != dataset_hash
            or manifest["driver_sha256"] != driver_sha256
            or not isinstance(manifest["files"], dict)
            or not {"adapter_config.json", "adapter_model.safetensors"} <= set(manifest["files"])):
        raise ValueError("GRPO adapter provenance differs from the admitted update")
    for name, expected in manifest["files"].items():
        path = root / name
        if (not isinstance(name, str) or Path(name).name != name or not SHA256.fullmatch(expected)
                or not path.is_file() or path.is_symlink() or digest(path.read_bytes()) != expected):
            raise ValueError("GRPO adapter file identity changed")
    return manifest


def _parent_adapter(root, expected_hash, policy_identity):
    if expected_hash is None:
        if root is not None:
            raise ValueError("Baseline rollout policy cannot load a parent adapter")
        return None
    if root is None:
        raise ValueError("Parent adapter bytes are required for an adapted rollout policy")
    root = Path(root)
    manifest_path = root / "adapter-manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise ValueError("Parent adapter manifest is missing")
    data = manifest_path.read_bytes()
    if digest(data) != expected_hash:
        raise ValueError("Parent adapter identity changed")
    manifest = json.loads(data)
    if (manifest.get("base_model") != policy_identity["base_model"]
            or manifest.get("base_revision") != policy_identity["base_revision"]
            or not isinstance(manifest.get("files"), dict)
            or not {"adapter_config.json", "adapter_model.safetensors"} <= set(manifest["files"])):
        raise ValueError("Parent adapter provenance differs from the rollout policy")
    for name, expected in manifest["files"].items():
        path = root / name
        if not path.is_file() or path.is_symlink() or digest(path.read_bytes()) != expected:
            raise ValueError("Parent adapter file identity changed")
    return root


def verify_parent_adapter(root, expected_hash, policy_identity):
    return _parent_adapter(root, expected_hash, policy_identity)


def _load_rollout_rows(root, manifest):
    groups = []
    for group in manifest["groups"]:
        advantages = group_advantages([member["reward"] for member in group["members"]])
        members = []
        for member, advantage in zip(group["members"], advantages["advantages"]):
            data = (root / member["trajectory"]).read_bytes()
            members.append({"id": member["id"], "advantage": advantage,
                            "rows": [json.loads(line) for line in data.splitlines() if line.strip()]})
        groups.append({"id": group["id"], "zero_variance": advantages["zero_variance"], "members": members})
    return groups


def train_grpo_dataset(root, dataset_hash, *, policy, context, expected_policy, expected_driver_sha256,
                       output, steps, parent_adapter=None, telemetry=None, experiment=None, seed=42):
    import torch
    from peft import LoraConfig, PeftModel, get_peft_model
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

    if type(steps) is not int or not 1 <= steps <= policy["model"]["maximum_optimizer_steps"]:
        raise ValueError("GRPO optimizer steps exceed the approved pilot")
    if telemetry is not None and (not isinstance(experiment, str) or not IDENTIFIER.fullmatch(experiment)):
        raise ValueError("GRPO telemetry requires a bounded experiment identity")
    verified = verify_rollout_dataset(root, dataset_hash, policy=policy, context=context,
                                      expected_policy=expected_policy,
                                      expected_driver_sha256=expected_driver_sha256)
    parent = _parent_adapter(parent_adapter, expected_policy["adapter_sha256"], expected_policy)
    root, output = Path(root), Path(output)
    output.mkdir(parents=True, exist_ok=False)
    torch.manual_seed(seed)
    processor = AutoProcessor.from_pretrained(expected_policy["base_model"],
                                              revision=expected_policy["base_revision"], trust_remote_code=False)

    def load_base():
        return Qwen3VLForConditionalGeneration.from_pretrained(
            expected_policy["base_model"], revision=expected_policy["base_revision"],
            torch_dtype=torch.bfloat16, attn_implementation="eager", trust_remote_code=False).to("cuda")

    if not torch.cuda.is_available():
        raise RuntimeError("The real GameWorld GRPO update requires a budget-admitted GPU worker")
    if parent is None:
        model = get_peft_model(load_base(), LoraConfig(
            r=8, lora_alpha=16, lora_dropout=0.0, target_modules=TARGETS,
            bias="none", task_type="CAUSAL_LM"))
        reference = load_base()
    else:
        model = PeftModel.from_pretrained(load_base(), str(parent), is_trainable=True)
        reference = PeftModel.from_pretrained(load_base(), str(parent), is_trainable=False)
    model.config.use_cache = False
    reference.config.use_cache = False
    reference.eval()
    trainable = {name: parameter for name, parameter in model.named_parameters() if parameter.requires_grad}
    if not trainable or any("lora_" not in name or "language_model.layers." not in name for name in trainable):
        raise ValueError("Only Qwen language-attention LoRA parameters may be trained")
    initial = {name: parameter.detach().cpu().clone() for name, parameter in trainable.items()}
    groups = _load_rollout_rows(root, verified["manifest"])
    samples = []
    for group in groups:
        if group["zero_variance"]:
            continue
        for member in group["members"]:
            for row in member["rows"]:
                samples.append({"id": member["id"], "advantage": member["advantage"],
                                "batch": rollout_batch(processor, row, root)})
    if not samples:
        raise ValueError("Every rollout group has zero reward variance; refusing a meaningless update")
    device = next(model.parameters()).device
    if device.type != "cuda":
        raise RuntimeError("GameWorld GRPO model did not load on CUDA")
    torch.cuda.reset_peak_memory_stats(device)
    old = []
    with torch.no_grad():
        for sample in samples:
            batch = {name: value.to(device) for name, value in sample["batch"].items()}
            logps, mask = completion_logps(reference, batch)
            old.append({"logps": logps.detach(), "mask": mask.detach()})
    optimizer = torch.optim.AdamW(trainable.values(), lr=5e-5, weight_decay=0.0)
    settings = policy["model"]["grpo"]
    history, telemetry_errors = [], []
    started = time.monotonic()
    for step in range(steps):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        metrics = {"policy_loss": 0.0, "reference_kl": 0.0, "clip_fraction": 0.0}
        total_loss = 0.0
        for sample, frozen in zip(samples, old):
            batch = {name: value.to(device) for name, value in sample["batch"].items()}
            current, mask = completion_logps(model, batch)
            advantage = torch.tensor([sample["advantage"]], dtype=current.dtype, device=device)
            loss, current_metrics = grpo_loss(
                current, frozen["logps"], frozen["logps"], mask, advantage,
                clip_epsilon=settings["clip_epsilon"], beta=settings["reference_kl_beta"])
            (loss / len(samples)).backward()
            total_loss += float(loss.detach()) / len(samples)
            for name in metrics:
                metrics[name] += current_metrics[name] / len(samples)
        gradients = [parameter.grad for parameter in trainable.values() if parameter.grad is not None]
        if not gradients or any(not torch.isfinite(gradient).all() for gradient in gradients):
            raise ValueError("GRPO produced missing or nonfinite adapter gradients")
        gradient_norm = torch.nn.utils.clip_grad_norm_(trainable.values(), 1.0, error_if_nonfinite=True)
        optimizer.step()
        row = {"timestamp_ns": time.time_ns(), "step": step + 1, "loss": total_loss,
               "gradient_norm": float(gradient_norm), **metrics}
        history.append(row)
        with (output / "loss.jsonl").open("ab") as handle:
            handle.write(canonical(row))
        if telemetry is not None:
            try:
                telemetry.record(f"grpo:{experiment}:{step + 1}", "gameworld-train",
                                 {"experiment": experiment, "phase": "train", "split": "train", "objective": "grpo"},
                                 {"gameworld_train_loss": total_loss, "gameworld_train_step": step + 1,
                                  "gameworld_train_policy_loss": metrics["policy_loss"],
                                  "gameworld_train_reference_kl": metrics["reference_kl"],
                                  "gameworld_train_clip_fraction": metrics["clip_fraction"],
                                  "gameworld_train_gradient_norm": float(gradient_norm)},
                                 step=step + 1, timestamp_ns=row["timestamp_ns"])
            except Exception as error:
                telemetry_errors.append({"step": step + 1, "error_type": type(error).__name__})
    changed = [name for name, parameter in trainable.items() if not torch.equal(initial[name], parameter.detach().cpu())]
    if not changed or any(not torch.isfinite(parameter).all() for parameter in trainable.values()):
        raise ValueError("GRPO did not produce a finite adapter update")
    model.eval()
    first = {name: value.to(device) for name, value in samples[0]["batch"].items()}
    with torch.no_grad():
        expected, expected_mask = completion_logps(model, first)
        expected = expected[expected_mask].detach().cpu()
    adapter = output / "adapter"
    model.save_pretrained(adapter, safe_serialization=True)
    files = {path.name: digest(path.read_bytes()) for path in adapter.iterdir() if path.is_file()}
    adapter_manifest = {
        "schema_version": 1, "objective": "grpo",
        "base_model": expected_policy["base_model"], "base_revision": expected_policy["base_revision"],
        "processor_revision": expected_policy["base_revision"],
        "parent_adapter_sha256": expected_policy["adapter_sha256"],
        "rollout_dataset_sha256": dataset_hash, "driver_sha256": expected_driver_sha256,
        "files": files,
        "hyperparameters": {"steps": steps, "learning_rate": 5e-5, "seed": seed,
                            "rank": 8, "alpha": 16, "targets": TARGETS,
                            "clip_epsilon": settings["clip_epsilon"],
                            "reference_kl_beta": settings["reference_kl_beta"]},
        "versions": {name: importlib.metadata.version(name)
                     for name in ("torch", "transformers", "peft", "accelerate")},
    }
    adapter_manifest_bytes = canonical(adapter_manifest)
    adapter_hash = digest(adapter_manifest_bytes)
    exclusive_write(adapter / "adapter-manifest.json", adapter_manifest_bytes, 0o400)
    del optimizer, reference, model
    torch.cuda.empty_cache()
    reloaded = PeftModel.from_pretrained(load_base(), str(adapter), is_trainable=False)
    reloaded.eval()
    reload_device = next(reloaded.parameters()).device
    reloaded_batch = {name: value.to(reload_device) for name, value in samples[0]["batch"].items()}
    with torch.no_grad():
        observed, observed_mask = completion_logps(reloaded, reloaded_batch)
        observed = observed[observed_mask].detach().cpu()
    reload_error = float((observed - expected).abs().max())
    if not torch.equal(observed_mask.cpu(), expected_mask.cpu()) or not torch.allclose(observed, expected, atol=1e-4, rtol=1e-4):
        raise ValueError("Saved GRPO adapter reload changes completion log probabilities")
    result = {
        "status": "complete", "objective": "grpo", "steps": steps,
        "losses": history, "adapter_manifest_sha256": adapter_hash,
        "rollout_dataset_sha256": dataset_hash, "groups": verified["groups"],
        "trajectories": verified["trajectories"], "zero_variance_groups": verified["zero_variance_groups"],
        "updated_parameter_tensors": len(changed), "reload_max_logprob_error": reload_error,
        "peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated(device),
        "seconds": time.monotonic() - started, "telemetry_errors": telemetry_errors,
        "benchmark_improvement_claimed": False,
    }
    exclusive_write(output / "result.json", canonical(result))
    return result
