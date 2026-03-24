"""
Zo & Antigravity 2-Way Workspace Sync — Optimized Architecture
Mutual API Key authentication middleware for server-to-server calls.
"""
import os
import secrets
import json
import hashlib
import time
from typing import Optional
from fastapi import Request, HTTPException
from fastapi.security import APIKeyHeader
from . import actions_log as alog

KEYS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "secrets", ".vault", "api_keys.json"
)
_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# In-memory key store: { hash(key): {agent_id, scopes, created_at} }
_keys: dict[str, dict] = {}


def _load():
    global _keys
    if os.path.exists(KEYS_FILE):
        with open(KEYS_FILE) as f:
            _keys = json.load(f)


def _save():
    os.makedirs(os.path.dirname(KEYS_FILE), exist_ok=True)
    with open(KEYS_FILE, "w") as f:
        json.dump(_keys, f, indent=2)


_load()


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def generate_key(agent_id: str, scopes: list[str] = None) -> str:
    """Generate a new API key for an agent. Returns the raw key (shown once)."""
    raw = f"zag-{secrets.token_urlsafe(32)}"
    h = _hash(raw)
    _keys[h] = {
        "agent_id": agent_id,
        "scopes": scopes or ["*"],
        "created_at": time.time(),
        "last_used": None
    }
    _save()
    alog.record("api_key_generated", agent_id, alog.CAT_SESSION,
                detail={"scopes": scopes or ["*"]})
    return raw


def validate_key(raw_key: str) -> Optional[dict]:
    """Validate an API key. Returns the key record or None."""
    h = _hash(raw_key)
    record = _keys.get(h)
    if record:
        record["last_used"] = time.time()
        _save()
    return record


def revoke_key_for_agent(agent_id: str) -> int:
    """Revoke all keys for an agent. Returns number revoked."""
    to_remove = [h for h, r in _keys.items() if r["agent_id"] == agent_id]
    for h in to_remove:
        del _keys[h]
    if to_remove:
        _save()
    return len(to_remove)


def list_keys() -> list[dict]:
    return [{"agent_id": r["agent_id"], "scopes": r["scopes"],
             "created_at": r["created_at"], "last_used": r["last_used"]}
            for r in _keys.values()]


# ── FastAPI middleware ─────────────────────────────────────────────────────────

async def require_auth(request: Request) -> Optional[dict]:
    """
    Dependency: validates X-API-Key header.
    If no keys are configured, allows all (open mode for local dev).
    Returns the key record or None (open mode).
    """
    if not _keys:
        return None  # No keys configured → open/dev mode

    raw = request.headers.get("X-API-Key", "")
    if not raw:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    record = validate_key(raw)
    if not record:
        alog.record("auth_denied", "unknown", alog.CAT_SESSION,
                    status="denied", error="Invalid API key")
        raise HTTPException(status_code=403, detail="Invalid API key")

    return record


def has_scope(key_record: Optional[dict], scope: str) -> bool:
    if key_record is None:
        return True  # open mode
    scopes = key_record.get("scopes", [])
    return "*" in scopes or scope in scopes
