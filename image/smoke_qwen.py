"""Check desktop, game rendering and dependencies without starting model inference."""

import asyncio
import json
import socket
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import ImageGrab
from bench.run_in_sandbox import LocalSession, task_module
from fps_bench.qwen_baseline import source_manifest


async def main():
    with socket.create_connection(("127.0.0.1", 8000), timeout=5):
        pass
    screenshot = ImageGrab.grab(xdisplay=":1")
    assert min(screenshot.size) > 100, screenshot.size
    session = LocalSession(display=":1")
    html = task_module.game_html().replace(
        "</head>", "<style>#hud { display: none !important; }</style></head>", 1
    )
    pid = await session.launch_window(html=html, title="Qwen-Image-Smoke", width=800, height=600)
    try:
        for attempt in range(60):
            try:
                state = await session.execute_javascript(pid, "Boolean(window.__state && window.__progress)")
                if state:
                    break
            except Exception:
                pass
            await asyncio.sleep(0.5)
        else:
            raise RuntimeError("game did not become ready")
        assert await session.execute_javascript(pid, "getComputedStyle(document.querySelector('#hud')).display") == "none"
        assert await session.execute_javascript(pid, "document.querySelector('canvas').width > 0")
        provenance = source_manifest()
        assert provenance["git_commit"]
        print(json.dumps({"status": "ready", "source": provenance["git_commit"],
                          "driver": subprocess.check_output(["cua-driver", "--version"], text=True).strip(),
                          "screen": screenshot.size}))
    finally:
        await session.close_window(pid)


if __name__ == "__main__":
    asyncio.run(main())
