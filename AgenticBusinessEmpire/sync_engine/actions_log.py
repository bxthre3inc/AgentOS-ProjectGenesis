"""
Zo & Antigravity 2-Way Workspace Sync
Shared Actions Log — append-only JSONL log at shared/actions.log
Captures EVERY action across both agents with full context.
"""
import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Optional

LOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "shared", "actions.log"
)

_lock = threading.Lock()

# Action categories
CAT_RESOURCE   = "resource"
CAT_SECRET     = "secret"
CAT_FEATURE    = "feature"
CAT_COMMAND    = "command"
CAT_MESSAGE    = "message"
CAT_EXTENSION  = "extension"
CAT_SYNC       = "sync"
CAT_SESSION    = "session"
CAT_SYSTEM     = "system"


def record(
    action: str,
    agent: str,
    category: str = CAT_SYSTEM,
    target_agent: Optional[str] = None,
    path: Optional[str] = None,
    detail: Optional[Any] = None,
    status: str = "ok",
    error: Optional[str] = None,
    trace_id: Optional[str] = None,
    latency_ms: Optional[float] = None,
):
    """
    Append a single action entry to shared/actions.log (JSONL format).

    Every call from anywhere in the system goes through here so the log
    is the single authoritative audit trail readable by both agents.
    """
    entry = {
        "ts":           datetime.now(timezone.utc).isoformat(),
        "action":       action,
        "agent":        agent,
        "category":     category,
        "status":       status,
    }
    if target_agent: entry["target_agent"] = target_agent
    if path:         entry["path"]         = path
    if trace_id:     entry["trace_id"]     = trace_id
    if latency_ms:   entry["latency_ms"]   = round(latency_ms, 2)
    if detail:       entry["detail"]       = detail if isinstance(detail, (str, int, float, bool)) \
                                                    else _safe_serial(detail)
    if error:        entry["error"]        = error

    line = json.dumps(entry, ensure_ascii=False)

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with _lock:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def _safe_serial(obj: Any) -> Any:
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)


def tail(n: int = 100) -> list[dict]:
    """Return the last n entries from the log."""
    if not os.path.exists(LOG_PATH):
        return []
    lines = []
    with _lock:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
    entries = []
    for line in lines[-n:]:
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return list(reversed(entries))


def search(
    agent: Optional[str] = None,
    category: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """Filter the actions log by agent, category, or action name."""
    all_entries = tail(max(limit * 10, 500))
    result = []
    for e in all_entries:
        if agent    and e.get("agent") != agent:       continue
        if category and e.get("category") != category: continue
        if action   and e.get("action") != action:     continue
        result.append(e)
        if len(result) >= limit:
            break
    return result


def clear():
    """Wipe the actions log (admin only)."""
    with _lock:
        if os.path.exists(LOG_PATH):
            with open(LOG_PATH, "w") as f:
                f.write("")
    record("log_cleared", "system", CAT_SYSTEM, detail="Actions log cleared by admin")
