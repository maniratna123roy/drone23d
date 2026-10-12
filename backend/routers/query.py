import time
from typing import List, Optional
from fastapi import APIRouter, Depends
from backend.scene_capabilities import require_query_scene
from pydantic import BaseModel

from backend.schemas.core import Structure
from backend.agent.intent_schema import OperationEnum
from backend.agent.ollama_client import ollama_client
from backend.agent.sql_compiler import sql_compiler
from backend.db.queries import execute_compiled_query

router = APIRouter(prefix="/api/query", dependencies=[Depends(require_query_scene)])


class QueryRequest(BaseModel):
    text: str


class QueryMetrics(BaseModel):
    count: int
    avg_height_m: float
    total_area_m2: float
    min_height_m: float
    max_height_m: float


class QueryResponse(BaseModel):
    status: str = "success"
    query: str
    matched_ids: List[int] = []
    objects: List[Structure] = []
    metrics: Optional[QueryMetrics] = None
    intent: Optional[dict] = None
    sql: Optional[str] = None
    message: Optional[str] = None
    latency_ms: float


@router.post("", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    start = time.perf_counter()
    raw_text = request.text.strip()

    if not raw_text:
        return QueryResponse(
            status="unsupported",
            query=request.text,
            message="Please provide a valid query.",
            latency_ms=round((time.perf_counter() - start) * 1000, 2),
        )

    # 1. Translate user natural language into structured intent
    intent = await ollama_client.parse_intent(raw_text)

    # 2. Check if intent is unknown or unsupported
    if intent.operation == OperationEnum.UNKNOWN:
        return QueryResponse(
            status="unsupported",
            query=request.text,
            message="I could not identify any spatial filters. Try asking: 'Which buildings are taller than 20m?' or 'Show structures in the center region.'",
            intent=intent.model_dump(),
            latency_ms=round((time.perf_counter() - start) * 1000, 2),
        )

    # 3. Compile intent to safe parameterized SQL
    compiled = sql_compiler.compile(intent)
    if not compiled:
        return QueryResponse(
            status="unsupported",
            query=request.text,
            message="Unable to compile spatial query for this intent.",
            intent=intent.model_dump(),
            latency_ms=round((time.perf_counter() - start) * 1000, 2),
        )

    # 4. Execute query against PostGIS and calculate metrics
    result = await execute_compiled_query(compiled.sql, compiled.params)
    latency_ms = round((time.perf_counter() - start) * 1000, 2)

    return QueryResponse(
        status="success",
        query=request.text,
        matched_ids=result["matched_ids"],
        objects=result["objects"],
        metrics=QueryMetrics(**result["metrics"]),
        intent=intent.model_dump(),
        sql=compiled.sql,
        latency_ms=latency_ms,
    )
