import pytest
import pytest_asyncio
import httpx
from httpx import ASGITransport

from backend.main import app
from backend.db.connection import connect_to_db, close_db_connection
from backend.agent.intent_schema import IntentModel, OperationEnum, LayerEnum, FilterModel
from backend.agent.sql_compiler import sql_compiler
from backend.agent.fallback_matcher import match_fallback_intent
from backend.agent.ollama_client import ollama_client


@pytest_asyncio.fixture(scope="function")
async def setup_test_app():
    await connect_to_db()
    from backend.scene_capabilities import require_query_scene, require_capability
    app.dependency_overrides[require_query_scene] = lambda: None
    app.dependency_overrides[require_capability] = lambda cap: None
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
    await close_db_connection()


# 1. Test Intent Schema & Pydantic Validation
def test_intent_schema_models():
    intent = IntentModel(
        operation=OperationEnum.QUERY_HEIGHT,
        layer=LayerEnum.structures,
        filter=FilterModel(min_height_m=20.0, region="center")
    )
    assert intent.operation == OperationEnum.QUERY_HEIGHT
    assert intent.filter.min_height_m == 20.0
    assert intent.filter.region == "center"


# 2. Test SQL Compiler
def test_sql_compiler_height():
    intent = IntentModel(
        operation=OperationEnum.QUERY_HEIGHT,
        layer=LayerEnum.structures,
        filter=FilterModel(min_height_m=25.0)
    )
    compiled = sql_compiler.compile(intent)
    assert compiled is not None
    assert "height_m >= $1" in compiled.sql
    assert compiled.params == [25.0]


def test_sql_compiler_region():
    intent = IntentModel(
        operation=OperationEnum.SELECT_REGION,
        layer=LayerEnum.structures,
        filter=FilterModel(region="north")
    )
    compiled = sql_compiler.compile(intent)
    assert compiled is not None
    assert "LOWER(region) = LOWER($1)" in compiled.sql
    assert compiled.params == ["north"]


def test_sql_compiler_unknown():
    intent = IntentModel(
        operation=OperationEnum.UNKNOWN,
        layer=LayerEnum.structures
    )
    compiled = sql_compiler.compile(intent)
    assert compiled is None


# 3. Test Fallback Regex Matcher
def test_fallback_matcher_queries():
    # Height taller than
    res1 = match_fallback_intent("Which buildings are taller than 20 metres?")
    assert res1 is not None
    assert res1.operation == OperationEnum.QUERY_HEIGHT
    assert res1.filter.min_height_m == 20.0

    # Height range
    res2 = match_fallback_intent("Find all buildings between 10m and 30m in height")
    assert res2 is not None
    assert res2.operation == OperationEnum.QUERY_HEIGHT
    assert res2.filter.min_height_m == 10.0
    assert res2.filter.max_height_m == 30.0

    # Region
    res3 = match_fallback_intent("Show me all structures in the center region")
    assert res3 is not None
    assert res3.operation == OperationEnum.SELECT_REGION
    assert res3.filter.region == "center"

    # Nonsense
    res4 = match_fallback_intent("Make me a cup of coffee")
    assert res4 is None


# 4. Test Ollama Live Intent Parser
@pytest.mark.asyncio
async def test_ollama_live_parsing():
    intent = await ollama_client.parse_intent("Which buildings are taller than 20 metres?")
    assert intent.operation == OperationEnum.QUERY_HEIGHT
    assert intent.layer == LayerEnum.structures
    assert intent.filter is not None
    assert intent.filter.min_height_m == 20.0


# 5. End-to-End API Query: Height Query
@pytest.mark.asyncio
async def test_query_api_height(setup_test_app: httpx.AsyncClient):
    client = setup_test_app
    resp = await client.post("/api/query", json={"text": "Which buildings are taller than 20 metres?"})
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "success"
    assert len(data["matched_ids"]) > 0
    assert data["metrics"]["count"] == len(data["matched_ids"])
    assert data["metrics"]["min_height_m"] >= 20.0
    assert data["latency_ms"] < 3000.0  # Constraint: < 3 seconds

    # Verify all returned objects have height >= 20
    for obj in data["objects"]:
        assert obj["height_m"] >= 20.0


# 6. End-to-End API Query: Region Query
@pytest.mark.asyncio
async def test_query_api_region(setup_test_app: httpx.AsyncClient):
    client = setup_test_app
    resp = await client.post("/api/query", json={"text": "Show me all structures in the center region"})
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "success"
    assert isinstance(data["matched_ids"], list)
    for obj in data["objects"]:
        assert obj["region"] == "center"


# 7. End-to-End API Query: Range Query
@pytest.mark.asyncio
async def test_query_api_range(setup_test_app: httpx.AsyncClient):
    client = setup_test_app
    resp = await client.post("/api/query", json={"text": "Find all buildings between 10m and 30m in height"})
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "success"
    assert isinstance(data["matched_ids"], list)
    for obj in data["objects"]:
        assert 10.0 <= obj["height_m"] <= 30.0


# 8. End-to-End API Query: Nonsense / Unsupported Query
@pytest.mark.asyncio
async def test_query_api_nonsense(setup_test_app: httpx.AsyncClient):
    client = setup_test_app
    resp = await client.post("/api/query", json={"text": "Order a pepperoni pizza with extra cheese"})
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "unsupported"
    assert data["matched_ids"] == []
    assert data["objects"] == []
    assert data["metrics"] is None
    assert "could not identify" in data["message"]


# 9. End-to-End API Query: Empty Query
@pytest.mark.asyncio
async def test_query_api_empty(setup_test_app: httpx.AsyncClient):
    client = setup_test_app
    resp = await client.post("/api/query", json={"text": "   "})
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "unsupported"
    assert "valid query" in data["message"]


# 10. Pipeline Integration: Static 3D Splat Assets Serving
@pytest.mark.asyncio
async def test_static_assets_serving(setup_test_app: httpx.AsyncClient):
    client = setup_test_app
    r_splat = await client.head("/static/scene.splat")
    assert r_splat.status_code == 200
    assert int(r_splat.headers.get("content-length", 0)) > 0

    r_classes = await client.head("/static/scene.classes.u8")
    assert r_classes.status_code == 200
    assert int(r_classes.headers.get("content-length", 0)) > 0


# 11. Pipeline Integration: Project Frame Alignment Metadata
@pytest.mark.asyncio
async def test_project_metadata_endpoint(setup_test_app: httpx.AsyncClient):
    client = setup_test_app
    resp = await client.get("/api/objects/project")
    assert resp.status_code == 200
    data = resp.json()
    assert "Twin" in data["name"]
    assert data["scale_factor"] == 1.0
    assert len(data["frame_transform"]) == 4  # 4x4 RANSAC alignment matrix

