"""
config.py — AgentOS Global Environment Configuration
Centralizes path resolution and system profiles.
"""
import os
import sys
import platform
import logging

# ── Environment Detection ─────────────────────────────────────────────────────
IS_LINUX = platform.system() == "Linux"
# Foxxd S67 / Mobile awareness (can be refined via build-time env vars)
IS_MOBILE = os.getenv("AGENTOS_PROFILE") == "mobile" or "android" in platform.version().lower()

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
MASTER_DB_PATH = os.path.join(RUNTIME_DIR, "agentos.db")

# ── Security ──────────────────────────────────────────────────────────────────
MESH_KEY_PATH = os.path.join(VAULT_DIR, "mesh.key")
ENCRYPTION_KEY_PATH = os.path.join(VAULT_DIR, "ledger.key") # Fernet Key

# ── Inference ─────────────────────────────────────────────────────────────────
# Profile-aware model selection
if IS_MOBILE:
    DEFAULT_MODEL = "phi3"
    FALLBACK_MODEL = "tinyllama"
else:
    DEFAULT_MODEL = os.getenv("AGENTOS_LLM_MODEL", "gpt-4o")
    FALLBACK_MODEL = "phi3"

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
