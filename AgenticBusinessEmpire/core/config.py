"""
config.py — AgenticBusinessEmpire Global Environment Configuration
Centralizes path resolution and system profiles.
"""
import os
import sys
import platform
import logging

def get_secret(key: str, default: str = None) -> str:
    """Fetch a secret from environment or local vault."""
    return os.getenv(key, default)

# ── Environment Detection ─────────────────────────────────────────────────────
IS_LINUX = platform.system() == "Linux"
# Foxxd S67 / Mobile awareness (can be refined via build-time env vars)
IS_MOBILE = os.getenv("AGENTIC_BUSINESS_EMPIRE_PROFILE") == "mobile" or "android" in platform.version().lower()

# Server detection (Zo.computer Hosting Services - 24GB RAM)
def _is_server():
    if os.getenv("AGENTIC_BUSINESS_EMPIRE_IS_SERVER") == "true":
        return True
    try:
        import psutil
        # Zo Basic plan comes with 24GB RAM. Anything above 16GB is considered server-class for us.
        return psutil.virtual_memory().total > (16 * 1024**3)
    except ImportError:
        return False

IS_SERVER = _is_server()

# ── Path Resolution ───────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")
SHARD_DIR = os.path.join(RUNTIME_DIR, "shards")
VAULT_DIR = os.path.join(BASE_DIR, "secrets", ".vault")
SHARED_DIR = os.path.join(BASE_DIR, "shared")

# Ensure critical directories exist
for d in [RUNTIME_DIR, SHARD_DIR, VAULT_DIR, SHARED_DIR]:
    os.makedirs(d, exist_ok=True)

PEER_REGISTRY_PATH = os.path.join(SHARED_DIR, "peer_registry.json")

# ── Database ──────────────────────────────────────────────────────────────────
MASTER_DB_PATH = os.path.join(RUNTIME_DIR, "agenticbusinessempire.db")

# ── Security ──────────────────────────────────────────────────────────────────
MESH_KEY_PATH = os.path.join(VAULT_DIR, "mesh.key")
ENCRYPTION_KEY_PATH = os.path.join(VAULT_DIR, "ledger.key") # Fernet Key

# ── Inference ─────────────────────────────────────────────────────────────────
# Profile-aware LOCAL-ONLY model selection (Open Source)
# Device: HP Chromebook A14 G5 / Foxxd HTH S67
# Server: Zo.computer Hosting Services (24GB RAM)

if IS_SERVER:
    # High-capacity server models: Optimized for 24GB RAM
    DEFAULT_MODEL    = os.getenv("AGENTIC_BUSINESS_EMPIRE_LLM_MODEL", "phi3:medium-128k") # 14B - Instruct
    MULTIMODAL_MODEL = "llava:13b-v1.6-vicuna-q4_K_M" 
    FALLBACK_MODEL   = "llama3:8b-instruct-q8_0"
else:
    # Optimized mobile/linux models: Optimized for 4GB RAM (S67/Chromebook)
    DEFAULT_MODEL    = os.getenv("AGENTIC_BUSINESS_EMPIRE_LLM_MODEL", "phi3:3.8b-mini-instruct-4k-q4_K_M")
    MULTIMODAL_MODEL = "moondream2:latest" # Efficient 1.6B multimodal
    FALLBACK_MODEL   = "tinyllama:1.1b-chat-v1.1-q4_K_M"

# Local Ollama endpoint by default
LLM_BASE_URL = os.getenv("AGENTIC_BUSINESS_EMPIRE_LLM_URL", "http://localhost:11434/v1")

# Native Voice Infrastructure (STT/TTS)
STT_ENDPOINT = os.getenv("AGENTIC_BUSINESS_EMPIRE_STT_URL", "http://localhost:5000/stt")
TTS_ENDPOINT = os.getenv("AGENTIC_BUSINESS_EMPIRE_TTS_URL", "http://localhost:5001/tts")
VOICE_ENGINE = "piper" if not IS_SERVER else "coqui"

# Corporate Communication (SignalWire IVR)
SIGNALWIRE_PROJECT_ID = get_secret("SIGNALWIRE_PROJECT_ID")
SIGNALWIRE_TOKEN      = get_secret("SIGNALWIRE_TOKEN")
SIGNALWIRE_SPACE      = get_secret("SIGNALWIRE_SPACE")

# ── Logging ───────────────────────────────────────────────────────────────────
def setup_logging(level=logging.INFO):
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(os.path.join(RUNTIME_DIR, "kernel.log"))
        ]
    )
