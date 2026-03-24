"""
Zo & Antigravity 2-Way Workspace Sync
SQLite state-tracking database layer
"""
import aiosqlite
import json
import os
from datetime import datetime, timezone
from typing import Optional, Any

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "secrets", ".vault", "state.db")


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def init_db():
    """Initialize all database tables."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS sync_events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type  TEXT NOT NULL,
                source      TEXT NOT NULL,
                target      TEXT,
                path        TEXT,
                payload     TEXT,
                status      TEXT DEFAULT 'pending',
                created_at  TEXT DEFAULT (datetime('now')),
                resolved_at TEXT
            );

            CREATE TABLE IF NOT EXISTS messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                from_agent  TEXT NOT NULL,
                to_agent    TEXT NOT NULL,
                topic       TEXT NOT NULL,
                body        TEXT,
                read        INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS commands (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                issuer      TEXT NOT NULL,
                target      TEXT NOT NULL,
                command     TEXT NOT NULL,
                args        TEXT,
                status      TEXT DEFAULT 'queued',
                result      TEXT,
                created_at  TEXT DEFAULT (datetime('now')),
                executed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS resources (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL UNIQUE,
                path        TEXT NOT NULL,
                owner       TEXT NOT NULL,
                mime_type   TEXT,
                size_bytes  INTEGER DEFAULT 0,
                checksum    TEXT,
                shared_with TEXT DEFAULT '[]',
                tags        TEXT DEFAULT '[]',
                created_at  TEXT DEFAULT (datetime('now')),
                updated_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS agent_sessions (
                agent_id        TEXT PRIMARY KEY,
                display_name    TEXT,
                status          TEXT DEFAULT 'offline',
                last_seen       TEXT,
                mcp_session_id  TEXT,
                capabilities    TEXT DEFAULT '[]'
            );

            CREATE INDEX IF NOT EXISTS idx_sync_events_source ON sync_events(source);
            CREATE INDEX IF NOT EXISTS idx_messages_to ON messages(to_agent, read);
            CREATE INDEX IF NOT EXISTS idx_commands_target ON commands(target, status);
        """)
        await db.commit()


async def log_event(event_type: str, source: str, target: Optional[str] = None,
                    path: Optional[str] = None, payload: Optional[Any] = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO sync_events (event_type, source, target, path, payload) VALUES (?, ?, ?, ?, ?)",
            (event_type, source, target, path, json.dumps(payload) if payload else None)
        )
        await db.commit()


async def update_agent_session(agent_id: str, status: str, display_name: str = "",
                                mcp_session_id: str = "", capabilities: list = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO agent_sessions (agent_id, display_name, status, last_seen, mcp_session_id, capabilities)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(agent_id) DO UPDATE SET
                status = excluded.status,
                last_seen = excluded.last_seen,
                mcp_session_id = excluded.mcp_session_id,
                display_name = CASE WHEN excluded.display_name != '' THEN excluded.display_name ELSE display_name END,
                capabilities = CASE WHEN excluded.capabilities != '[]' THEN excluded.capabilities ELSE capabilities END
        """, (agent_id, display_name, status, datetime.now(timezone.utc).isoformat(),
              mcp_session_id, json.dumps(capabilities or [])))
        await db.commit()


async def get_recent_events(limit: int = 50) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM sync_events ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_pending_commands(target: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM commands WHERE target = ? AND status = 'queued' ORDER BY created_at ASC",
            (target,)
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def resolve_command(command_id: int, result: Any):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE commands SET status = 'done', result = ?, executed_at = datetime('now') WHERE id = ?",
            (json.dumps(result), command_id)
        )
        await db.commit()
