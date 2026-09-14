"""Static allowlist checks; these do not replace the offline Docker image smoke."""

from pathlib import Path
import re
import shlex

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "image/qwen-training/requirements.lock", "image/qwen-training/cache_model.py",
    "image/qwen-training/write_provenance.py", "image/qwen-training/smoke.py",
    "fps_bench/__init__.py", "fps_bench/evaluation_contract.py", "fps_bench/qwen_lora.py",
    "fps_bench/training_data.py", "fps_bench/gameworld_protocol.py", "fps_bench/qwen_protocol.py",
    "fps_bench/telemetry.py", "scripts/qwen_lora_worker.py", "scripts/qwen_lora_check.py",
}


def main():
    text = (ROOT / "image/Dockerfile.qwen-training").read_text().replace("\\\n", " ")
    assert re.search(r"^FROM python:3\.12\.13-slim-bookworm@sha256:[0-9a-f]{64}$", text, re.M)
    copied = set()
    for line in text.splitlines():
        if line.startswith("COPY "):
            parts = shlex.split(line)
            copied.update(parts[1:-1])
    assert copied == EXPECTED, copied ^ EXPECTED
    assert all((ROOT / name).is_file() for name in copied)
    assert "--require-hashes" in text
    assert "HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1" in text
    assert "PYTHONPATH=/app" in text
    ignore = (ROOT / "image/Dockerfile.qwen-training.dockerignore").read_text().splitlines()
    assert ignore[0] == "**"
    files = {line[1:] for line in ignore if line.startswith("!") and not line.endswith("/")}
    assert files == EXPECTED | {"image/Dockerfile.qwen-training"}
    assert not any("*" in name for name in copied)
    lock = (ROOT / "image/qwen-training/requirements.lock").read_text()
    assert "--hash=sha256:" in lock and "torch==2.9.0" in lock and "transformers==4.57.1" in lock
    print(f"Validated {len(copied)} explicit public COPY inputs, deny-by-default context, pinned base and dependency hashes")


if __name__ == "__main__":
    main()
