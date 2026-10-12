"""Run genuine per-upload reconstruction outside the FastAPI event loop.

The old depth/procedural fallback chain is deliberately not imported. A worker
must pass the verified A/B/C gates, and only the API parent may publish results.

Uses subprocess.Popen instead of asyncio.create_subprocess_exec because
uvicorn's event loop on Windows may not support subprocess transports
(raises NotImplementedError from SelectorEventLoop._make_subprocess_transport).
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
from typing import Any, Callable

from pipeline.scene_publication import read_json

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _stop_process_tree(process: subprocess.Popen) -> None:
    """Kill the worker and its child processes."""
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


async def execute_drone_video_pipeline(
    video_path: str | Path,
    progress_callback: Callable[[str, int, dict[str, Any]], None] | None = None,
    *,
    job_dir: str | Path,
    timeout_seconds: int = 7200,
) -> dict[str, Any]:
    root = Path(job_dir).resolve()
    request = read_json(root / "request.json")
    if Path(video_path).resolve() != (root / request["input_file"]).resolve():
        raise ValueError("Upload file does not match the isolated job request")
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONUNBUFFERED"] = "1"

    # Use subprocess.Popen instead of asyncio.create_subprocess_exec to avoid
    # NotImplementedError on Windows when the event loop lacks subprocess support.
    popen_kwargs: dict[str, Any] = dict(
        args=[sys.executable, "-B", "-u", "-m", "pipeline.reconstruction_job",
              "--request", str(root / "request.json")],
        cwd=str(PROJECT_ROOT),
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if os.name != "nt":
        popen_kwargs["start_new_session"] = True

    process = subprocess.Popen(**popen_kwargs)

    # Read stdout in a background thread so we don't block the event loop.
    result_holder: dict[str, Any] = {"returncode": None, "error": None}

    def _consume_output() -> None:
        try:
            with (root / "worker.log").open("w", encoding="utf-8") as log:
                for raw_line in process.stdout:
                    text = raw_line.decode("utf-8", errors="replace")
                    log.write(text)
                    log.flush()
                    if text.startswith("SPATIAL_PROGRESS ") and progress_callback:
                        import json
                        update = json.loads(text.removeprefix("SPATIAL_PROGRESS "))
                        progress_callback(update["step"], min(99, int(update["progress"])), update["details"])
                    match = re.match(r"\[3DGS (\d+)/(\d+)\]", text)
                    if match and progress_callback:
                        step, total = map(int, match.groups())
                        progress_callback(
                            f"Phase C: optimizing photograph fit ({step}/{total} steps)",
                            60 + int(32 * step / total),
                            {"optimization_step": step, "optimization_steps": total},
                        )
            result_holder["returncode"] = process.wait()
        except Exception as exc:
            result_holder["error"] = exc
            result_holder["returncode"] = -1

    reader_thread = threading.Thread(target=_consume_output, daemon=True)
    reader_thread.start()

    try:
        # Wait for the reader thread with a timeout, yielding to the event loop.
        await asyncio.to_thread(reader_thread.join, timeout_seconds)
        if reader_thread.is_alive():
            # Timed out — kill the process tree.
            _stop_process_tree(process)
            reader_thread.join(timeout=5)
            raise asyncio.TimeoutError()
    except asyncio.CancelledError:
        _stop_process_tree(process)
        reader_thread.join(timeout=5)
        raise

    if result_holder["error"] is not None:
        _stop_process_tree(process)
        raise RuntimeError(f"Output reader failed: {result_holder['error']}")

    returncode = result_holder["returncode"]
    if returncode != 0:
        failure_path = root / "failure.json"
        if failure_path.exists():
            failure = read_json(failure_path)
            raise RuntimeError(f"{failure['error']} {failure['guidance']}")
        raise RuntimeError(f"Reconstruction worker exited with code {returncode}. See the job's worker.log; no scene was replaced.")
    result = read_json(root / "result.json")
    if result.get("status") != "PASSED":
        raise RuntimeError("Reconstruction worker did not produce passed evidence; no scene was replaced")
    return result
