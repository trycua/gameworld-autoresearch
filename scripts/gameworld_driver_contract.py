"""Exercise focus, held-key, key-release and mouse delivery on the X11 desktop."""

import argparse
import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import uuid

from fps_bench.evaluation_contract import canonical, exclusive_write
from fps_bench.gameworld_baseline import driver_command


HTML = """<!doctype html><html><head><title>Driver Contract</title></head>
<body tabindex="0" style="margin:0;width:100vw;height:100vh;background:#132;color:white">
<script>
window.contractState={focused:false,pressed:[],downs:[],ups:[],moves:[]};
addEventListener('focus',()=>contractState.focused=document.hasFocus());
addEventListener('blur',()=>contractState.focused=document.hasFocus());
addEventListener('keydown',e=>{if(!contractState.pressed.includes(e.key))contractState.pressed.push(e.key);contractState.downs.push({key:e.key,t:e.timeStamp,trusted:e.isTrusted});});
addEventListener('keyup',e=>{contractState.pressed=contractState.pressed.filter(k=>k!==e.key);contractState.ups.push({key:e.key,t:e.timeStamp,trusted:e.isTrusted});});
addEventListener('mousemove',e=>contractState.moves.push({x:e.clientX,y:e.clientY,mx:e.movementX,my:e.movementY,trusted:e.isTrusted}));
</script></body></html>"""


async def run(output, driver):
    from playwright.async_api import async_playwright

    display = os.environ.get("DISPLAY", ":1")
    with tempfile.TemporaryDirectory(prefix="driver-contract-") as directory:
        root = Path(directory)
        page_path = root / "index.html"
        page_path.write_text(HTML)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        server = subprocess.Popen([
            "python3", "-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory", str(root),
        ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        socket = str(root / "driver.sock")
        daemon = subprocess.Popen([
            driver, "serve", "--socket", socket, "--dangerously-bypass-approvals", "--no-permissions-gate",
        ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            for _ in range(100):
                if daemon.poll() is not None:
                    raise RuntimeError("Candidate driver daemon exited")
                try:
                    await driver_command(driver, socket, "status")
                    break
                except (RuntimeError, ValueError):
                    await asyncio.sleep(0.1)
            else:
                raise RuntimeError("Candidate driver readiness timeout")
            for _ in range(100):
                if server.poll() is not None:
                    raise RuntimeError("Contract HTTP server exited")
                try:
                    _, writer = await asyncio.open_connection("127.0.0.1", port)
                    writer.close()
                    await writer.wait_closed()
                    break
                except OSError:
                    await asyncio.sleep(0.05)
            else:
                raise RuntimeError("Contract HTTP server readiness timeout")
            session = "contract-" + uuid.uuid4().hex

            async def call(tool, arguments):
                return await driver_command(driver, socket, "call", tool,
                                            json.dumps({**arguments, "session": session}))

            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=False, args=[
                    "--no-sandbox", "--disable-dev-shm-usage", "--window-position=0,0", "--window-size=800,600",
                ])
                try:
                    context = await browser.new_context(viewport={"width": 780, "height": 500})
                    page = await context.new_page()
                    await page.goto(f"http://127.0.0.1:{port}", wait_until="load")
                    title = "Driver-Contract-" + session
                    await page.evaluate("title => document.title = title", title)
                    target = None
                    for _ in range(50):
                        data = await call("list_windows", {})
                        windows = data.get("windows", data.get("structuredContent", {}).get("windows", []))
                        target = next((window for window in windows if title in window.get("title", "")), None)
                        if target:
                            break
                        await asyncio.sleep(0.1)
                    if not target:
                        raise RuntimeError("Candidate driver cannot discover the contract window")
                    target = {"pid": target["pid"], "window_id": target.get("window_id", target.get("id")),
                              "delivery_mode": "foreground"}
                    await call("click", {**target, "x": 400, "y": 300})
                    await asyncio.sleep(0.2)
                    focused = bool(await page.evaluate("document.hasFocus()"))
                    await call("press_key", {**target, "key": "w", "hold_ms": 200})
                    await asyncio.sleep(0.1)
                    await call("move_cursor", {"x": 300, "y": 300, "scope": "desktop"})
                    await call("move_cursor", {"x": 430, "y": 300, "scope": "desktop"})
                    await asyncio.sleep(0.2)
                    state = await page.evaluate("window.contractState")
                finally:
                    await browser.close()
            downs = [event for event in state["downs"] if event["key"].lower() == "w" and event["trusted"]]
            ups = [event for event in state["ups"] if event["key"].lower() == "w" and event["trusted"]]
            held = bool(downs and ups and ups[-1]["t"] - downs[-1]["t"] >= 150)
            released = "w" not in [key.lower() for key in state["pressed"]] and bool(ups)
            moved = any(event["trusted"] and (event["mx"] or event["my"]) for event in state["moves"])
            checks = {"focus": focused, "held-keys": held, "key-release": released, "mouse-delivery": moved}
            if not all(checks.values()):
                raise RuntimeError(f"Candidate driver desktop contract failed: {checks}")
            result = {"status": "passed", "checked_at": time.time(), "display": display,
                      "checks": checks, "event_counts": {"downs": len(downs), "ups": len(ups),
                                                           "moves": len(state["moves"])}}
            exclusive_write(output, canonical(result))
            return result
        finally:
            for process in (daemon, server):
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--driver", default="/usr/local/bin/cua-driver")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.output, args.driver)), sort_keys=True))


if __name__ == "__main__":
    main()
