"""
schema.py — AgentOS Master Ledger DDL

Three top-level tables for the Bxthre3 PostgreSQL state store:

  subsidiary_health   — Real-time KPIs for Irrig8 (and future subsidiaries)
  product_roadmap     — Feature completion tracking for Starting5
  recursive_logs      — Audit trail of every self-patch applied to the kernel

All tables include `tenant_id` so the RQE can enforce row-level isolation.
Call `apply(pool)` at kernel startup after db.init_pool().
"""

from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger("agentos.schema")

# ---------------------------------------------------------------------------
# DDL — idempotent (CREATE TABLE IF NOT EXISTS everywhere)
# ---------------------------------------------------------------------------

SUBSIDIARY_HEALTH_DDL = """
CREATE TABLE IF NOT EXISTS subsidiary_health (
    id              INTEGER         PRIMARY KEY AUTOINCREMENT,
    tenant_id       TEXT            NOT NULL DEFAULT 'subsidiary_beta',
    subsidiary      TEXT            NOT NULL,           -- e.g. 'irrig8'
    recorded_at     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metric_name     TEXT            NOT NULL,           -- e.g. 'active_sensors'
    metric_value    REAL,
    metric_meta     TEXT            NOT NULL DEFAULT '{}',
    lat             REAL,
    lon             REAL,
    CONSTRAINT chk_subsidiary_health_tenant
        CHECK (tenant_id IN ('tenant_zero','product_alpha','subsidiary_beta'))
);
CREATE INDEX IF NOT EXISTS idx_sh_lat_lon
    ON subsidiary_health (lat, lon);
CREATE INDEX IF NOT EXISTS idx_sh_subsidiary_metric
    ON subsidiary_health (subsidiary, metric_name, recorded_at);
"""

PRODUCT_ROADMAP_DDL = """
CREATE TABLE IF NOT EXISTS product_roadmap (
    id              INTEGER         PRIMARY KEY AUTOINCREMENT,
    tenant_id       TEXT            NOT NULL DEFAULT 'product_alpha',
    product         TEXT            NOT NULL,           -- e.g. 'starting5'
    feature_id      TEXT            NOT NULL,
    feature_name    TEXT            NOT NULL,
    status          TEXT            NOT NULL DEFAULT 'pending',
    readiness_score INTEGER         NOT NULL DEFAULT 0,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    meta            TEXT            NOT NULL DEFAULT '{}',
    UNIQUE (product, feature_id)
);
CREATE INDEX IF NOT EXISTS idx_pr_product_status
    ON product_roadmap (product, status, readiness_score);
"""

RECURSIVE_LOGS_DDL = """
CREATE TABLE IF NOT EXISTS recursive_logs (
    id              INTEGER         PRIMARY KEY AUTOINCREMENT,
    tenant_id       TEXT            NOT NULL DEFAULT 'tenant_zero',
    patch_id        TEXT            NOT NULL UNIQUE,    -- uuid of the self-patch TCO
    applied_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    target_file     TEXT            NOT NULL,
    description     TEXT,
    diff_summary    TEXT,
    outcome         TEXT            NOT NULL DEFAULT 'success',
    meta            TEXT            NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_rl_applied_at
    ON recursive_logs (applied_at);
"""

BXTHREE3_EMPLOYEES_DDL = """
CREATE TABLE IF NOT EXISTS bxthre3_employees (
    emp_id          TEXT            PRIMARY KEY,
    name            TEXT            NOT NULL,
    department      TEXT            NOT NULL,           -- e.g. 'kernel', 'product', 'agtech', 'corp'
    role            TEXT            NOT NULL,
    clearance_level INTEGER         NOT NULL DEFAULT 1,
    joined_at       DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status          TEXT            NOT NULL DEFAULT 'active'
);
CREATE INDEX IF NOT EXISTS idx_emp_dept_clearance
    ON bxthre3_employees (department, clearance_level);
"""

BXTHREE3_CORPORATE_LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS bxthre3_corporate_ledger (
    entry_id        INTEGER         PRIMARY KEY AUTOINCREMENT,
    recorded_at     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    amount          REAL            NOT NULL,
    description     TEXT            NOT NULL,
    department      TEXT            NOT NULL,           -- attribution
    meta            TEXT            NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_cl_date_dept
    ON bxthre3_corporate_ledger (recorded_at, department);
"""

ALL_DDL = [
    SUBSIDIARY_HEALTH_DDL, PRODUCT_ROADMAP_DDL, RECURSIVE_LOGS_DDL,
    BXTHREE3_EMPLOYEES_DDL, BXTHREE3_CORPORATE_LEDGER_DDL
]


async def apply(pool: Any = None) -> None:
    """Apply all DDL statements using its own SQLite loop (standalone)."""
    import aiosqlite
    import os
    _DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "runtime", "agentos.db")
    
    async with aiosqlite.connect(_DB_PATH) as db:
        for ddl in ALL_DDL:
            try:
                await db.executescript(ddl)
            except Exception as e:
                logger.error(f"Failed to apply DDL: {e}")
        await db.commit()
    logger.info("[schema] Master Ledger SQLite Schema applied.")


# ---------------------------------------------------------------------------
# Seed helpers (used by tests and the developer sandbox)
# ---------------------------------------------------------------------------
async def seed_product_roadmap(product: str, features: list[dict]) -> None:
    """Upsert a list of features into product_roadmap using SQLite."""
    import aiosqlite
    import json
    import os
    _DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "runtime", "agentos.db")
    
    sql = """
        INSERT INTO product_roadmap (product, feature_id, feature_name, status, readiness_score, meta)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (product, feature_id) DO UPDATE
            SET status = EXCLUDED.status,
                readiness_score = EXCLUDED.readiness_score,
                updated_at = CURRENT_TIMESTAMP
    """
    async with aiosqlite.connect(_DB_PATH) as db:
        for f in features:
            await db.execute(
                sql, (product, f["feature_id"], f["feature_name"],
                f.get("status", "pending"), f.get("readiness_score", 0),
                json.dumps(f.get("meta", {})))
            )
        await db.commit()
    logger.info("[schema] Seeded %d features for product '%s'.", len(features), product)


if __name__ == "__main__":
    print("--- AgentOS Schema DDL ---")
    for ddl in ALL_DDL:
        print(ddl)
