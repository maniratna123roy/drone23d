import re
from typing import Optional
from backend.agent.intent_schema import (
    IntentModel,
    OperationEnum,
    LayerEnum,
    FilterModel,
    MagnitudeModel,
    ScopeEnum,
    DirectionEnum
)

def match_fallback_intent(text: str) -> Optional[IntentModel]:
    """
    Fast rule-based regex fallback to extract IntentModel from common demo phrases.
    Used if Ollama is unreachable, slow, or returns malformed output.
    """
    clean = text.strip().lower()

    # Detect target layer (default structures)
    layer = LayerEnum.structures
    if "terrain" in clean:
        layer = LayerEnum.terrain
    elif "road" in clean:
        layer = LayerEnum.roads
    elif "tree" in clean or "vegetation" in clean:
        layer = LayerEnum.vegetation

    # 1. Height range: between X and Y (e.g. "between 10m and 30m")
    range_match = re.search(r"between\s+(\d+(?:\.\d+)?)\s*(?:m|metres|meters)?\s+and\s+(\d+(?:\.\d+)?)\s*(?:m|metres|meters)?", clean)
    if range_match:
        min_h = float(range_match.group(1))
        max_h = float(range_match.group(2))
        region = _extract_region(clean)
        return IntentModel(
            operation=OperationEnum.QUERY_HEIGHT,
            layer=layer,
            filter=FilterModel(min_height_m=min_h, max_height_m=max_h, region=region)
        )

    # 2. Taller / higher than X (e.g. "taller than 20 metres", "> 20m")
    taller_match = re.search(r"(?:taller|higher|greater|more)\s+than\s+(\d+(?:\.\d+)?)\s*(?:m|metres|meters)?", clean)
    if not taller_match:
        taller_match = re.search(r">\s*(\d+(?:\.\d+)?)\s*(?:m|metres|meters)?", clean)

    if taller_match:
        min_h = float(taller_match.group(1))
        region = _extract_region(clean)
        return IntentModel(
            operation=OperationEnum.QUERY_HEIGHT,
            layer=layer,
            filter=FilterModel(min_height_m=min_h, region=region)
        )

    # 3. Shorter / lower than X (e.g. "shorter than 20 metres", "< 20m")
    shorter_match = re.search(r"(?:shorter|lower|less)\s+than\s+(\d+(?:\.\d+)?)\s*(?:m|metres|meters)?", clean)
    if not shorter_match:
        shorter_match = re.search(r"<\s*(\d+(?:\.\d+)?)\s*(?:m|metres|meters)?", clean)

    if shorter_match:
        max_h = float(shorter_match.group(1))
        region = _extract_region(clean)
        return IntentModel(
            operation=OperationEnum.QUERY_HEIGHT,
            layer=layer,
            filter=FilterModel(max_height_m=max_h, region=region)
        )

    # 4. Region query (e.g. "in the center region", "show center structures")
    region = _extract_region(clean)
    if region:
        # Check if it is an extrude/raise command
        extrude_match = re.search(r"(?:raise|extrude|increase)\s+.*?\s+by\s+(\d+(?:\.\d+)?)\s*(?:m|metres|meters)?", clean)
        if extrude_match:
            mag = float(extrude_match.group(1))
            return IntentModel(
                operation=OperationEnum.EXTRUDE,
                layer=layer,
                filter=FilterModel(region=region),
                magnitude=MagnitudeModel(value=mag, unit="m"),
                direction=DirectionEnum.UP,
                scope=ScopeEnum.preview
            )

        return IntentModel(
            operation=OperationEnum.SELECT_REGION,
            layer=layer,
            filter=FilterModel(region=region)
        )

    return None


def _extract_region(text: str) -> Optional[str]:
    known_regions = ["center", "central", "north", "south", "east", "west"]
    for r in known_regions:
        pattern = r"\b" + r + r"\b"
        if re.search(pattern, text):
            return "center" if r == "central" else r
    return None
