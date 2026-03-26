"""
Zo & Antigravity 2-Way Workspace Sync
SQLite state-tracking database layer
"""
import aiosqlite
import json
import os
from datetime import datetime, timezone
from typing import Optional, Any
from cryptography.fernet import Fernet

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "secrets", ".vault", "state.db")
KEY_PATH = os.path.join(os.path.dirname(__file__), "..", "secrets", ".vault", "db.key")

class SecureData:
    _fernet = None

    @classmethod
    def get_cipher(cls):
        if cls._fernet is None:
            if os.path.exists(KEY_PATH):
                with open(KEY_PATH, 'rb') as f:
                    cls._fernet = Fernet(f.read().strip())
            else:
                # Fallback to plaintext if key is missing (dev mode)
                return None
        return cls._fernet

    @classmethod
    def encrypt(cls, data: str) -> str:
        cipher = cls.get_cipher()
        if not cipher or not data:
            return data
        return cipher.encrypt(data.encode()).decode()

    @classmethod
    def decrypt(cls, token: str) -> str:
        cipher = cls.get_cipher()
        if not cipher or not token:
            return token
        try:
            return cipher.decrypt(token.encode()).decode()
        except Exception:
            return token # Return as is if decryption fails (likely plaintext)

    @classmethod
    def encrypt_data(cls, data: Any) -> str:
        """Utility to JSON-dump and encrypt any data structure."""
        return cls.encrypt(json.dumps(data))

    @classmethod
    def decrypt_data(cls, token: str) -> Any:
        """Utility to decrypt and JSON-load any data structure."""
        raw = cls.decrypt(token)
        try:
            return json.loads(raw)
        except Exception:
            return raw

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
                department_id TEXT DEFAULT 'general',
                employee_id TEXT DEFAULT 'kernel',
                status      TEXT DEFAULT 'pending'
            );

            CREATE TABLE IF NOT EXISTS messages (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                from_agent      TEXT NOT NULL,
                to_agent        TEXT NOT NULL,
                source_tenant   TEXT DEFAULT 'agentos_internal',
                target_tenant   TEXT DEFAULT 'agentos_internal',
                topic           TEXT NOT NULL,
                body            TEXT,
                read            INTEGER DEFAULT 0,
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS commands (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                issuer          TEXT NOT NULL,
                target          TEXT NOT NULL,
                source_tenant   TEXT DEFAULT 'agentos_internal',
                target_tenant   TEXT DEFAULT 'agentos_internal',
                command         TEXT NOT NULL,
                args            TEXT,
                status          TEXT DEFAULT 'queued',
                result          TEXT,
                created_at      TEXT DEFAULT (datetime('now')),
                executed_at     TEXT
            );

            CREATE TABLE IF NOT EXISTS workforce (
                entity_id       TEXT PRIMARY KEY,
                tier            TEXT NOT NULL, -- agentic | human | robotic
                department      TEXT NOT NULL,
                tenant          TEXT NOT NULL,
                skills          TEXT DEFAULT '[]',
                status          TEXT DEFAULT 'active',
                last_active     TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS boards (
                board_id        TEXT PRIMARY KEY,
                company_id      TEXT NOT NULL,
                name            TEXT NOT NULL,
                config_json     TEXT, -- schema, views
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS cells (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                board_id        TEXT NOT NULL,
                row_id          TEXT NOT NULL,
                col_name        TEXT NOT NULL,
                value           TEXT,
                last_updated    TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS docs (
                doc_id          TEXT PRIMARY KEY,
                company_id      TEXT NOT NULL,
                title           TEXT NOT NULL,
                owner_id        TEXT NOT NULL,
                department      TEXT DEFAULT 'general',
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS doc_blocks (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id          TEXT NOT NULL,
                block_type      TEXT NOT NULL,
                content         TEXT,
                position        INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS invoices (
                invoice_id      TEXT PRIMARY KEY,
                company_id      TEXT NOT NULL,
                entity_id       TEXT NOT NULL,
                amount          REAL NOT NULL,
                currency        TEXT DEFAULT 'USD',
                stripe_id       TEXT,
                status          TEXT DEFAULT 'unpaid', -- unpaid | paid | void
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS payouts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id      TEXT NOT NULL,
                entity_id       TEXT NOT NULL, -- The workforce member
                amount          REAL NOT NULL,
                stripe_tx_id    TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS budgets (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id      TEXT NOT NULL,
                dept_id         TEXT NOT NULL,
                amount          REAL NOT NULL,
                period          TEXT DEFAULT 'monthly',
                status          TEXT DEFAULT 'active',
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS tax_provisions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id      TEXT NOT NULL,
                amount          REAL NOT NULL,
                tax_type        TEXT DEFAULT 'income',
                due_date        TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS funding_rounds (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id      TEXT NOT NULL,
                amount          REAL NOT NULL,
                funding_type    TEXT NOT NULL, -- grant | equity | debt
                source          TEXT NOT NULL,
                terms_json      TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS messages (
                message_id      INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id      TEXT NOT NULL,
                sender_id       TEXT NOT NULL,
                receiver_id     TEXT NOT NULL, -- 'dept_head' or specific employee_id
                content         TEXT NOT NULL,
                status          TEXT DEFAULT 'sent', -- sent | delivered | read
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS companies (
                company_id      TEXT PRIMARY KEY,
                name            TEXT NOT NULL,
                lifecycle_state TEXT DEFAULT 'BLUE_OCEAN', -- BLUE_OCEAN | IDEA | VALIDATION | PROJECT | DIVISION | SUBSIDIARY | EXIT
                parent_id       TEXT DEFAULT 'bxthre3_inc',
                ceo_entity_id   TEXT, -- Can be Human or Agent
                created_at      TEXT DEFAULT (datetime('now'))
            );

            -- THE IDEA PIPELINE (BLUE OCEAN INTAKE)
            CREATE TABLE IF NOT EXISTS blue_ocean_seeds (
                seed_id          TEXT PRIMARY KEY,
                title            TEXT NOT NULL,
                description      TEXT,
                pipeline_source  TEXT NOT NULL, -- CHAIRMAN | BLUE_OCEAN_TEAM
                core_fit         REAL DEFAULT 0.0,
                impl_cost        REAL DEFAULT 0.0,
                scalability      REAL DEFAULT 0.0,
                strat_divergence REAL DEFAULT 0.0,
                overall_rating   REAL DEFAULT 0.0,
                status           TEXT DEFAULT 'pending', -- pending | triaged | rejected | promoted
                created_at       TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS entities (
                entity_id       TEXT PRIMARY KEY,
                type            TEXT NOT NULL, -- client | partner | funder
                name            TEXT NOT NULL,
                balance         REAL DEFAULT 0.0,
                contract_data   TEXT, -- encrypted
                tenant          TEXT NOT NULL,
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS milestones (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                dept_id         TEXT NOT NULL,
                title           TEXT NOT NULL,
                description     TEXT,
                deadline        TEXT,
                status          TEXT DEFAULT 'planned', -- planned | in_progress | completed
                tenant          TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sops (

            CREATE TABLE IF NOT EXISTS resources (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL UNIQUE,
                path        TEXT NOT NULL,
                owner       TEXT NOT NULL,
                department  TEXT DEFAULT 'general',
                employee    TEXT DEFAULT 'kernel',
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
    # Encrypt payload if sensitive
    encrypted_payload = SecureData.encrypt(json.dumps(payload)) if payload else None
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO sync_events (event_type, source, target, path, payload) VALUES (?, ?, ?, ?, ?)",
            (event_type, source, target, path, encrypted_payload)
        )
        await db.commit()

async def post_hierarchical_message(company_id: str, sender_id: str, receiver_id: str, content: str):
    """Securely log a message in the Master Ledger."""
    encrypted_content = SecureData.encrypt(content)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO messages (company_id, sender_id, receiver_id, content)
            VALUES (?, ?, ?, ?)
        """, (company_id, sender_id, receiver_id, encrypted_content))
        await db.commit()


async def hire_employee(entity_id: str, tier: str, department: str, tenant: str, skills: list):
    """Securely hire a new workforce member."""
    encrypted_skills = SecureData.encrypt_data(skills)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO workforce (entity_id, tier, department, tenant, skills)
            VALUES (?, ?, ?, ?, ?)
        """, (entity_id, tier, department, tenant, encrypted_skills))
        await db.commit()

async def create_invoice(invoice_id: str, company_id: str, entity_id: str, amount: float, currency: str = "USD"):
    """Log an invoice securely."""
    # We encrypt the amount and entity_id for absolute privacy at rest
    enc_amount = SecureData.encrypt(str(amount))
    enc_entity = SecureData.encrypt(entity_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO invoices (invoice_id, company_id, entity_id, amount, currency)
            VALUES (?, ?, ?, ?, ?)
        """, (invoice_id, company_id, enc_entity, enc_amount, currency))
        await db.commit()
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
        events = []
        for r in rows:
            d = dict(r)
            if d.get("payload"):
                try:
                    # Decrypt and Parse JSON
                    decrypted = SecureData.decrypt(d["payload"])
                    d["payload"] = json.loads(decrypted)
                except Exception:
                    # Fallback to raw if not encrypted/invalid
                    pass
            events.append(d)
        return events


async def get_pending_commands(target: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM commands WHERE target = ? AND status = 'queued' ORDER BY created_at ASC",
            (target,)
        )
        rows = await cur.fetchall()
        cmds = []
        for r in rows:
            d = dict(r)
            if d.get("args"):
                # args might be encrypted
                d["args"] = SecureData.decrypt(d["args"])
            cmds.append(d)
        return cmds


async def resolve_command(command_id: int, result: Any):
    encrypted_result = SecureData.encrypt(json.dumps(result)) if result else None
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE commands SET status = 'done', result = ?, executed_at = datetime('now') WHERE id = ?",
            (encrypted_result, command_id)
        )
        await db.commit()
