"""Screenshot-only 2048 pilot contract, separate from the L-platform protocol."""

import json
from pathlib import Path

from fps_bench.qwen_protocol import messages

PROMPT = '''Play 2048. Merge matching tiles to make a tile of at least 32.
All tiles slide in the selected direction; equal tiles merge. A new tile appears
following each valid move. Observe the screenshot and choose one direction.
Return ONLY JSON with exactly these fields:
{"action":"key","key":"left"}
Allowed keys: up, down, left, right. No explanation or Markdown.
'''


def parse_action(text: str) -> dict:
    action = json.loads(text)
    if (not isinstance(action, dict) or set(action) != {"action", "key"}
            or action["action"] != "key"
            or action["key"] not in ("up", "down", "left", "right")):
        raise ValueError("expected exactly one arrow-key action")
    return action


def model_messages(image: Path, history: list[str]) -> list[dict]:
    result = messages(image, history[-4:])
    result[0]["content"] = PROMPT
    return result
