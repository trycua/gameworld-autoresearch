"""Versioned visual-policy contract; no game state or driver dependencies."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

PROMPT = """You control a first-person game. Reach the glowing goal at the far end
of the L-shaped platform without falling off. Falling resets you to the start.
Observe the screenshot and choose exactly one action. The mouse is already
focused on the game. Movement keys are held for a bounded duration.
Return ONLY a JSON object, no Markdown or explanation, using one of:
{"action":"key","key":"w","hold_ms":300}
{"action":"turn","dx":100}
{"action":"wait","ms":150}
Keys allowed: w, a, s, d. hold_ms: integer 120..500.
turn dx: integer -400..400, nonzero; positive looks right, negative looks left.
wait ms: integer 50..500. Use the visual scene, not imagined coordinates.
"""


def parse_action(text: str) -> dict[str, Any]:
    action = json.loads(text)
    if not isinstance(action, dict):
        raise ValueError("action must be an object")
    kind = action.get("action")
    fields = {
        "key": {"action", "key", "hold_ms"},
        "turn": {"action", "dx"},
        "wait": {"action", "ms"},
    }
    if not isinstance(kind, str) or kind not in fields or set(action) != fields[kind]:
        raise ValueError("unknown action or unexpected fields")
    if kind == "key":
        if action["key"] not in ("w", "a", "s", "d"):
            raise ValueError("unsupported key")
        name, lower, upper = "hold_ms", 120, 500
    elif kind == "turn":
        name, lower, upper = "dx", -400, 400
        if action[name] == 0:
            raise ValueError("turn must be nonzero")
    else:
        name, lower, upper = "ms", 50, 500
    if type(action[name]) is not int or not lower <= action[name] <= upper:
        raise ValueError(f"{name} must be an integer in {lower}..{upper}")
    return action


def messages(image: Path, previous: list[str]) -> list[dict[str, Any]]:
    data_url = "data:image/png;base64," + base64.b64encode(image.read_bytes()).decode()
    return [
        {"role": "system", "content": PROMPT},
        {"role": "user", "content": [
            {"type": "text", "text": "Recent responses (invalid responses do nothing):\n"
             + "\n".join(previous) + "\nChoose the next action from this screenshot."},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]},
    ]
