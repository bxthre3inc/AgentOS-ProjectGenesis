"""
Zo & Antigravity 2-Way Workspace Sync
Feature flag management with per-agent overrides
"""
import json
import os
from typing import Any, Optional
from datetime import datetime, timezone

FEATURES_DIR = os.path.join(os.path.dirname(__file__), "..", "shared", "features")
FEATURES_FILE = os.path.join(FEATURES_DIR, "flags.json")

DEFAULT_FLAGS = {
    "bidirectional_sync": {
        "enabled": True,
        "description": "Allow both agents to push and pull workspace changes",
        "owner": "system",
        "overrides": {}
    },
    "command_execution": {
        "enabled": True,
        "description": "Allow agents to issue commands to each other",
        "owner": "system",
        "overrides": {}
    },
    "secrets_sharing": {
        "enabled": True,
        "description": "Allow shared secrets in the vault",
        "owner": "system",
        "overrides": {}
    },
    "extension_push": {
        "enabled": True,
        "description": "Allow agents to push extensions to each other",
        "owner": "system",
        "overrides": {}
    },
    "auto_accept_resources": {
        "enabled": False,
        "description": "Auto-accept incoming resources without confirmation",
        "owner": "system",
        "overrides": {}
    },
    "read_only_mode": {
        "enabled": False,
        "description": "Put the workspace in read-only mode (no writes)",
        "owner": "system",
        "overrides": {}
    },
    "live_dashboard": {
        "enabled": True,
        "description": "Enable the browser dashboard",
        "owner": "system",
        "overrides": {}
    }
}


def _load_flags() -> dict:
    os.makedirs(FEATURES_DIR, exist_ok=True)
    if not os.path.exists(FEATURES_FILE):
        _save_flags(DEFAULT_FLAGS)
        return DEFAULT_FLAGS
    with open(FEATURES_FILE) as f:
        return json.load(f)


def _save_flags(flags: dict):
    os.makedirs(FEATURES_DIR, exist_ok=True)
    with open(FEATURES_FILE, "w") as f:
        json.dump(flags, f, indent=2)


def get_flag(name: str, agent_id: Optional[str] = None) -> bool:
    flags = _load_flags()
    flag = flags.get(name)
    if not flag:
        return False
    if agent_id and agent_id in flag.get("overrides", {}):
        return flag["overrides"][agent_id]
    return flag.get("enabled", False)


def set_flag(name: str, enabled: bool, agent_id: Optional[str] = None,
             issuer: str = "system") -> dict:
    flags = _load_flags()
    if name not in flags:
        flags[name] = {
            "enabled": enabled,
            "description": f"Custom flag: {name}",
            "owner": issuer,
            "overrides": {}
        }
    if agent_id:
        flags[name]["overrides"][agent_id] = enabled
    else:
        flags[name]["enabled"] = enabled
    _save_flags(flags)
    return flags[name]


def list_flags(agent_id: Optional[str] = None) -> list:
    flags = _load_flags()
    result = []
    for name, data in flags.items():
        effective = data.get("enabled", False)
        if agent_id and agent_id in data.get("overrides", {}):
            effective = data["overrides"][agent_id]
        result.append({
            "name": name,
            "enabled": effective,
            "description": data.get("description", ""),
            "owner": data.get("owner", "system"),
            "has_overrides": bool(data.get("overrides"))
        })
    return result


def create_flag(name: str, enabled: bool, description: str, owner: str) -> dict:
    flags = _load_flags()
    flags[name] = {
        "enabled": enabled,
        "description": description,
        "owner": owner,
        "overrides": {},
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    _save_flags(flags)
    return flags[name]


def delete_flag(name: str) -> bool:
    flags = _load_flags()
    if name in flags and flags[name].get("owner") != "system":
        del flags[name]
        _save_flags(flags)
        return True
    return False
