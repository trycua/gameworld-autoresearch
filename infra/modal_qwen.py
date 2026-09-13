"""Authenticated, scale-to-zero Qwen3-VL inference for the L-platform pilot."""

import json
import os
import subprocess
from pathlib import Path

import modal

CONFIG_PATH = Path(__file__).resolve().parents[1] / "configs/qwen-lplatform-baseline.json"
CONFIG = json.loads(CONFIG_PATH.read_text())
app = modal.App("gameworld-qwen-baseline")
image = (
    modal.Image.from_registry("nvidia/cuda:12.9.0-devel-ubuntu22.04", add_python="3.12")
    .entrypoint([])
    .uv_pip_install(f"vllm=={CONFIG['vllm_version']}", "huggingface-hub==0.36.0")
    .env({"HF_HOME": "/cache/huggingface"})
    .add_local_file(CONFIG_PATH, "/configs/qwen-lplatform-baseline.json", copy=True)
)
cache = modal.Volume.from_name("gameworld-qwen-hf-cache", create_if_missing=True)


@app.function(
    image=image,
    gpu=CONFIG["gpu"],
    volumes={"/cache": cache},
    secrets=[modal.Secret.from_name("gameworld-qwen-api")],
    max_containers=1,
    scaledown_window=300,
    timeout=3600,
)
@modal.web_server(8000, startup_timeout=900)
def serve():
    api_key = os.environ.get("QWEN_API_KEY", "")
    if len(api_key) < 32:
        raise ValueError("gameworld-qwen-api must contain QWEN_API_KEY (32+ characters)")
    subprocess.Popen(
        [
            "vllm", "serve", CONFIG["model"],
            "--revision", CONFIG["revision"],
            "--tokenizer-revision", CONFIG["revision"],
            "--served-model-name", CONFIG["served_model"],
            "--host", "0.0.0.0", "--port", "8000",
            "--dtype", "bfloat16",
            "--max-model-len", str(CONFIG["max_model_len"]),
            "--max-num-seqs", "1",
            "--gpu-memory-utilization", "0.85",
            "--limit-mm-per-prompt", '{"image": 1, "video": 0}',
            "--seed", str(CONFIG["seed"]),
            "--generation-config", "vllm",
        ] + (["--enforce-eager"] if CONFIG["enforce_eager"] else []),
        env={**os.environ, "VLLM_API_KEY": api_key},
    )
