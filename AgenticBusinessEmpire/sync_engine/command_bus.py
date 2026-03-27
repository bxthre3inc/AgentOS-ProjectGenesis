"""
Zo & Antigravity 2-Way Workspace Sync
Bidirectional command bus — issue commands between agents
"""
import json
import asyncio
import aiosqlite
import os
from typing import Any, Optional, Callable
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "secrets", ".vault", "state.db")

VALID_COMMANDS = {
    "ping": "Check if target agent is alive",
    "sync_now": "Force an immediate sync",
    "push_resource": "Push a resource to the target",
    "pull_resource": "Request a resource from the target",
    "toggle_feature": "Toggle a feature flag on the target",
    "load_extension": "Ask target to load an extension",
    "unload_extension": "Ask target to unload an extension",
    "send_message": "Post a message in the message queue",
    "set_secret": "Push a secret to the shared vault",
    "shell": "Execute a shell command (requires shell-relay extension)",
    "restart_sync": "Restart the sync engine",
}

_handlers: dict[str, Callable] = {}


def register_handler(command: str, handler: Callable):
    """Register a handler for incoming commands."""
    _handlers[command] = handler


async def issue_command(issuer: str, target: str, command: str,
                        args: Optional[dict] = None) -> int:
    """Queue a command from issuer → target. Returns command ID."""
    if command not in VALID_COMMANDS:
        raise ValueError(f"Unknown command: {command}. Valid: {list(VALID_COMMANDS)}")
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO commands (issuer, target, command, args) VALUES (?, ?, ?, ?)",
            (issuer, target, command, json.dumps(args or {}))
        )
        await db.commit()
        return cur.lastrowid


async def poll_commands(agent_id: str) -> list[dict]:
    """Fetch and dispatch queued commands for an agent."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM commands WHERE target = ? AND status = 'queued' ORDER BY created_at ASC",
            (agent_id,)
        )
        rows = await cur.fetchall()
        commands = [dict(r) for r in rows]

    results = []
    for cmd in commands:
        handler = _handlers.get(cmd["command"])
        result = {"dispatched": True, "handler": bool(handler)}
        if handler:
            try:
                result["output"] = await handler(json.loads(cmd["args"] or "{}"))
            except Exception as e:
                result["error"] = str(e)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE commands SET status = 'done', result = ?, executed_at = ? WHERE id = ?",
                (json.dumps(result), datetime.now(timezone.utc).isoformat(), cmd["id"])
            )
            await db.commit()
        results.append({**cmd, "result": result})

    return results


async def get_command_history(limit: int = 50) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM commands ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def post_message(from_agent: str, to_agent: str, topic: str, body: Any):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (from_agent, to_agent, topic, body) VALUES (?, ?, ?, ?)",
            (from_agent, to_agent, topic, json.dumps(body))
        )
        await db.commit()


async def get_messages(agent_id: str, unread_only: bool = True) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if unread_only:
            cur = await db.execute(
                "SELECT * FROM messages WHERE to_agent = ? AND read = 0 ORDER BY created_at ASC",
                (agent_id,)
            )
        else:
            cur = await db.execute(
                "SELECT * FROM messages WHERE to_agent = ? ORDER BY created_at DESC LIMIT 100",
                (agent_id,)
            )
        rows = await cur.fetchall()
        ids = [r["id"] for r in rows]

        if ids and unread_only:
            placeholders = ",".join("?" * len(ids))
            await db.execute(
                f"UPDATE messages SET read = 1 WHERE id IN ({placeholders})", ids
            )
            await db.commit()

        return [dict(r) for r in rows]
