"""Offline localhost vLLM compatibility probe for one verified language LoRA."""

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
import urllib.error
import urllib.request


def main():
    root = Path('/input')
    output = Path('/output')
    output.mkdir(exist_ok=False)
    config = json.loads((root / 'request.json').read_bytes())
    if importlib.metadata.version('vllm') != '0.13.0':
        raise ValueError('Pinned vLLM version mismatch')
    manifest = json.loads((root / 'adapter/adapter-manifest.json').read_bytes())
    for name, expected in manifest['files'].items():
        if hashlib.sha256((root / 'adapter' / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Adapter payload mismatch')
    api_key = secrets.token_urlsafe(32)
    command = ['vllm', 'serve', config['model'], '--revision', config['revision'],
               '--tokenizer-revision', config['revision'], '--served-model-name', config['served_model'],
               '--host', '127.0.0.1', '--port', '8000', '--dtype', 'bfloat16',
               '--max-model-len', '8192', '--max-num-seqs', '1', '--gpu-memory-utilization', '0.85',
               '--limit-mm-per-prompt', '{"image":1,"video":0}', '--seed', '42',
               '--generation-config', 'vllm', '--enforce-eager', '--enable-lora',
               '--max-loras', '1', '--max-lora-rank', '8', '--lora-modules', 'trained=/input/adapter']

    def request(path, payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        query = urllib.request.Request('http://127.0.0.1:8000' + path, data=data,
            headers={'Authorization': 'Bearer ' + api_key, 'Content-Type': 'application/json'})
        with urllib.request.urlopen(query, timeout=120) as response:
            return json.load(response)

    started = time.monotonic()
    with (output / 'server.log').open('w') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   env={**os.environ, 'VLLM_API_KEY': api_key})
        try:
            while True:
                if process.poll() is not None:
                    raise RuntimeError('vLLM exited during startup; see server.log')
                try:
                    models = request('/v1/models')
                    break
                except (urllib.error.URLError, TimeoutError):
                    if time.monotonic() - started > 480:
                        raise TimeoutError('vLLM startup exceeded 480 seconds')
                    time.sleep(2)
            if not {config['served_model'], 'trained'} <= {item['id'] for item in models['data']}:
                raise ValueError('Static adapter not registered')
            results = []
            for model in (config['served_model'], 'trained'):
                payload = {**config['payload'], 'model': model, 'logprobs': True}
                request_started = time.monotonic()
                response = request('/v1/chat/completions', payload)
                results.append({'model': model, 'seconds': time.monotonic() - request_started, 'response': response})
            report = {'purpose': 'historical compatibility only, not frozen evaluation',
                      'vllm_version': importlib.metadata.version('vllm'), 'models': models,
                      'results': results, 'elapsed_seconds': time.monotonic() - started,
                      'worker_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
            (output / 'result.json').write_text(json.dumps(report, sort_keys=True))
            print(json.dumps({'status': 'complete', 'models': [item['model'] for item in results]}), flush=True)
        finally:
            process.terminate()
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)


if __name__ == '__main__':
    main()
