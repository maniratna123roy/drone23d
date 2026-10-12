"""Kaggle bootstrap for the same verified reconstruction used by local uploads.

Ship only the existing reconstruction modules, never a second implementation of
depth, camera parsing, Gaussian fitting, or semantic voting.
"""
import base64
import io
from pathlib import Path
import zipfile


WORKER_FILES = (
    "pipeline/video_processor.py",
    "pipeline/colmap_reconstructor.py",
    "pipeline/dense_reconstruction.py",
    "pipeline/gaussian_optimizer.py",
    "pipeline/semantic_classification.py",
    "pipeline/reconstruction_job.py",
    "pipeline/scene_publication.py",
    "pipeline/common/io.py",
    "pipeline/common/frame.py",
)


def build_worker_script(request: dict) -> str:
    """Embed an allowlisted snapshot of working local code and this job's ticket."""
    root = Path(__file__).resolve().parent.parent
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in WORKER_FILES:
            archive.writestr(name, (root / name).read_bytes())
        for name in ("pipeline/__init__.py", "pipeline/common/__init__.py"):
            archive.writestr(name, "")
    payload = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"CODE_BUNDLE = {payload!r}\nJOB_REQUEST = {request!r}\n" + KAGGLE_WORKER_SCRIPT


KAGGLE_WORKER_SCRIPT = '''
import base64
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile


def command(args):
    print("[KAGGLE SETUP] " + " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), check=True)


def ensure_cuda_colmap(root):
    """Distro COLMAP can be CPU-only; native dense stereo requires CUDA."""
    binary = shutil.which("colmap")
    if binary:
        help_result = subprocess.run([binary, "-h"], capture_output=True, text=True, check=True)
        banner = help_result.stdout + help_result.stderr
        if "with CUDA" in banner and "without CUDA" not in banner:
            return
    # Build the already-used COLMAP engine, with GUI disabled for Kaggle.
    # Do not substitute guessed depth when a CPU-only apt package lacks MVS.
    if not shutil.which("nvcc"):
        raise RuntimeError("Kaggle CUDA toolkit is missing. Enable a GPU accelerator and retry.")
    root.mkdir(parents=True, exist_ok=True)
    command(["apt-get", "update", "-qq"])
    command(["apt-get", "install", "-y", "-qq", "git", "cmake", "ninja-build",
             "build-essential", "libboost-program-options-dev", "libboost-graph-dev",
             "libboost-system-dev", "libeigen3-dev", "libflann-dev", "libfreeimage-dev",
             "libmetis-dev", "libgoogle-glog-dev", "libgtest-dev", "libsqlite3-dev",
             "libglew-dev", "libceres-dev", "libcgal-dev", "liblz4-dev", "libgl1-mesa-dev"])
    command(["ldconfig"])
    source, build, install = (root / name for name in ("colmap-src", "colmap-build", "colmap-install"))
    command(["git", "clone", "--depth", "1", "--branch", "3.11.1",
             "https://github.com/colmap/colmap.git", source])
    # CUDA MVS is retained, but headless Kaggle uses CPU SIFT so the optional
    # OpenGL/SiftGPU target and its fragile dispatch libraries are unnecessary.
    dependencies = source / "cmake/FindDependencies.cmake"
    dependency_text = dependencies.read_text(encoding="utf-8")
    dependencies.write_text(
        dependency_text.replace("if(OPENGL_ENABLED OR CUDA_ENABLED)", "if(OPENGL_ENABLED)"),
        encoding="utf-8",
    )
    import torch
    major, minor = torch.cuda.get_device_capability(0)
    command(["cmake", "-S", source, "-B", build, "-GNinja", "-DCMAKE_BUILD_TYPE=Release",
             "-DGUI_ENABLED=OFF", "-DCUDA_ENABLED=ON", "-DTESTS_ENABLED=OFF",
             f"-DCMAKE_CUDA_ARCHITECTURES={major}{minor}", f"-DCMAKE_INSTALL_PREFIX={install}"])
    command(["cmake", "--build", build, "--parallel", "2"])
    command(["cmake", "--install", build])
    os.environ["PATH"] = str(install / "bin") + os.pathsep + os.environ["PATH"]


def main():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    output = Path("/kaggle/working")
    code = output / "worker-code"
    code.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(CODE_BUNDLE))) as archive:
        archive.extractall(code)
    reconstructor = code / "pipeline/colmap_reconstructor.py"
    source_text = reconstructor.read_text(encoding="utf-8")
    reconstructor.write_text(
        source_text.replace(
            'use_gpu_flag = "1" if torch.cuda.is_available() else "0"',
            'use_gpu_flag = "0"',
        ).replace('"--FeatureExtraction.use_gpu"', '"--SiftExtraction.use_gpu"')
         .replace('"--FeatureMatching.use_gpu"', '"--SiftMatching.use_gpu"'),
        encoding="utf-8",
    )
    sys.path.insert(0, str(code))
    # These are existing project dependencies, not alternative reconstruction libraries.
    command([sys.executable, "-m", "pip", "install", "-q", "av==18.1.0", "plyfile",
             "scipy", "scikit-learn", "transformers>=4.40,<5", "opencv-python-headless"])
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("Kaggle GPU is unavailable. Enable a GPU accelerator and retry.")
    ensure_cuda_colmap(Path("/tmp/spatial-twin-colmap"))
    from pipeline.scene_publication import atomic_json, sha256_file, publish_verified_scene
    from pipeline.reconstruction_job import run_reconstruction

    videos = list(Path("/kaggle/input").rglob("drone_footage.mp4"))
    if len(videos) != 1 or sha256_file(videos[0]) != JOB_REQUEST["video_sha256"]:
        raise ValueError("Kaggle input does not match this upload. Retry the video upload.")
    job = output / "reconstruction"
    job.mkdir(exist_ok=False)
    shutil.copyfile(videos[0], job / "input.mp4")
    request = {**JOB_REQUEST, "input_file": "input.mp4", "device": "cuda"}
    atomic_json(job / "request.json", request)
    result = run_reconstruction(job / "request.json")
    manifest = publish_verified_scene(job, output / "published", request["job_id"], request["source_name"])
    atomic_json(output / "cloud_result.json", {
        "status": result["status"], "video_sha256": result["video_sha256"],
        "job_id": request["job_id"], "manifest_sha256": sha256_file(
            output / "published/scenes" / request["job_id"] / "manifest.json"),
    })
    print(f"[KAGGLE SUCCESS] {manifest['gaussian_count']:,} Gaussians (not building instances).", flush=True)


if __name__ == "__main__":
    main()
'''
