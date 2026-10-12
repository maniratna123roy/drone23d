"""Opt-in browser check of the CURRENT real classified scene; no uploads/training.

Starts isolated real API/Vite/Chrome processes, verifies served hashes and actual
class-color/hide/show pixels, then stops only those processes. Windows environment.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import httpx
import numpy as np
from PIL import Image
import websockets

from backend.tests.run_phase_d_acceptance import Browser, eventually
from pipeline.scene_publication import atomic_json


async def run(output: Path):
    output = output.resolve()
    if output.exists():
        raise ValueError("Use a fresh browser evidence directory")
    for port in (8012, 5176, 9230):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                raise ValueError(f"Test port {port} is busy; existing services are preserved")
    output.mkdir(parents=True)
    root = Path(__file__).resolve().parents[2]
    report = {"status": "FAILED", "mock_http_or_geometry_used": False, "checks": {}}
    children, logs = [], []
    ws = browser = None
    profile = output / "chrome-profile"
    try:
        env = {**os.environ, "PIPELINE_JOBS_DIR": str(output / "jobs"), "PYTHONIOENCODING": "utf-8"}
        for label, command, cwd, environment in [
            ("api", [sys.executable, "-B", "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8012"], root, env),
            ("vite", [shutil.which("node.exe") or "node", "node_modules/vite/bin/vite.js", "--host", "127.0.0.1", "--port", "5176", "--strictPort"], root / "frontend",
             {**env, "VITE_API_BASE_URL": "http://127.0.0.1:8012", "VITE_WS_URL": "ws://127.0.0.1:8012/ws/scene"}),
            ("chrome", [r"C:\Program Files\Google\Chrome\Application\chrome.exe", "--headless=new", "--no-first-run", "--no-default-browser-check", "--disable-background-networking", "--remote-debugging-port=9230", f"--user-data-dir={profile}", "about:blank"], root, env),
        ]:
            log = (output / f"{label}.log").open("w", encoding="utf-8")
            logs.append(log)
            children.append(subprocess.Popen(command, cwd=cwd, env=environment, stdout=log, stderr=log))

        async with httpx.AsyncClient(timeout=10) as client:
            async def api_ready():
                result = await client.get("http://127.0.0.1:8012/api/pipeline/scene")
                return result.json()["manifest"] if result.status_code == 200 else None

            manifest = await eventually(api_ready, "classification API")
            assert manifest["semantics"] == "CLASSIFIED_MULTIVIEW"
            for name, key in (("scene.splat", "splat_url"), ("scene.classes.u8", "classes_url")):
                response = await client.get("http://127.0.0.1:8012" + manifest[key])
                response.raise_for_status()
                assert hashlib.sha256(response.content).hexdigest() == manifest["sha256"][name]
            report["checks"]["served_hashes"] = True
            report["manifest"] = manifest

            async def debugger():
                pages = (await client.get("http://127.0.0.1:9230/json/list")).json()
                return next((page for page in pages if page["type"] == "page"), None)

            async def frontend_ready():
                return (await client.get("http://127.0.0.1:5176/demo")).status_code == 200

            await eventually(frontend_ready, "real frontend", timeout=90)
            page = await eventually(debugger, "installed Chrome")
            ws = await websockets.connect(page["webSocketDebuggerUrl"], max_size=64 * 1024 * 1024)
            browser = Browser(ws)
            for domain in ("Page", "Runtime", "Network"):
                await browser.call(domain + ".enable")
            await browser.call("Emulation.setDeviceMetricsOverride", width=1440, height=1000, deviceScaleFactor=1, mobile=False)
            await browser.call("Page.navigate", url="http://127.0.0.1:5176/demo")

            async def rendered():
                return await browser.evaluate("!!document.querySelector('[aria-label=\"Semantic classification\"]') && document.querySelectorAll('canvas').length === 1")

            await eventually(rendered, "classified scene rendering", timeout=90)
            await asyncio.sleep(2)
            bounds = await browser.evaluate("(()=>{const r=document.querySelector('canvas').getBoundingClientRect();return [r.x+10,r.y+10,r.right-10,r.bottom-65]})()")
            box = tuple(map(int, bounds))

            async def capture(name):
                await asyncio.sleep(.7)
                path = output / name
                await browser.screenshot(path)
                return np.asarray(Image.open(path).convert("RGB").crop(box)).astype(float)

            rgb = await capture("01-photographic.png")
            assert (rgb.max(axis=2) > 20).mean() > .02
            panel = "document.querySelector('[aria-label=\"Semantic classification\"]')"
            await browser.evaluate(f"{panel}.querySelectorAll('input')[0].click()")
            colored = await capture("02-class-colors.png")
            delta = float(np.abs(colored - rgb).mean())
            assert delta > 1, "Class colors did not change actual viewport pixels"
            report["color_mean_pixel_change"] = delta
            report["checks"]["class_colors_render"] = True

            await browser.evaluate(f"{panel}.querySelectorAll('input')[1].click()")
            hidden = await capture("03-structures-hidden.png")
            delta = float(np.abs(hidden - colored).mean())
            assert delta > 1, "Structure visibility did not change actual viewport pixels"
            report["hide_structure_mean_pixel_change"] = delta
            report["checks"]["structure_toggle_renders"] = True

            await browser.evaluate(f"[...{panel}.querySelectorAll('input')].slice(1).filter(i=>i.checked).forEach(i=>i.click())")
            empty = await capture("04-all-classes-hidden.png")
            assert (empty.max(axis=2) > 20).mean() < .001, "Hidden classes still rendered"
            report["checks"]["all_classes_can_hide_including_unknown"] = True
            await browser.evaluate(f"[...{panel}.querySelectorAll('input')].slice(1).forEach(i=>i.click())")
            restored = await capture("05-classes-restored.png")
            assert np.abs(restored - colored).mean() < .1
            report["checks"]["show_restores_same_geometry"] = True

            await browser.call("Page.reload")
            await eventually(rendered, "classified scene after reload")
            await capture("06-reloaded.png")
            assert "Viewer error" not in await browser.text()
            exceptions = [event for event in browser.events if event["method"] == "Runtime.exceptionThrown"]
            assert not exceptions, exceptions
            report["checks"]["reload_and_no_js_exceptions"] = True
            report["status"] = "PASSED"
            print(report["checks"], flush=True)
    finally:
        atomic_json(output / "browser-acceptance.json", report)
        if ws:
            await ws.close()
        if browser:
            browser.reader.cancel()
        for child in reversed(children):
            if child.poll() is None:
                subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                child.wait(timeout=15)
        for log in logs:
            log.close()
        await asyncio.sleep(1)
        shutil.rmtree(profile, ignore_errors=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    asyncio.run(run(parser.parse_args().output))
