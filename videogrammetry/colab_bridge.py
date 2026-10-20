"""Colab Bridge Service.
Provides bidirectional integration between the local Spatial Twin application
and the remote Google Colab T4 GPU reconstruction worker.
"""

import asyncio
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional, Callable
import urllib.request
import urllib.parse
import json

class ColabBridge:
    def __init__(self, default_url: Optional[str] = None):
        env_url = os.getenv("COLAB_WORKER_URL") or os.getenv("CLOUD_GPU_URL")
        self.worker_url: Optional[str] = (default_url or env_url or "").rstrip("/") or None
        self.is_connected: bool = False
        self.gpu_device: Optional[str] = None
        self.gpu_vram_gb: float = 0.0

    def set_worker_url(self, url: str) -> None:
        self.worker_url = url.strip().rstrip("/") if url else None

    async def check_health(self, url: Optional[str] = None) -> Dict[str, Any]:
        """Pings the Colab worker /health endpoint."""
        target_url = (url or self.worker_url or "").rstrip("/")
        if not target_url:
            return {"connected": False, "error": "No Colab worker URL configured"}

        endpoint = f"{target_url}/health"

        def _do_request():
            req = urllib.request.Request(endpoint, headers={"User-Agent": "SpatialTwin-Sidecar/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
                raise RuntimeError(f"HTTP {resp.status}")

        try:
            data = await asyncio.to_thread(_do_request)
            self.is_connected = True
            self.gpu_device = data.get("device", "NVIDIA GPU")
            self.gpu_vram_gb = float(data.get("vram_gb", 0.0))
            self.worker_url = target_url
            return {
                "connected": True,
                "url": target_url,
                "device": self.gpu_device,
                "vram_gb": self.gpu_vram_gb,
                "model_ready": data.get("model_ready", False),
            }
        except Exception as e:
            self.is_connected = False
            return {
                "connected": False,
                "url": target_url,
                "error": str(e),
            }

    async def get_status(self) -> Dict[str, Any]:
        """Retrieves real-time training progress from Colab /status."""
        if not self.worker_url:
            return {"status": "offline", "progress": 0}

        endpoint = f"{self.worker_url}/status"

        def _do_request():
            req = urllib.request.Request(endpoint, headers={"User-Agent": "SpatialTwin-Sidecar/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read().decode("utf-8"))

        try:
            return await asyncio.to_thread(_do_request)
        except Exception as e:
            return {"status": "error", "error": str(e), "progress": 0}

    async def train_and_sync(
        self,
        video_path: Path,
        out_dir: Path,
        on_progress: Optional[Callable[[str, float, list], None]] = None,
        poll_interval: float = 2.0,
        max_timeout_s: float = 900.0,
    ) -> Dict[str, Any]:
        """Uploads drone video to Colab, polls progress, and downloads scene.glb and point_cloud.ply."""
        if not self.worker_url:
            raise RuntimeError("Colab worker URL is not connected.")

        out_dir.mkdir(parents=True, exist_ok=True)
        train_url = f"{self.worker_url}/train"

        # 1. Upload video file via multipart form-data
        def _upload_video():
            boundary = f"----WebKitFormBoundary{hex(int(time.time()*1000))[2:]}"
            with open(video_path, "rb") as vf:
                file_bytes = vf.read()

            body = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="{video_path.name}"\r\n'
                f"Content-Type: video/mp4\r\n\r\n"
            ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

            req = urllib.request.Request(
                train_url,
                data=body,
                headers={
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                    "User-Agent": "SpatialTwin-Sidecar/1.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))

        start_res = await asyncio.to_thread(_upload_video)

        # 2. Poll Colab status until completed or failed
        t_start = time.time()
        last_progress = 0
        last_stage = "Stage 1: Frame Extraction (FFmpeg GPU)"

        while (time.time() - t_start) < max_timeout_s:
            status_data = await self.get_status()
            cur_status = status_data.get("status", "unknown")
            cur_stage = status_data.get("stage_name", last_stage)
            cur_progress = float(status_data.get("progress", last_progress))
            logs = status_data.get("logs", [])

            if on_progress:
                on_progress(cur_stage, cur_progress, logs)

            if cur_status == "completed":
                break
            elif cur_status == "failed":
                err_msg = status_data.get("error", "Colab training pipeline failed")
                raise RuntimeError(f"Colab worker error: {err_msg}")

            await asyncio.sleep(poll_interval)

        # 3. Download compiled scene.glb
        glb_url = f"{self.worker_url}/model/glb"
        glb_dest = out_dir / "scene.glb"

        def _download_file(src_url, dest_path):
            req = urllib.request.Request(src_url, headers={"User-Agent": "SpatialTwin-Sidecar/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp, open(dest_path, "wb") as out_f:
                out_f.write(resp.read())

        await asyncio.to_thread(_download_file, glb_url, glb_dest)

        if not glb_dest.exists() or glb_dest.stat().st_size == 0:
            raise RuntimeError("Downloaded scene.glb is empty (0 bytes).")

        # 4. Attempt to download point_cloud.ply (optional companion)
        ply_url = f"{self.worker_url}/model/ply"
        ply_dest = out_dir / "point_cloud.ply"
        try:
            await asyncio.to_thread(_download_file, ply_url, ply_dest)
        except Exception:
            pass

        return {
            "status": "completed",
            "glb_path": str(glb_dest),
            "glb_bytes": glb_dest.stat().st_size,
            "has_ply": ply_dest.exists(),
        }

# Global ColabBridge instance
colab_bridge = ColabBridge()
