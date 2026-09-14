"""Verify public image provenance and processor availability with networking disabled."""

import hashlib
import json
from pathlib import Path

from transformers import AutoProcessor
from fps_bench.qwen_lora import BASE_MODEL, BASE_REVISION

root = Path("/app")
manifest = json.loads((root / "training-image.json").read_bytes())
for name, expected in manifest["source_hashes"].items():
    path = root / name
    if not path.resolve().is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError("Training source identity changed")
cache = Path("/model-cache")
model_manifest = cache / "model-manifest.json"
if hashlib.sha256(model_manifest.read_bytes()).hexdigest() != manifest["model_manifest_sha256"]:
    raise ValueError("Cached model manifest changed")
model = json.loads(model_manifest.read_bytes())
if model["model"] != BASE_MODEL or model["revision"] != BASE_REVISION:
    raise ValueError("Wrong cached model revision")
for name, expected in model["files"].items():
    path = cache / name
    if not path.resolve().is_relative_to(cache):
        raise ValueError("Model cache escapes its root")
    with path.open("rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() != expected:
            raise ValueError("Cached model artifact changed")
if hashlib.sha256((cache / "MODEL-LICENSE.txt").read_bytes()).hexdigest() != model["license_sha256"]:
    raise ValueError("Model license changed")
if Path("/dataset").exists() or Path("/output").exists():
    raise ValueError("Public image must not bake in dataset or experiment output directories")
processor = AutoProcessor.from_pretrained(BASE_MODEL, revision=BASE_REVISION, local_files_only=True, trust_remote_code=False)
print(json.dumps({"source_revision": manifest["source_revision"], "cached_model_revision": model["revision"],
                  "processor": type(processor).__name__, "gpu_training_verified": False}))
