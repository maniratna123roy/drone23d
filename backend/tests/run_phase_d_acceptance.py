"""Opt-in, REAL video/browser acceptance. Not collected by pytest.

Requires the actual backend and frontend already running, installed Chrome,
and a user-authorized footage path. No mocked HTTP, model, camera, or geometry.
It creates a real reconstruction job and publishes only if production gates pass.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
from pathlib import Path
import shutil
import socket as socket_module
import subprocess
import time
import uuid

import httpx
import numpy as np
from PIL import Image
import websockets


class Browser:
    def __init__(self, socket):
        self.socket = socket
        self.sequence = 0
        self.pending = {}
        self.events = []
        self.reader = asyncio.create_task(self.listen())

    async def listen(self):
        async for raw in self.socket:
            message = json.loads(raw)
            if "id" in message:
                future = self.pending.pop(message["id"], None)
                if future is not None and not future.done():
                    if "error" in message:
                        future.set_exception(RuntimeError(str(message["error"])))
                    else:
                        future.set_result(message.get("result", {}))
            elif message.get("method") in ("Runtime.exceptionThrown", "Runtime.consoleAPICalled", "Network.requestWillBeSent", "Network.responseReceived"):
                self.events.append(message)

    async def call(self, method, **params):
        self.sequence += 1
        future = asyncio.get_running_loop().create_future()
        self.pending[self.sequence] = future
        await self.socket.send(json.dumps({"id": self.sequence, "method": method, "params": params}))
        return await asyncio.wait_for(future, 30)

    async def evaluate(self, expression):
        result = await self.call("Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True)
        if "exceptionDetails" in result:
            raise RuntimeError(str(result["exceptionDetails"]))
        return result.get("result", {}).get("value")

    async def text(self):
        return await self.evaluate("document.body.innerText")

    async def upload(self, path):
        document = await self.call("DOM.getDocument")
        node = await self.call("DOM.querySelector", nodeId=document["root"]["nodeId"], selector="input[type=file]")
        assert node["nodeId"], "Upload file input missing"
        await self.call("DOM.setFileInputFiles", nodeId=node["nodeId"], files=[str(Path(path).resolve())])

    async def screenshot(self, path):
        result = await self.call("Page.captureScreenshot", format="png")
        path.write_bytes(base64.b64decode(result["data"]))


async def eventually(check, label, timeout=60):
    started = time.monotonic()
    last = None
    while time.monotonic() - started < timeout:
        try:
            value = await check()
            if value:
                return value
        except (httpx.HTTPError, OSError, RuntimeError) as exc:
            last = str(exc)
        await asyncio.sleep(.3)
    raise RuntimeError(f"Timed out waiting for {label}: {last}")


async def run(args):
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Choose a fresh acceptance output directory; existing evidence is preserved")
    output.mkdir(parents=True, exist_ok=True)
    video = args.video.resolve()
    assert video.is_file(), "Authorized video path missing"
    report = {"status": "FAILED", "real_video": str(video), "video_sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
              "mock_http_or_geometry_used": False, "checks": {}, "timeline": []}
    profile = output / f"chrome-profile-{uuid.uuid4().hex}"
    chrome = None
    socket = browser = None
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(args.api + "/api/pipeline/scene")
            response.raise_for_status()
            previous_manifest = response.json()["manifest"]
            if (await client.get(args.api + "/api/pipeline/status")).json()["status"] == "processing":
                raise RuntimeError("Another real reconstruction is active; acceptance will not interrupt it")
            with socket_module.socket() as probe:
                if probe.connect_ex(("127.0.0.1", args.debug_port)) == 0:
                    raise RuntimeError("The browser debugging port is already in use. Choose a free --debug-port; this test will not attach to another browser profile.")
            chrome = subprocess.Popen([
                str(args.chrome), "--headless=new", "--no-first-run", "--no-default-browser-check",
                "--disable-background-networking", f"--remote-debugging-port={args.debug_port}",
                f"--user-data-dir={profile}", "about:blank",
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            async def debugger():
                pages = (await client.get(f"http://127.0.0.1:{args.debug_port}/json/list")).json()
                return next((page for page in pages if page["type"] == "page"), None)

            page = await eventually(debugger, "installed Chrome")
            socket = await websockets.connect(page["webSocketDebuggerUrl"], max_size=64 * 1024 * 1024)
            browser = Browser(socket)
            for domain in ("Page", "Runtime", "Network"):
                await browser.call(domain + ".enable")
            await browser.call("Emulation.setDeviceMetricsOverride", width=1440, height=900, deviceScaleFactor=1, mobile=False)
            await browser.call("Page.navigate", url=args.frontend + "/demo")

            async def ready():
                return await browser.evaluate("!!document.querySelector('input[type=file]') && [...document.querySelectorAll('button')].some(b=>b.innerText.includes('Upload local video')&&!b.disabled)")

            await eventually(ready, "verified upload interface")
            if previous_manifest is None:
                assert await browser.evaluate("document.querySelectorAll('canvas').length") == 0
                report["checks"]["empty_state_has_no_substitute_scene"] = True
            await browser.screenshot(output / "01-before-upload.png")
            await browser.upload(video)

            async def processing():
                state = (await client.get(args.api + "/api/pipeline/status")).json()
                return state if state["status"] == "processing" else None

            state = await eventually(processing, "real browser file upload accepted")
            job_id = state["job_id"]
            report["job_id"] = job_id
            report["checks"]["browser_upload_created_job"] = True
            await browser.call("Page.reload")

            async def restored():
                text = await browser.text()
                return job_id in text and "PROCESSING" in text

            await eventually(restored, "processing status restored after page reload")
            report["checks"]["processing_survives_page_reload"] = True
            latencies = []
            previous_step = None
            deadline = time.monotonic() + args.timeout
            while time.monotonic() < deadline:
                tick = time.monotonic()
                response = await client.get(args.api + "/api/pipeline/status", params={"job_id": job_id})
                response.raise_for_status()
                latencies.append(time.monotonic() - tick)
                state = response.json()
                if state["step"] != previous_step:
                    row = {"elapsed_seconds": round(time.monotonic() - started, 2),
                           "status": state["status"], "step": state["step"], "progress": state["progress"]}
                    report["timeline"].append(row)
                    print(json.dumps(row), flush=True)
                    previous_step = state["step"]
                if state["status"] == "error":
                    await browser.screenshot(output / "failed-job.png")
                    raise RuntimeError(state["error"])
                if state["status"] == "completed":
                    break
                await asyncio.sleep(3)
            else:
                raise TimeoutError("Real reconstruction did not finish within the acceptance wait limit; the server job was not cancelled")
            report["max_status_latency_seconds"] = max(latencies)
            response = await client.get(args.api + "/api/pipeline/scene")
            response.raise_for_status()
            manifest = response.json()["manifest"]
            assert manifest["job_id"] == job_id
            assert manifest["quality"]["phase_a"] == manifest["quality"]["phase_b"] == manifest["quality"]["phase_c"] == "PASSED"
            assert manifest["capabilities"] == {"queries": False, "edits": False}
            report["manifest"] = manifest
            report["checks"]["fresh_ABC_gates_passed"] = True
            report["checks"]["uncalibrated_metric_features_disabled"] = True
            for name, key in (("scene.splat", "splat_url"), ("scene.classes.u8", "classes_url")):
                asset = await client.get(args.api + manifest[key])
                asset.raise_for_status()
                assert hashlib.sha256(asset.content).hexdigest() == manifest["sha256"][name]
                assert len(asset.content) == manifest["gaussian_count"] * (32 if name == "scene.splat" else 1)
            report["checks"]["served_bytes_match_verified_hashes_and_counts"] = True

            async def rendered():
                text = await browser.text()
                return (job_id in text and "learned Gaussians" in text and "Viewer error" not in text
                        and await browser.evaluate("document.querySelectorAll('canvas').length") == 1)

            await eventually(rendered, "real learned Gaussian browser scene", timeout=120)
            await asyncio.sleep(3)
            await browser.screenshot(output / "02-real-reconstruction.png")
            bounds = await browser.evaluate("(()=>{const r=document.querySelector('canvas').getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height}})()")
            image = Image.open(output / "02-real-reconstruction.png").convert("RGB")
            box = (int(bounds["x"] + 10), int(bounds["y"] + 10), int(bounds["x"] + bounds["width"] - 10), int(bounds["y"] + bounds["height"] - 65))
            pixels = np.asarray(image.crop(box))
            report["render_pixels"] = {"mean_rgb": pixels.mean(axis=(0, 1)).tolist(),
                                       "rgb_standard_deviation": float(pixels.std()),
                                       "nonblack_fraction": float((pixels.max(axis=2) > 20).mean()),
                                       "unique_rgb_values": len(np.unique(pixels.reshape(-1, 3), axis=0))}
            assert report["render_pixels"]["nonblack_fraction"] > .02
            assert report["render_pixels"]["unique_rgb_values"] > 1000
            report["webgl_renderer"] = await browser.evaluate("(()=>{const g=document.querySelector('canvas').getContext('webgl2');const e=g.getExtension('WEBGL_debug_renderer_info');return e?g.getParameter(e.UNMASKED_RENDERER_WEBGL):g.getParameter(g.RENDERER)})()")
            report["checks"]["real_textured_gaussian_pixels_rendered"] = True
            x, y = bounds["x"] + bounds["width"] * .5, bounds["y"] + bounds["height"] * .5
            await browser.call("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y, button="left", buttons=1, clickCount=1)
            for offset in range(5, 66, 5):
                await browser.call("Input.dispatchMouseEvent", type="mouseMoved", x=x + offset, y=y + 10, button="left", buttons=1)
                await asyncio.sleep(.03)
            await browser.call("Input.dispatchMouseEvent", type="mouseReleased", x=x + 65, y=y + 10, button="left", buttons=0, clickCount=1)
            await asyncio.sleep(1)
            await browser.screenshot(output / "03-orbited-reconstruction.png")
            after = np.asarray(Image.open(output / "03-orbited-reconstruction.png").convert("RGB").crop(box))
            difference = float(np.abs(after.astype(float) - pixels).mean())
            assert difference > .2, "Orbit did not change the actual rendered scene"
            report["orbit_mean_pixel_change"] = difference
            report["checks"]["interactive_orbit_changes_real_render"] = True
            await browser.call("Page.reload")
            await eventually(rendered, "published scene reload from durable manifest")
            report["checks"]["published_scene_survives_reload"] = True
            # A corrupt user-selected clip must fail honestly and preserve this scene.
            bad_video = output / "invalid-upload.mp4"
            bad_video.write_bytes(b"intentional invalid video for fail-closed acceptance")
            await browser.upload(bad_video)

            async def failed_later():
                state = (await client.get(args.api + "/api/pipeline/status")).json()
                return state if state["job_id"] != job_id and state["status"] == "error" else None

            failed = await eventually(failed_later, "corrupt-video failure without replacement", timeout=90)
            report["failed_followup_job"] = failed["job_id"]
            current = (await client.get(args.api + "/api/pipeline/scene")).json()["manifest"]
            assert current == manifest

            async def retained():
                text = await browser.text()
                return "Previous verified scene" in text and "Reconstruction failed:" in text and "learned Gaussians" in text

            await eventually(retained, "previous scene with persistent failure message")
            await browser.screenshot(output / "04-failed-upload-preserves-scene.png")
            report["checks"]["failed_upload_preserves_and_identifies_previous_scene"] = True
            forbidden = [event["params"]["request"]["url"] for event in browser.events
                         if event["method"] == "Network.requestWillBeSent"
                         and any(part in event["params"]["request"]["url"] for part in
                                 ("/api/objects", "/api/query", "/api/edit", "/static/scene.splat", "/static/scene.classes.u8", "/upload-kaggle"))]
            assert not forbidden, forbidden
            report["checks"]["browser_never_uses_legacy_scene_or_seed_database"] = True
            exceptions = [event for event in browser.events if event["method"] == "Runtime.exceptionThrown"]
            report["javascript_exceptions"] = exceptions
            assert not exceptions, "Unexpected browser JavaScript exceptions"
            report["checks"]["no_browser_javascript_exceptions"] = True
            report["status"] = "PASSED"
    except BaseException as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        report["elapsed_seconds"] = round(time.monotonic() - started, 2)
        (output / "browser-acceptance.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
        if browser:
            browser.reader.cancel()
        if socket:
            await socket.close()
        if chrome and chrome.poll() is None:
            subprocess.run(["taskkill", "/PID", str(chrome.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            chrome.wait(timeout=15)
        shutil.rmtree(profile, ignore_errors=True)
    print(f"REAL BROWSER ACCEPTANCE: {report['status']}; {report['elapsed_seconds']} seconds; evidence at {output}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--api", default="http://127.0.0.1:8011")
    parser.add_argument("--frontend", default="http://127.0.0.1:5174")
    parser.add_argument("--chrome", type=Path, default=Path("C:/Program Files/Google/Chrome/Application/chrome.exe"))
    parser.add_argument("--debug-port", type=int, default=9228)
    parser.add_argument("--timeout", type=int, default=3600)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
