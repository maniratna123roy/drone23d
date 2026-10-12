"""Run the repaired cloud worker on real footage, without publishing a live scene."""
import argparse
import asyncio
from pathlib import Path
import subprocess
import sys
import uuid

from pipeline.scene_publication import atomic_json, read_json, sha256_file


async def acceptance(video: Path, root: Path, request_path: Path):
    from pipeline.kaggle_runner import run_kaggle_3dgs_job

    request = {**read_json(request_path), "job_id": uuid.uuid4().hex}
    pointer = Path("static/current-scene.json")
    before = sha256_file(pointer) if pointer.exists() else None
    atomic_json(root / "acceptance-request.json", request)
    try:
        result = await run_kaggle_3dgs_job(video, request=request, output_dir=root / "download")
        after = sha256_file(pointer) if pointer.exists() else None
        if before != after:
            raise ValueError("Live scene pointer changed during isolated acceptance")
        atomic_json(root / "acceptance-result.json", {**result, "live_scene_unchanged": True})
    except Exception as exc:
        atomic_json(root / "acceptance-failure.json", {"error": str(exc), "live_scene_unchanged":
                    before == (sha256_file(pointer) if pointer.exists() else None)})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--detach", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.detach:
        command = [sys.executable, "-u", "-m", "backend.tests.run_kaggle_fix_acceptance",
                   "--video", str(args.video), "--request", str(args.request), "--output", str(args.output)]
        with (args.output / "acceptance.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        atomic_json(args.output / "process.json", {"pid": process.pid})
        print(f"Isolated cloud acceptance started: PID {process.pid}, evidence: {args.output}")
    else:
        asyncio.run(acceptance(args.video, args.output, args.request))


if __name__ == "__main__":
    main()
