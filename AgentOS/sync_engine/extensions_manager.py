"""
Zo & Antigravity 2-Way Workspace Sync
Extensions manager — load, register, and push extensions between agents
"""
import json
import os
import shutil
from typing import Optional
from datetime import datetime, timezone

EXTENSIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "shared", "extensions")
INDEX_FILE = os.path.join(EXTENSIONS_DIR, "index.json")

DEFAULT_EXTENSIONS = [
    {
        "id": "code-mirror",
        "name": "Code Mirror",
        "version": "1.0.0",
        "description": "Live code editing sync between agents",
        "author": "system",
        "enabled": True,
        "compatible_with": ["antigravity", "zo"],
        "entry_point": "code_mirror/main.py",
        "capabilities": ["read_file", "write_file", "diff"]
    },
    {
        "id": "shell-relay",
        "name": "Shell Relay",
        "version": "1.0.0",
        "description": "Run shell commands on behalf of each other",
        "author": "system",
        "enabled": True,
        "compatible_with": ["antigravity", "zo"],
        "entry_point": "shell_relay/main.py",
        "capabilities": ["execute"]
    },
    {
        "id": "web-preview",
        "name": "Web Preview Sync",
        "version": "1.0.0",
        "description": "Stream live browser previews between agents",
        "author": "system",
        "enabled": False,
        "compatible_with": ["antigravity"],
        "entry_point": "web_preview/main.py",
        "capabilities": ["screenshot", "navigate"]
    },
    {
        "id": "context-bridge",
        "name": "Context Bridge",
        "version": "1.0.0",
        "description": "Share conversation context and memory snapshots",
        "author": "system",
        "enabled": True,
        "compatible_with": ["antigravity", "zo"],
        "entry_point": "context_bridge/main.py",
        "capabilities": ["read_context", "write_context"]
    }
]


def _load_index() -> list:
    os.makedirs(EXTENSIONS_DIR, exist_ok=True)
    if not os.path.exists(INDEX_FILE):
        _save_index(DEFAULT_EXTENSIONS)
        return DEFAULT_EXTENSIONS
    with open(INDEX_FILE) as f:
        return json.load(f)


def _save_index(extensions: list):
    os.makedirs(EXTENSIONS_DIR, exist_ok=True)
    with open(INDEX_FILE, "w") as f:
        json.dump(extensions, f, indent=2)


def list_extensions(agent_id: Optional[str] = None) -> list:
    exts = _load_index()
    if agent_id:
        return [e for e in exts if agent_id in e.get("compatible_with", [])]
    return exts


def get_extension(ext_id: str) -> Optional[dict]:
    exts = _load_index()
    return next((e for e in exts if e["id"] == ext_id), None)


def toggle_extension(ext_id: str, enabled: bool) -> Optional[dict]:
    exts = _load_index()
    for ext in exts:
        if ext["id"] == ext_id:
            ext["enabled"] = enabled
            _save_index(exts)
            return ext
    return None


def register_extension(ext: dict) -> dict:
    exts = _load_index()
    existing = next((e for e in exts if e["id"] == ext["id"]), None)
    if existing:
        exts = [e if e["id"] != ext["id"] else {**e, **ext} for e in exts]
    else:
        ext["registered_at"] = datetime.now(timezone.utc).isoformat()
        exts.append(ext)
    _save_index(exts)
    return ext


def unregister_extension(ext_id: str) -> bool:
    exts = _load_index()
    original_len = len(exts)
    exts = [e for e in exts if e["id"] != ext_id]
    if len(exts) < original_len:
        _save_index(exts)
        return True
    return False
