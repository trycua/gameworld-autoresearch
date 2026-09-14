"""Cache the public pinned model without forwarding any Hugging Face credentials."""

import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

from huggingface_hub import HfApi, snapshot_download

MODEL = "Qwen/Qwen3-VL-2B-Instruct"
REVISION = "89644892e4d85e24eaac8bacfd4f463576704203"


def file_hash(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-root", type=Path, default=Path("/model-cache"))
    args = parser.parse_args()
    info = HfApi(token=False).model_info(MODEL, revision=REVISION, files_metadata=True)
    if info.sha != REVISION or info.card_data.license != "apache-2.0":
        raise ValueError("Upstream model revision or declared license changed")
    snapshot = Path(snapshot_download(MODEL, revision=REVISION, cache_dir=args.cache_root / "hub", token=False,
                                      allow_patterns=["*.json", "*.safetensors", "*.txt", "README.md"], max_workers=2))
    files = {}
    for item in info.siblings:
        path = snapshot / item.rfilename
        if not path.is_file():
            continue
        if not path.resolve().is_relative_to(args.cache_root.resolve()):
            raise ValueError("Model cache symlink escapes its root")
        actual = file_hash(path)
        if item.lfs is not None and actual != item.lfs.sha256:
            raise ValueError("Downloaded model weights differ from upstream LFS identity")
        files[str(path.relative_to(args.cache_root))] = actual
    if not (snapshot / "model.safetensors").is_file():
        raise ValueError("Pinned model weights are missing")
    with urllib.request.urlopen("https://www.apache.org/licenses/LICENSE-2.0.txt", timeout=30) as response:
        license_text = response.read(32768)
    if b"Apache License" not in license_text or b"Version 2.0" not in license_text:
        raise ValueError("Unexpected model license text")
    (args.cache_root / "MODEL-LICENSE.txt").write_bytes(license_text)
    manifest = {"model": MODEL, "revision": REVISION, "license": "apache-2.0", "files": files,
                "license_sha256": hashlib.sha256(license_text).hexdigest()}
    (args.cache_root / "model-manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"model": MODEL, "revision": REVISION, "verified_files": len(files)}))


if __name__ == "__main__":
    main()
