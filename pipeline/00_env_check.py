"""
Spatial Twin: Environment Verification & Diagnostic Script (Phase 1)

Checks:
1. Python runtime & version
2. PyTorch, CUDA runtime, NVIDIA GPU device, and total VRAM
3. PostGIS database connectivity (Docker on host port 5435)
4. Ollama local LLM service & qwen2.5:3b model readiness
"""

import sys
import os
import socket
import json
import urllib.request
import urllib.error

def check_python():
    print("=" * 60)
    print("1. PYTHON RUNTIME CHECK")
    print(f"   Python Executable : {sys.executable}")
    print(f"   Python Version    : {sys.version.split()[0]}")
    if sys.version_info >= (3, 10):
        print("   Status            : [OK] Python version compatible")
        return True
    else:
        print("   Status            : [WARN] Python 3.10+ recommended")
        return False

def check_cuda_and_gpu():
    print("-" * 60)
    print("2. NVIDIA GPU & PYTORCH CUDA CHECK")
    try:
        import torch
        print(f"   PyTorch Version   : {torch.__version__}")
        cuda_available = torch.cuda.is_available()
        print(f"   CUDA Available    : {cuda_available}")
        
        if cuda_available:
            device_name = torch.cuda.get_device_name(0)
            total_vram_gb = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 2)
            print(f"   GPU Device Name   : {device_name}")
            print(f"   Total VRAM        : {total_vram_gb} GB")
            print("   Status            : [OK] GPU & CUDA active")
            return True, total_vram_gb
        else:
            print("   Status            : [FAIL] CUDA is not available in PyTorch")
            return False, 0
    except ImportError:
        print("   Status            : [FAIL] PyTorch is not installed")
        return False, 0

def check_database():
    print("-" * 60)
    print("3. DOCKER POSTGIS DATABASE CHECK")
    host = os.environ.get("POSTGRES_HOST", "127.0.0.1")
    port = int(os.environ.get("POSTGRES_PORT", 5435))
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3.0)
    try:
        result = sock.connect_ex((host, port))
        if result == 0:
            print(f"   PostGIS Socket    : {host}:{port} is REACHABLE")
            print("   Status            : [OK] Database service online")
            return True
        else:
            print(f"   PostGIS Socket    : {host}:{port} is NOT reachable (Error code: {result})")
            print("   Status            : [FAIL] Ensure 'docker compose up -d db' is running")
            return False
    except Exception as e:
        print(f"   PostGIS Error     : {e}")
        return False
    finally:
        sock.close()

def check_ollama():
    print("-" * 60)
    print("4. OLLAMA LLM SERVICE CHECK")
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    tags_url = f"{base_url}/api/tags"
    
    try:
        req = urllib.request.Request(tags_url, headers={"User-Agent": "SpatialTwin-EnvCheck"})
        with urllib.request.urlopen(req, timeout=5.0) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                models = [m.get("name", "") for m in data.get("models", [])]
                print(f"   Ollama URL        : {base_url} is ONLINE")
                print(f"   Available Models  : {models}")
                
                target_model = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
                found = any(target_model in m for m in models)
                if found:
                    print(f"   Target Model      : '{target_model}' is READY")
                    print("   Status            : [OK] Ollama & Model ready for natural language translation")
                    return True
                else:
                    print(f"   Target Model      : '{target_model}' not found in models list")
                    print(f"   Action Required   : Run 'ollama pull {target_model}'")
                    print("   Status            : [WARN] Ollama is online, but model is still downloading")
                    return False
    except urllib.error.URLError as e:
        print(f"   Ollama Connection : Failed to connect to {base_url} ({e.reason})")
        print("   Status            : [FAIL] Ensure Ollama is running on your machine")
        return False
    except Exception as e:
        print(f"   Ollama Error      : {e}")
        return False

def main():
    py_ok = check_python()
    gpu_ok, vram = check_cuda_and_gpu()
    db_ok = check_database()
    ollama_ok = check_ollama()
    
    print("=" * 60)
    print("SUMMARY:")
    print(f"  • Python 3.10+    : {'PASS' if py_ok else 'FAIL'}")
    print(f"  • GPU / CUDA      : {'PASS' if gpu_ok else 'FAIL'} ({vram} GB VRAM)")
    print(f"  • PostGIS (DB)    : {'PASS' if db_ok else 'FAIL'}")
    print(f"  • Ollama + Qwen   : {'PASS' if ollama_ok else 'IN PROGRESS / PENDING'}")
    print("=" * 60)
    
    if py_ok and gpu_ok and db_ok and ollama_ok:
        print(">>> ALL CORE SERVICES HEALTHY! READY FOR PHASE 1 VERIFICATION. <<<")
    else:
        print(">>> Some services require attention (see logs above). <<<")

if __name__ == "__main__":
    main()
