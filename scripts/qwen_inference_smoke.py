"""Test live image inference, not game performance; invoking this can start a GPU.

python3 scripts/qwen_inference_smoke.py --image /path/to/game.png
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fps_bench.qwen_baseline import DEFAULT_CONFIG, endpoint, request, sha256, write_json
from fps_bench.qwen_protocol import messages, parse_action


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    payload = {'model': config['served_model'], 'messages': messages(args.image, []),
               'temperature': config['temperature'], 'seed': config['seed'],
               'max_tokens': config['max_tokens']}
    started = time.monotonic()
    print('Waiting for inference endpoint (may cold-start a GPU)...', flush=True)
    models = request(endpoint(), '/models', 900)
    if config['served_model'] not in [model['id'] for model in models['data']]:
        raise RuntimeError('endpoint model mismatch')
    print('Live model discovery passed.', flush=True)
    response = request(endpoint(), '/chat/completions', config['request_timeout_seconds'], payload)
    action = parse_action(response['choices'][0]['message']['content'])
    try:
        with urllib.request.urlopen(endpoint() + '/models', timeout=30):
            raise RuntimeError('endpoint accepted an unauthenticated request')
    except urllib.error.HTTPError as error:
        if error.code != 401:
            raise
    result = {'kind': 'inference-smoke-only-not-game-baseline', 'config': config,
              'response': response, 'parsed_action': action, 'unauthenticated_status': 401,
              'seconds_including_cold_start': time.monotonic() - started,
              'image_sha256': sha256(args.image), 'image': str(args.image),
              'note': 'No cua-driver action was executed; no game success score was measured.'}
    if args.output:
        if args.output.exists():
            raise FileExistsError(args.output)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_json(args.output, result)
    print(json.dumps({'action': action, 'usage': response.get('usage'),
                      'unauthenticated_status': 401}, indent=2))


if __name__ == '__main__':
    main()
