import time
import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends
from backend.scene_capabilities import require_edit_scene
from pydantic import BaseModel

from backend.agent.intent_schema import OperationEnum
from backend.agent.ollama_client import ollama_client
from backend.agent.sql_compiler import sql_compiler
from backend.db.queries import (
    execute_compiled_query,
    apply_extrude_edit,
    rollback_last_edit_session,
    fetch_structures_by_ids,
)
from backend.ws.manager import manager

router = APIRouter(prefix="/api/edit", dependencies=[Depends(require_edit_scene)])

# In-memory store for active preview tokens (Decision D9)
# preview_token -> metadata dict
PREVIEW_CACHE: Dict[str, Dict[str, Any]] = {}


class EditPreviewRequest(BaseModel):
    text: str


class PreviewDelta(BaseModel):
    object_id: int
    current_height_m: float
    new_height_m: float
    delta_height_m: float
    footprint: Optional[dict] = None
    splat_bbox: Optional[dict] = None


class EditPreviewResponse(BaseModel):
    status: str = "success"
    preview_token: Optional[str] = None
    command: str
    affected_count: int
    target_ids: List[int] = []
    deltas: List[PreviewDelta] = []
    intent: Optional[dict] = None
    message: Optional[str] = None
    latency_ms: float


class EditApplyRequest(BaseModel):
    preview_token: str


class EditApplyResponse(BaseModel):
    status: str = "success"
    session_id: str
    affected_count: int
    updated_ids: List[int] = []
    updated_objects: List[dict] = []
    message: Optional[str] = None
    latency_ms: float


class EditUndoRequest(BaseModel):
    session_id: Optional[str] = None


class EditUndoResponse(BaseModel):
    status: str = "success"
    session_id: Optional[str] = None
    restored_count: int
    restored_ids: List[int] = []
    restored_objects: List[dict] = []
    message: Optional[str] = None
    latency_ms: float


@router.post("/preview", response_model=EditPreviewResponse)
async def preview_edit(request: EditPreviewRequest):
    """
    Step 1 of the Edit Loop:
    Translates user command to intent, calculates geometry deltas,
    and returns a preview_token + ghost objects without changing the database.
    """
    start = time.perf_counter()
    raw_text = request.text.strip()

    if not raw_text:
        return EditPreviewResponse(
            status="error",
            command=request.text,
            affected_count=0,
            message="Please provide an edit command.",
            latency_ms=round((time.perf_counter() - start) * 1000, 2),
        )

    # 1. Parse intent
    intent = await ollama_client.parse_intent(raw_text)

    # Check for valid edit operation (EXTRUDE, TRANSLATE, FLATTEN)
    if intent.operation not in [OperationEnum.EXTRUDE, OperationEnum.TRANSLATE, OperationEnum.FLATTEN]:
        # Fallback heuristic: check if magnitude or extrude keywords exist
        if "raise" in raw_text.lower() or "taller" in raw_text.lower() or "extrude" in raw_text.lower() or "increase" in raw_text.lower():
            intent.operation = OperationEnum.EXTRUDE

    if intent.operation != OperationEnum.EXTRUDE:
        return EditPreviewResponse(
            status="unsupported",
            command=request.text,
            affected_count=0,
            message=f"Operation '{intent.operation.value}' is not supported yet for live editing. Try: 'Raise the central buildings by 40 metres'.",
            intent=intent.model_dump(),
            latency_ms=round((time.perf_counter() - start) * 1000, 2),
        )

    # Determine delta height
    delta_m = 10.0
    if intent.magnitude and intent.magnitude.value is not None:
        delta_m = float(intent.magnitude.value)
        if intent.direction and intent.direction.value == "DOWN":
            delta_m = -abs(delta_m)

    # 2. Compile query for target structures
    compiled = sql_compiler.compile_extrude_targets(intent)
    if not compiled:
        return EditPreviewResponse(
            status="error",
            command=request.text,
            affected_count=0,
            message="Failed to compile target selection for edit.",
            intent=intent.model_dump(),
            latency_ms=round((time.perf_counter() - start) * 1000, 2),
        )

    # 3. Fetch matched structures
    query_result = await execute_compiled_query(compiled.sql, compiled.params)
    targets = query_result["objects"]

    if not targets:
        return EditPreviewResponse(
            status="no_match",
            command=request.text,
            affected_count=0,
            message="No structures matched the specified region or criteria to edit.",
            intent=intent.model_dump(),
            latency_ms=round((time.perf_counter() - start) * 1000, 2),
        )

    target_ids = [t["id"] for t in targets]
    deltas = []
    for t in targets:
        cur_h = float(t["height_m"] or 20.0)
        new_h = max(1.0, cur_h + delta_m)
        deltas.append(
            PreviewDelta(
                object_id=t["id"],
                current_height_m=cur_h,
                new_height_m=new_h,
                delta_height_m=delta_m,
                footprint=t["footprint"],
                splat_bbox=t["splat_bbox"],
            )
        )

    # Generate preview token
    preview_token = str(uuid.uuid4())
    PREVIEW_CACHE[preview_token] = {
        "command": raw_text,
        "intent": intent.model_dump(),
        "target_ids": target_ids,
        "delta_height_m": delta_m,
        "created_at": time.time(),
    }

    return EditPreviewResponse(
        status="success",
        preview_token=preview_token,
        command=raw_text,
        affected_count=len(target_ids),
        target_ids=target_ids,
        deltas=deltas,
        intent=intent.model_dump(),
        message=f"Preview ready for {len(target_ids)} structure(s). Click confirm to apply.",
        latency_ms=round((time.perf_counter() - start) * 1000, 2),
    )


@router.post("/apply", response_model=EditApplyResponse)
async def apply_edit(request: EditApplyRequest):
    """
    Step 2 of the Edit Loop (Decision D9):
    Applies the previewed edit using the preview_token.
    Updates DB, logs history, broadcasts WebSocket scene_diff.
    """
    start = time.perf_counter()
    token = request.preview_token

    if token not in PREVIEW_CACHE:
        return EditApplyResponse(
            status="error",
            session_id="",
            affected_count=0,
            message="Invalid or expired preview token. Please generate a new preview.",
            latency_ms=round((time.perf_counter() - start) * 1000, 2),
        )

    cached = PREVIEW_CACHE.pop(token)
    session_id = f"session_{uuid.uuid4().hex[:8]}"

    updated_structures = await apply_extrude_edit(
        session_id=session_id,
        command=cached["command"],
        intent_dict=cached["intent"],
        object_ids=cached["target_ids"],
        delta_height_m=cached["delta_height_m"],
    )

    updated_ids = [s["id"] for s in updated_structures]

    # WebSocket broadcast to all connected 3D viewports
    await manager.broadcast({
        "event": "scene_diff",
        "action": "edit",
        "session_id": session_id,
        "updated": updated_ids,
        "removed": [],
        "version": updated_structures[0]["version"] if updated_structures else 1,
    })

    return EditApplyResponse(
        status="success",
        session_id=session_id,
        affected_count=len(updated_ids),
        updated_ids=updated_ids,
        updated_objects=updated_structures,
        message=f"Applied extrusion of {cached['delta_height_m']}m to {len(updated_ids)} structure(s).",
        latency_ms=round((time.perf_counter() - start) * 1000, 2),
    )


@router.post("/undo", response_model=EditUndoResponse)
async def undo_edit(request: EditUndoRequest):
    """
    Step 3 of the Edit Loop:
    Reverts the last edit session (or specified session_id) from geometry_history.
    Broadcasts WebSocket scene_diff to sync all 3D viewports.
    """
    start = time.perf_counter()

    rolled_session_id, restored_ids = await rollback_last_edit_session(request.session_id)

    if not rolled_session_id or not restored_ids:
        return EditUndoResponse(
            status="no_op",
            session_id=None,
            restored_count=0,
            message="No previous edit session found to undo.",
            latency_ms=round((time.perf_counter() - start) * 1000, 2),
        )

    restored_structures = await fetch_structures_by_ids(restored_ids)

    # Broadcast undo to all connected clients
    await manager.broadcast({
        "event": "scene_diff",
        "action": "undo",
        "session_id": rolled_session_id,
        "updated": restored_ids,
        "removed": [],
        "version": restored_structures[0]["version"] if restored_structures else 1,
    })

    return EditUndoResponse(
        status="success",
        session_id=rolled_session_id,
        restored_count=len(restored_ids),
        restored_ids=restored_ids,
        restored_objects=restored_structures,
        message=f"Undid session '{rolled_session_id}'. Restored {len(restored_ids)} structure(s).",
        latency_ms=round((time.perf_counter() - start) * 1000, 2),
    )
