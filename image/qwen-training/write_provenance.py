"""Record only explicitly copied public source files and the cached model identity."""

import hashlib
import importlib.metadata
import json
import os
import re
from pathlib import Path

if not re.fullmatch(r"[0-9a-f]{40}", os.environ.get("SOURCE_REVISION", "")):
    raise ValueError("An exact source commit is required")
root = Path("/app")
source = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
          for directory in (root / "fps_bench", root / "scripts", root / "image")
          for path in directory.rglob("*") if path.is_file() and "__pycache__" not in path.parts}
model = Path("/model-cache/model-manifest.json")
manifest = {"schema_version": 1, "source_revision": os.environ["SOURCE_REVISION"], "source_hashes": source,
            "model_manifest_sha256": hashlib.sha256(model.read_bytes()).hexdigest(),
            "versions": {name: importlib.metadata.version(name)
                         for name in ("torch", "torchvision", "transformers", "peft", "accelerate", "huggingface-hub")}}
(root / "training-image.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
