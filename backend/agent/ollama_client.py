import json
import logging
import httpx
from typing import Optional

from backend.config import settings
from backend.agent.intent_schema import (
    IntentModel,
    INTENT_JSON_SCHEMA,
    OperationEnum
)
from backend.agent.fallback_matcher import match_fallback_intent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Spatial Twin intent parser.
Your only job is to convert user natural language requests about a 3D digital twin into a valid structured intent JSON object.
Rules:
- For queries asking for objects taller or higher than X metres, set operation='QUERY_HEIGHT' and filter.min_height_m = X.
- For queries asking for objects shorter than X metres, set operation='QUERY_HEIGHT' and filter.max_height_m = X.
- For queries asking for objects between X and Y metres, set filter.min_height_m = X and filter.max_height_m = Y.
- For queries asking about a region (e.g. center, north, south, east, west), set filter.region.
- For requests unrelated to the 3D twin, set operation='UNKNOWN'.
Return raw JSON strictly matching the schema."""


class OllamaClient:
    def __init__(self, base_url: str = settings.OLLAMA_BASE_URL, model: str = settings.OLLAMA_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def warmup(self) -> bool:
        """Pre-warms the model into GPU memory on server startup to prevent cold-start timeouts."""
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": "ping"}],
            "keep_alive": "60m",
            "stream": False,
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload)
                if resp.status_code == 200:
                    logger.info("Ollama model successfully pre-warmed and resident in memory.")
                    return True
        except Exception as e:
            logger.warning(f"Ollama warmup notice: {type(e).__name__}: {e or repr(e)}")
        return False

    async def parse_intent(self, text: str) -> IntentModel:
        """
        Takes raw English query string, calls local Ollama with schema constraint,
        and returns a validated IntentModel. Falls back to regex matcher if Ollama fails.
        """
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            "format": INTENT_JSON_SCHEMA,
            "options": {
                "temperature": 0.0
            },
            "keep_alive": "60m",
            "stream": False
        }

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    content = data.get("message", {}).get("content", "{}")
                    parsed_dict = json.loads(content)
                    return IntentModel.model_validate(parsed_dict)
                else:
                    logger.warning(f"Ollama returned status {resp.status_code}: {resp.text}")
        except Exception as e:
            err_details = f"{type(e).__name__}: {e}" if str(e) else repr(e)
            logger.warning(f"Ollama call failed ({err_details}). Attempting fallback matcher.")

        # Fallback to deterministic regex matcher
        fallback = match_fallback_intent(text)
        if fallback:
            return fallback

        # If completely unparseable or nonsense query
        return IntentModel(operation=OperationEnum.UNKNOWN)

ollama_client = OllamaClient()
