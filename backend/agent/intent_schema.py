from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class OperationEnum(str, Enum):
    QUERY_HEIGHT = "QUERY_HEIGHT"
    SELECT_REGION = "SELECT_REGION"
    EXTRUDE = "EXTRUDE"
    TRANSLATE = "TRANSLATE"
    FLATTEN = "FLATTEN"
    UNKNOWN = "UNKNOWN"


class LayerEnum(str, Enum):
    structures = "structures"
    terrain = "terrain"
    roads = "roads"
    vegetation = "vegetation"


class DirectionEnum(str, Enum):
    N = "N"
    S = "S"
    E = "E"
    W = "W"
    UP = "UP"
    DOWN = "DOWN"


class ScopeEnum(str, Enum):
    preview = "preview"
    apply = "apply"


class FilterModel(BaseModel):
    type: Optional[str] = None
    region: Optional[str] = None
    min_height_m: Optional[float] = None
    max_height_m: Optional[float] = None
    within_m_of: Optional[float] = None


class MagnitudeModel(BaseModel):
    value: Optional[float] = None
    unit: str = "m"


class IntentModel(BaseModel):
    operation: OperationEnum
    layer: LayerEnum = LayerEnum.structures
    filter: Optional[FilterModel] = None
    magnitude: Optional[MagnitudeModel] = None
    direction: Optional[DirectionEnum] = None
    scope: Optional[ScopeEnum] = None


# Strict JSON schema provided to Ollama for constrained structured decoding
INTENT_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "operation": {
            "type": "string",
            "enum": ["QUERY_HEIGHT", "SELECT_REGION", "EXTRUDE", "TRANSLATE", "FLATTEN", "UNKNOWN"],
        },
        "layer": {
            "type": "string",
            "enum": ["structures", "terrain", "roads", "vegetation"],
        },
        "filter": {
            "type": "object",
            "properties": {
                "min_height_m": {"type": ["number", "null"]},
                "max_height_m": {"type": ["number", "null"]},
                "region": {"type": ["string", "null"]}
            },
        },
        "magnitude": {
            "type": "object",
            "properties": {
                "value": {"type": ["number", "null"]},
                "unit": {"type": "string"},
            },
        },
        "direction": {
            "type": ["string", "null"],
            "enum": ["N", "S", "E", "W", "UP", "DOWN", None],
        },
        "scope": {
            "type": ["string", "null"],
            "enum": ["preview", "apply", None],
        },
    },
    "required": ["operation", "layer"],
}
