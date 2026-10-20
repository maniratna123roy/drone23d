import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from pathlib import Path
from fastapi.staticfiles import StaticFiles
from backend.config import settings
from backend.db.connection import connect_to_db, close_db_connection
from backend.routers import status, objects, query, edit, pipeline, openrouter_3d
from backend.ws.manager import manager
from backend import pipeline_jobs

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        pipeline_jobs.acquire_worker_lock()
    except RuntimeError as exc:
        print(f"[WARN] {exc}; proceeding in secondary mode.")
    try:
        pipeline_jobs.recover_interrupted_job()
        # Reconstruction/viewing do not require PostGIS. Do not pre-load the LLM
        # into the same small GPU used by COLMAP and Gaussian optimization.
        try:
            await asyncio.wait_for(connect_to_db(), timeout=3)
        except asyncio.TimeoutError:
            print("[INFO] PostGIS unavailable; verified reconstruction/viewing remain available.")
        yield
    finally:
        await pipeline_jobs.shutdown()
        await close_db_connection()

app = FastAPI(title="Spatial Twin API", lifespan=lifespan)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For dev only, restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static assets directory for 3D splats and binary sidecars
static_path = Path(settings.STATIC_ASSETS_DIR)
static_path.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Middleware: log incoming mutating/pipeline requests and disable aggressive browser caching
@app.middleware("http")
async def add_cache_control_and_logging_headers(request, call_next):
    path = request.url.path
    method = request.method
    is_pipeline_or_mutation = (method in ("POST", "PUT", "DELETE")) or path.startswith("/api/pipeline")
    # Reject oversized normal browser requests before multipart parsing can spool
    # the entire video. The upload handler also counts actual file bytes.
    if method == "POST" and path in ("/api/pipeline/upload", "/api/pipeline/upload-kaggle", "/api/pipeline/import-splat"):
        length = request.headers.get("content-length", "")
        if length.isdigit() and int(length) > (settings.PIPELINE_MAX_UPLOAD_MB + 1) * 1024 * 1024:
            return JSONResponse(status_code=413, content={"detail": f"File exceeds the {settings.PIPELINE_MAX_UPLOAD_MB}MB upload limit"})

    if is_pipeline_or_mutation:
        print(f"\n[HTTP REQ] >>> {method} {path}", flush=True)

    response = await call_next(request)

    if is_pipeline_or_mutation:
        print(f"[HTTP RES] <<< {method} {path} -> {response.status_code}", flush=True)

    if path.startswith("/static") or path.startswith("/api/objects") or path.startswith("/api/pipeline"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Include routers
app.include_router(status.router)
app.include_router(objects.router)
app.include_router(query.router)
app.include_router(edit.router)
app.include_router(pipeline.router)
app.include_router(openrouter_3d.router)

# WebSocket endpoint for real-time scene updates
@app.websocket("/ws/scene")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # For now, just listen for disconnects
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
