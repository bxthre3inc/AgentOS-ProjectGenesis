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
    id              BIGSERIAL       PRIMARY KEY,
    tenant_id       TEXT            NOT NULL DEFAULT 'subsidiary_beta',
    subsidiary      TEXT            NOT NULL,           -- e.g. 'irrig8'
    recorded_at     TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    metric_name     TEXT            NOT NULL,           -- e.g. 'active_sensors'
    metric_value    DOUBLE PRECISION,
    metric_meta     JSONB           NOT NULL DEFAULT '{}',
    lat             DOUBLE PRECISION,
    lon             DOUBLE PRECISION,
    CONSTRAINT chk_subsidiary_health_tenant
        CHECK (tenant_id IN ('tenant_zero','product_alpha','subsidiary_beta'))
);
CREATE INDEX IF NOT EXISTS idx_sh_lat_lon
    ON subsidiary_health (lat, lon);
CREATE INDEX IF NOT EXISTS idx_sh_subsidiary_metric
    ON subsidiary_health (subsidiary, metric_name, recorded_at DESC);
"""

PRODUCT_ROADMAP_DDL = """
CREATE TABLE IF NOT EXISTS product_roadmap (
    id              BIGSERIAL       PRIMARY KEY,
    tenant_id       TEXT            NOT NULL DEFAULT 'product_alpha',
    product         TEXT            NOT NULL,           -- e.g. 'starting5'
    feature_id      TEXT            NOT NULL,
    feature_name    TEXT            NOT NULL,
    status          TEXT            NOT NULL DEFAULT 'pending',
    readiness_score SMALLINT        NOT NULL DEFAULT 0 CHECK (readiness_score BETWEEN 0 AND 100),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    meta            JSONB           NOT NULL DEFAULT '{}',
    CONSTRAINT chk_product_roadmap_status
        CHECK (status IN ('pending','in_progress','complete','blocked')),
    UNIQUE (product, feature_id)
);
CREATE INDEX IF NOT EXISTS idx_pr_product_status
    ON product_roadmap (product, status, readiness_score DESC);
"""

RECURSIVE_LOGS_DDL = """
CREATE TABLE IF NOT EXISTS recursive_logs (
    id              BIGSERIAL       PRIMARY KEY,
    tenant_id       TEXT            NOT NULL DEFAULT 'tenant_zero',
    patch_id        TEXT            NOT NULL UNIQUE,    -- uuid of the self-patch TCO
    applied_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    target_file     TEXT            NOT NULL,
    description     TEXT,
    diff_summary    TEXT,
    outcome         TEXT            NOT NULL DEFAULT 'success',
    meta            JSONB           NOT NULL DEFAULT '{}',
    CONSTRAINT chk_recursive_logs_outcome
        CHECK (outcome IN ('success','failed','rolled_back'))
);
CREATE INDEX IF NOT EXISTS idx_rl_applied_at
    ON recursive_logs (applied_at DESC);
"""

BXTHREE3_EMPLOYEES_DDL = """
CREATE TABLE IF NOT EXISTS bxthre3_employees (
    emp_id          UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT            NOT NULL,
    department      TEXT            NOT NULL,           -- e.g. 'kernel', 'product', 'agtech', 'corp'
    role            TEXT            NOT NULL,
    clearance_level SMALLINT        NOT NULL DEFAULT 1 CHECK (clearance_level BETWEEN 1 AND 5),
    joined_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    status          TEXT            NOT NULL DEFAULT 'active'
);
CREATE INDEX IF NOT EXISTS idx_emp_dept_clearance
    ON bxthre3_employees (department, clearance_level DESC);
"""

BXTHREE3_CORPORATE_LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS bxthre3_corporate_ledger (
    entry_id        BIGSERIAL       PRIMARY KEY,
    recorded_at     TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    amount          NUMERIC(15,2)   NOT NULL,
    description     TEXT            NOT NULL,
    department      TEXT            NOT NULL,           -- attribution
    meta            JSONB           NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_cl_date_dept
    ON bxthre3_corporate_ledger (recorded_at DESC, department);
"""

ALL_DDL = [
    SUBSIDIARY_HEALTH_DDL, PRODUCT_ROADMAP_DDL, RECURSIVE_LOGS_DDL,
    BXTHREE3_EMPLOYEES_DDL, BXTHREE3_CORPORATE_LEDGER_DDL
]


async def apply(pool: Any) -> None:
    """Apply all DDL statements.  Safe to call on every startup."""
    async with pool.acquire() as conn:
        for ddl in ALL_DDL:
            await conn.execute(ddl)
    logger.info("[schema] Master Ledger DDL applied (subsidiary_health, product_roadmap, recursive_logs).")


# ---------------------------------------------------------------------------
# Seed helpers (used by tests and the developer sandbox)
# ---------------------------------------------------------------------------
async def seed_product_roadmap(pool: Any, product: str, features: list[dict]) -> None:
    """Upsert a list of features into product_roadmap."""
    sql = """
        INSERT INTO product_roadmap (product, feature_id, feature_name, status, readiness_score, meta)
        VALUES ($1, $2, $3, $4, $5, $6::jsonb)
        ON CONFLICT (product, feature_id) DO UPDATE
            SET status = EXCLUDED.status,
                readiness_score = EXCLUDED.readiness_score,
                updated_at = NOW()
    """
    import json
    async with pool.acquire() as conn:
        for f in features:
            await conn.execute(
                sql, product, f["feature_id"], f["feature_name"],
                f.get("status", "pending"), f.get("readiness_score", 0),
                json.dumps(f.get("meta", {})),
            )
    logger.info("[schema] Seeded %d features for product '%s'.", len(features), product)


if __name__ == "__main__":
    print("--- AgentOS Schema DDL ---")
    for ddl in ALL_DDL:
        print(ddl)
