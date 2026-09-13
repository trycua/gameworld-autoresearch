"""Offline protocol/client smoke tests: python3 scripts/qwen_baseline_check.py."""

import asyncio
import base64
import json
import io
from contextlib import redirect_stdout
import os
import sys
import tempfile
import threading
import unittest
from types import ModuleType
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fps_bench.qwen_baseline import collect, endpoint, request, write_json, source_file_hashes, source_manifest
from fps_bench.qwen_protocol import PROMPT, messages, parse_action


class ProtocolChecks(unittest.TestCase):
    def test_valid_actions(self):
        for action in (
            {"action": "key", "key": "w", "hold_ms": 120},
            {"action": "key", "key": "d", "hold_ms": 500},
            {"action": "turn", "dx": -400},
            {"action": "turn", "dx": 400},
            {"action": "wait", "ms": 50},
        ):
            self.assertEqual(parse_action(json.dumps(action)), action)

    def test_rejects_unbounded_or_executable_actions(self):
        for text in (
            '[]', 'null', 'not json', '```json\n{"action":"wait","ms":50}\n```',
            '{"action":"key","key":"Return","hold_ms":200}',
            '{"action":"key","key":"w","hold_ms":501}',
            '{"action":"turn","dx":0}', '{"action":"turn","dx":401}',
            '{"action":"turn","dx":true}', '{"action":"wait","ms":50.0}',
            '{"action":"wait","ms":50,"shell":"whoami"}',
            '{"action":"shell","command":"whoami"}', '{"action":[]}',
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_action(text)

    def test_model_sees_only_prompt_image_and_history(self):
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / 'frame.png'
            image.write_bytes(b'example-image')
            history = ['{"action":"turn","dx":10}']
            result = messages(image, history)
            self.assertEqual(result[0], {"role": "system", "content": PROMPT})
            content = result[1]["content"]
            self.assertIn(history[0], content[0]["text"])
            self.assertEqual(base64.b64decode(content[1]["image_url"]["url"].split(',')[1]), b'example-image')
            self.assertNotIn('evaluator', json.dumps(result))
            self.assertNotIn('__state', json.dumps(result))

    def test_endpoint_rejects_credentials_and_insecure_remote(self):
        for url in ('http://remote/v1', 'https://user:password@remote/v1',
                    'https://remote/v1?secret=abc', 'https://remote'):
            with self.subTest(url=url), patch.dict(os.environ, {"QWEN_BASE_URL": url, "QWEN_API_KEY": "test"}):
                with self.assertRaises(ValueError):
                    endpoint()

    def test_container_provenance_detects_source_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'fps_bench').mkdir()
            source = root / 'fps_bench/policy.py'
            source.write_text('value = 1\n')
            with patch('fps_bench.qwen_baseline.ROOT', root):
                (root / 'image-source.json').write_text(json.dumps({
                    'git_commit': 'a' * 40, 'files_sha256': source_file_hashes(),
                }))
                self.assertFalse(source_manifest()['image_source_modified'])
                source.write_text('value = 2\n')
                self.assertTrue(source_manifest()['image_source_modified'])
                self.assertEqual(source_manifest()['git_commit'], 'a' * 40)

    def test_atomic_artifact(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'manifest.json'
            write_json(path, {"status": "running"})
            write_json(path, {"status": "failed"})
            self.assertEqual(json.loads(path.read_text()), {"status": "failed"})
            self.assertFalse(path.with_suffix('.json.tmp').exists())

    def test_authenticated_inference_client(self):
        received = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                received.append((self.path, self.headers['Authorization'],
                                 json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"choices":[{"message":{"content":"ok"}}]}')

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.dict(os.environ, {"QWEN_API_KEY": "test-secret"}):
                result = request(f'http://127.0.0.1:{server.server_port}/v1', '/chat/completions', 5,
                                 {"model": "test-model"})
            self.assertEqual(result['choices'][0]['message']['content'], 'ok')
            self.assertEqual(received, [('/v1/chat/completions', 'Bearer test-secret', {"model": "test-model"})])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


class CollectorChecks(unittest.TestCase):
    def exercise_collector(self, fail=False):
        windows = []
        closed = []
        requests = []

        class Session:
            def __init__(self, display):
                pass

            async def launch_window(self, **kwargs):
                self.reads = 0
                windows.append(kwargs)
                return len(windows)

            async def execute_javascript(self, pid, javascript):
                return "none" if "getComputedStyle" in javascript else 1

            async def close_window(self, pid):
                closed.append(pid)

        class Agent:
            def __init__(self, window_title):
                self.window_title = window_title

            async def _screen_size(self, session):
                pass

            async def _resolve_window(self, session):
                return {"pid": 1, "frame": {"x": 0, "y": 0, "width": 10, "height": 10}}

            async def _focus(self, session, target):
                await self._call(session, "click", {})

            async def _state(self, session, pid):
                session.reads += 1
                return {"reached": session.reads > 1, "falls": 0, "private_state": 123}

        class Image:
            size = (1024, 768)

            def crop(self, bbox):
                return self

            def save(self, path):
                path.write_bytes(b"mock screenshot, not a real observation")

        bench = ModuleType("bench.run_in_sandbox")
        bench.LocalSession = Session
        bench.task_module = type("Task", (), {
            "game_html": staticmethod(lambda: "<head></head><body></body>"),
            "WINDOW_W": 800, "WINDOW_H": 600,
        })
        agent = ModuleType("fps_bench.agent")
        agent.CuaDriverAgent = Agent
        agent.RAD_PER_PX = 0.002
        pillow = ModuleType("PIL")
        pillow.ImageGrab = type("Grab", (), {"grab": staticmethod(lambda **kwargs: Image())})

        def respond(base, route, timeout, payload):
            requests.append(payload)
            return {"choices": [{"message": {"content": '{"action":"wait","ms":50}'}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5}}

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'run'
            output.mkdir()
            binary = Path(temporary) / 'fake-driver'
            binary.write_text(
                '#!/usr/bin/env python3\nimport sys,time\n'
                'if sys.argv[1] == "serve": time.sleep(60)\n'
                + 'print(' + repr(json.dumps({'isError': fail})) + ')\n'
            )
            binary.chmod(0o700)
            config = {"episodes": 2, "max_steps": 2, "settle_ms": 0,
                      "episode_timeout_seconds": 30, "request_timeout_seconds": 5,
                      "history_actions": 4, "served_model": "mock", "seed": 42,
                      "temperature": 0, "max_tokens": 128}
            with patch.dict(sys.modules, {"bench.run_in_sandbox": bench,
                                          "fps_bench.agent": agent, "PIL": pillow}), \
                 patch.dict(os.environ, {"DISPLAY": ":99", "QWEN_BASE_URL": "http://localhost/v1",
                                         "QWEN_API_KEY": "test"}), \
                 patch('fps_bench.qwen_baseline.request', side_effect=respond):
                if fail:
                    with self.assertRaisesRegex(RuntimeError, 'driver .* failed'):
                        asyncio.run(collect(None, config, str(binary), output))
                else:
                    with redirect_stdout(io.StringIO()):
                        result = asyncio.run(collect(None, config, str(binary), output))
                    self.assertEqual(result['episodes'], 2)
                    self.assertEqual(result['score'], 1)
                    self.assertNotEqual(windows[0]['title'], windows[1]['title'])
                    for window in windows:
                        self.assertIn('#hud { display: none !important; }', window['html'])
                    for payload in requests:
                        self.assertNotIn('private_state', json.dumps(payload))
                    row = json.loads((output / 'episode-000/trajectory.jsonl').read_text())
                    self.assertEqual(row['evaluator']['before']['private_state'], 123)
                    self.assertEqual(row['reward'], 1)
                    self.assertTrue(row['done'])
                self.assertEqual(len(closed), len(windows))

    def test_mocked_rollout_artifacts_and_isolation(self):
        self.exercise_collector()

    def test_driver_failure_aborts_and_closes_window(self):
        self.exercise_collector(fail=True)


if __name__ == '__main__':
    unittest.main()
