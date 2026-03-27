"""
Zo & Antigravity 2-Way Workspace Sync
File-system watcher + sync core
"""
import asyncio
import hashlib
import json
import os
import shutil
from typing import Callable, Optional
from datetime import datetime, timezone
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WATCH_DIRS = ["shared", "agents"]
IGNORE_PATTERNS = {".tmp", ".DS_Store", "__pycache__", ".pyc", "state.db",
                   "secrets.enc", ".salt", ".swp"}

# Battery Saver for Foxxd S67 / Mobile
BATTERY_SAVER_MODE = os.getenv("AGENTIC_BUSINESS_EMPIRE_BATTERY_SAVER", "false").lower() == "true"
POLL_INTERVAL = int(os.getenv("AGENTIC_BUSINESS_EMPIRE_POLL_INTERVAL", "60"))

_ws_broadcast: Optional[Callable] = None  # injected by API at startup


def set_broadcaster(fn: Callable):
    global _ws_broadcast
    _ws_broadcast = fn


async def broadcast_event(event_dict: dict):
    """Global hook to push a WebSocket event to all dashboard clients."""
    if _ws_broadcast:
        await _ws_broadcast(event_dict)


def _should_ignore(path: str) -> bool:
    parts = path.replace("\\", "/").split("/")
    for part in parts:
        if any(pat in part for pat in IGNORE_PATTERNS):
            return True
        if part.startswith(".vault"):
            return True
    return False


def _checksum(path: str) -> str:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
    except (IOError, OSError):
        pass
    return h.hexdigest()


def _make_event(kind: str, path: str, source: str = "watcher") -> dict:
    rel = os.path.relpath(path, WORKSPACE_ROOT)
    return {
        "kind": kind,
        "path": rel,
        "source": source,
        "checksum": _checksum(path) if os.path.isfile(path) else None,
        "size": os.path.getsize(path) if os.path.isfile(path) else 0,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


class SyncEventHandler(FileSystemEventHandler):
    def __init__(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop

    def _emit(self, event_dict: dict):
        if _ws_broadcast:
            asyncio.run_coroutine_threadsafe(
                _ws_broadcast(event_dict), self.loop
            )

    def on_created(self, event: FileSystemEvent):
        if event.is_directory or _should_ignore(event.src_path):
            return
        self._emit(_make_event("created", event.src_path))

    def on_modified(self, event: FileSystemEvent):
        if event.is_directory or _should_ignore(event.src_path):
            return
        self._emit(_make_event("modified", event.src_path))

    def on_deleted(self, event: FileSystemEvent):
        if event.is_directory or _should_ignore(event.src_path):
            return
        rel = os.path.relpath(event.src_path, WORKSPACE_ROOT)
        self._emit({
            "kind": "deleted",
            "path": rel,
            "source": "watcher",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    def on_moved(self, event: FileSystemEvent):
        if event.is_directory or _should_ignore(event.src_path):
            return
        self._emit({
            "kind": "moved",
            "src_path": os.path.relpath(event.src_path, WORKSPACE_ROOT),
            "dest_path": os.path.relpath(event.dest_path, WORKSPACE_ROOT),
            "source": "watcher",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })


_observer: Optional[Observer] = None


def start_watcher(loop: asyncio.AbstractEventLoop):
    global _observer
    
    if BATTERY_SAVER_MODE:
        print(f"🔋 Battery Saver Active: Polling mesh every {POLL_INTERVAL}s")
        asyncio.run_coroutine_threadsafe(_poll_loop(), loop)
        return None

    handler = SyncEventHandler(loop)
    _observer = Observer()
    for watch_dir in WATCH_DIRS:
        abs_dir = os.path.join(WORKSPACE_ROOT, watch_dir)
        os.makedirs(abs_dir, exist_ok=True)
        _observer.schedule(handler, abs_dir, recursive=True)
    _observer.start()
    return _observer

async def _poll_loop():
    """Low-power periodic scan for standalone mobile devices."""
    last_snap = {}
    while True:
        await asyncio.sleep(POLL_INTERVAL)
        snap = snapshot_workspace()
        for path, info in snap.items():
            if path not in last_snap or last_snap[path]["checksum"] != info["checksum"]:
                await broadcast_event({"kind": "modified", "path": path, "source": "polling"})
        last_snap = snap


def stop_watcher():
    global _observer
    if _observer:
        _observer.stop()
        _observer.join()
        _observer = None


def snapshot_workspace() -> dict:
    """Return a complete snapshot of all watched files."""
    snap = {}
    for watch_dir in WATCH_DIRS:
        abs_dir = os.path.join(WORKSPACE_ROOT, watch_dir)
        for root, _, files in os.walk(abs_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                if _should_ignore(fpath):
                    continue
                rel = os.path.relpath(fpath, WORKSPACE_ROOT)
                snap[rel] = {
                    "checksum": _checksum(fpath),
                    "size": os.path.getsize(fpath),
                    "mtime": os.path.getmtime(fpath)
                }
    return snap


def write_resource(rel_path: str, content: bytes, overwrite: bool = True) -> dict:
    abs_path = os.path.join(WORKSPACE_ROOT, rel_path)
    if not overwrite and os.path.exists(abs_path):
        return {"ok": False, "error": "File exists"}
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "wb") as f:
        f.write(content)
    return {"ok": True, "path": rel_path, "size": len(content)}


def read_resource(rel_path: str) -> Optional[bytes]:
    abs_path = os.path.join(WORKSPACE_ROOT, rel_path)
    if not os.path.exists(abs_path):
        return None
    with open(abs_path, "rb") as f:
        return f.read()


def delete_resource(rel_path: str) -> bool:
    abs_path = os.path.join(WORKSPACE_ROOT, rel_path)
    if os.path.exists(abs_path):
        os.remove(abs_path)
        return True
    return False
