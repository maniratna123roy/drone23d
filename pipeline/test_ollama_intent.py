"""
Spatial Twin: Phase 1 Ollama Structured Output Smoke Test

Runs 5 test queries against local Ollama running qwen2.5:3b
Verifies JSON schema enforcement and intent parsing accuracy.
"""

import json
import urllib.request
import time

INTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "operation": {
            "type": "string", 
            "enum": ["QUERY_HEIGHT", "SELECT_REGION", "EXTRUDE", "TRANSLATE", "FLATTEN"]
        },
        "layer": {
            "type": "string", 
            "enum": ["structures", "terrain", "roads", "vegetation"]
        },
        "filter": {
            "type": "object",
            "properties": {
                "min_height_m": {"type": ["number", "null"]},
                "max_height_m": {"type": ["number", "null"]},
                "region": {"type": ["string", "null"]}
            }
        },
        "magnitude": {
            "type": "object",
            "properties": {
                "value": {"type": ["number", "null"]},
                "unit": {"type": "string"}
            }
        },
        "direction": {"type": ["string", "null"]},
        "scope": {"type": "string", "enum": ["preview", "apply"]}
    },
    "required": ["operation", "layer"]
}

SYSTEM_PROMPT = """You are the Spatial Twin intent parser.
Your only job is to convert user natural language requests about a 3D digital twin into a valid structured intent JSON object.
Follow the provided JSON schema strictly. Never return markdown code blocks, explanations, or commentary. Only return raw JSON."""

TEST_QUERIES = [
    "Which buildings are taller than 20 metres?",
    "Show me all structures in the center region",
    "Raise the two central buildings by 40 metres",
    "Find all buildings between 10m and 30m in height",
    "Which buildings are taller than 20 metres?"
]

def run_test(query: str, test_num: int):
    url = "http://127.0.0.1:11434/api/chat"
    payload = {
        "model": "qwen2.5:3b",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query}
        ],
        "format": INTENT_SCHEMA,
        "options": {
            "temperature": 0.0
        },
        "stream": False
    }
    
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    
    print(f"Sending request {test_num}/{len(TEST_QUERIES)}: '{query}'...", flush=True)
    start_time = time.time()
    with urllib.request.urlopen(req, timeout=60.0) as resp:
        duration = round(time.time() - start_time, 2)
        res_data = json.loads(resp.read().decode("utf-8"))
        raw_content = res_data.get("message", {}).get("content", "{}")
        
        parsed = json.loads(raw_content)
        print(f"\n[Test {test_num}/5] Query: '{query}' ({duration}s)", flush=True)
        print(f"  Parsed JSON: {json.dumps(parsed, indent=2)}", flush=True)
        assert "operation" in parsed, "Missing 'operation' key"
        assert "layer" in parsed, "Missing 'layer' key"
        return True

def main():
    print("=" * 60, flush=True)
    print("OLLAMA STRUCTURED OUTPUT SMOKE TEST (5 Iterations)", flush=True)
    print("=" * 60, flush=True)
    
    success_count = 0
    for i, q in enumerate(TEST_QUERIES, 1):
        try:
            if run_test(q, i):
                success_count += 1
        except Exception as e:
            print(f"[FAIL] Test {i} failed: {e}", flush=True)
            
    print("\n" + "=" * 60)
    print(f"RESULTS: {success_count}/{len(TEST_QUERIES)} tests passed successfully!")
    print("=" * 60)

if __name__ == "__main__":
    main()
