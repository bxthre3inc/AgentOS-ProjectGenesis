"""
Zo & Antigravity 2-Way Workspace Sync — Optimized Architecture
Session Sync: real-time IDE workspace context shared between agents.

Tracks: open files, active file, cursor position, running terminals,
debugger state, diagnostics — so AgentOS agents know exactly what
state Antigravity IDE is in, and vice versa.
"""
import json
import os
import time
import threading
from typing import Optional, Any
from datetime import datetime, timezone
from . import actions_log as alog

SESSION_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "shared", "session.json"
)

_lock = threading.Lock()
_on_change_hooks: list = []

DEFAULT_SESSION = {
    "antigravity": {
        "open_files": [],
        "active_file": None,
        "cursor": {"file": None, "line": 0, "col": 0},
        "running_terminals": [],
        "debugger": {"active": False, "breakpoints": [], "paused_at": None},
        "diagnostics": [],
        "selection": None,
        "updated_at": None
    },
    "zo": {
        "open_files": [],
        "active_file": None,
        "cursor": {"file": None, "line": 0, "col": 0},
        "running_terminals": [],
        "debugger": {"active": False, "breakpoints": [], "paused_at": None},
        "diagnostics": [],
        "selection": None,
        "updated_at": None
    }
}


def _load() -> dict:
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE) as f:
                data = json.load(f)
            # Merge in any missing keys from defaults
            for agent, defaults in DEFAULT_SESSION.items():
                if agent not in data:
                    data[agent] = defaults.copy()
                else:
                    for k, v in defaults.items():
                        data[agent].setdefault(k, v)
            return data
        except Exception:
            pass
    return {k: v.copy() for k, v in DEFAULT_SESSION.items()}


def _save(session: dict):
    os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
    with open(SESSION_FILE, "w") as f:
        json.dump(session, f, indent=2)


def get_session(agent_id: Optional[str] = None) -> dict:
    with _lock:
        data = _load()
    if agent_id:
        return data.get(agent_id, {})
    return data


def update_session(agent_id: str, patch: dict) -> dict:
    """Merge a partial patch into an agent's session state."""
    with _lock:
        data = _load()
        if agent_id not in data:
            data[agent_id] = DEFAULT_SESSION.get(agent_id, {}).copy()
        data[agent_id].update(patch)
        data[agent_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save(data)

    alog.record("session_update", agent_id, alog.CAT_SESSION,
                detail={"fields": list(patch.keys())})

    for hook in _on_change_hooks:
        try:
            hook(agent_id, patch)
        except Exception:
            pass

    return data[agent_id]


def open_file(agent_id: str, path: str) -> dict:
    session = get_session(agent_id)
    open_files = session.get("open_files", [])
    if path not in open_files:
        open_files.append(path)
    return update_session(agent_id, {
        "open_files": open_files,
        "active_file": path,
        "cursor": {"file": path, "line": 0, "col": 0}
    })


def close_file(agent_id: str, path: str) -> dict:
    session = get_session(agent_id)
    open_files = [f for f in session.get("open_files", []) if f != path]
    patch = {"open_files": open_files}
    if session.get("active_file") == path:
        patch["active_file"] = open_files[-1] if open_files else None
    return update_session(agent_id, patch)


def set_cursor(agent_id: str, file: str, line: int, col: int = 0) -> dict:
    return update_session(agent_id, {
        "cursor": {"file": file, "line": line, "col": col},
        "active_file": file
    })


def set_breakpoint(agent_id: str, file: str, line: int, add: bool = True) -> dict:
    session = get_session(agent_id)
    bps = session.get("debugger", {}).get("breakpoints", [])
    bp = {"file": file, "line": line}
    if add:
        if bp not in bps:
            bps.append(bp)
    else:
        bps = [b for b in bps if not (b["file"] == file and b["line"] == line)]
    debugger = session.get("debugger", {})
    debugger["breakpoints"] = bps
    return update_session(agent_id, {"debugger": debugger})


def add_diagnostic(agent_id: str, file: str, line: int,
                   message: str, severity: str = "error") -> dict:
    session = get_session(agent_id)
    diags = session.get("diagnostics", [])
    diags.append({"file": file, "line": line, "message": message,
                  "severity": severity,
                  "ts": datetime.now(timezone.utc).isoformat()})
    return update_session(agent_id, {"diagnostics": diags[-100:]})  # cap at 100


def clear_diagnostics(agent_id: str, file: Optional[str] = None) -> dict:
    session = get_session(agent_id)
    if file:
        diags = [d for d in session.get("diagnostics", []) if d["file"] != file]
    else:
        diags = []
    return update_session(agent_id, {"diagnostics": diags})


def register_change_hook(fn):
    """Register a callback fired on every session change (e.g. WS broadcast)."""
    _on_change_hooks.append(fn)
