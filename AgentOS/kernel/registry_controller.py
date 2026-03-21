"""
registry_controller.py — AgentOS Multi-Tenant Security Registry

The Registry Controller enforces strict filesystem and data access
permissions for every tenant. It is the **security firewall** between
AgentOS components.

Permission model
----------------
  tenant_zero  (AgentOS Internal): ROOT — full read/write everywhere.
  product_alpha (Starting5):       read/write /tenants/starting5/src|dist only.
                                   NO access to Bxthre3 Master Ledger.
  subsidiary_beta (Irrig8):        read/write /tenants/irrig8/ + worksheets.
                                   NO access to Starting5 or Ledger.

Usage
-----
    registry = RegistryController()
    registry.assert_can_read("product_alpha", "/tenants/starting5/src/roster.py")  # OK
    registry.assert_can_read("product_alpha", "/kernel/db.py")                     # raises
    registry.assert_can_write("subsidiary_beta", "/tenants/irrig8/sensor_data/")   # OK
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

logger = logging.getLogger("agentos.registry")

Operation = Literal["read", "write"]

# ---------------------------------------------------------------------------
# Permission rules
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PermissionRule:
    tenant_id:  str
    path_prefix: str      # relative to AGENTOS root
    read:        bool
    write:       bool
    min_clearance: int = 1  # 1-5
    reason:      str = ""


_RULES: list[PermissionRule] = [
    # ── Tenant Zero: root access ──────────────────────────────────────────
    PermissionRule("tenant_zero",     "",                                    read=True,  write=True, min_clearance=5,
                   reason="Tenant Zero has root access for governance (Clearance L5)."),

    # ── Product Alpha (Starting5) ─────────────────────────────────────────
    PermissionRule("product_alpha",   "AgentOS/tenants/starting5/src",       read=True,  write=True,
                   reason="Starting5 owns its source directory."),
    PermissionRule("product_alpha",   "AgentOS/tenants/starting5/dist",      read=True,  write=True,
                   reason="Starting5 owns its distribution directory."),
    PermissionRule("product_alpha",   "AgentOS/tenants/starting5/ui",        read=True,  write=True,
                   reason="Starting5 owns its UI directory."),
    PermissionRule("product_alpha",   "AgentOS/tenants/starting5/sandbox",   read=True,  write=True,
                   reason="Starting5 owns its sandbox."),
    # Explicit denials (checked before generic deny)
    PermissionRule("product_alpha",   "AgentOS/tenants/agentos_internal",    read=False, write=False,
                   reason="Starting5 must NOT access the Bxthre3 Master Ledger."),
    PermissionRule("product_alpha",   "AgentOS/kernel",                      read=False, write=False,
                   reason="Starting5 must NOT access AgentOS kernel internals."),
    PermissionRule("product_alpha",   "AgentOS/tenants/irrig8",              read=False, write=False,
                   reason="Starting5 must NOT access Irrig8 data."),

    # ── Subsidiary Beta (Irrig8) ──────────────────────────────────────────
    PermissionRule("subsidiary_beta", "AgentOS/tenants/irrig8",              read=True,  write=True,
                   reason="Irrig8 owns its full tenant directory."),
    PermissionRule("subsidiary_beta", "AgentOS/runtime/tasks",               read=True,  write=True,
                   reason="Irrig8 may read/write TCOs (for worksheet triggers)."),
    # Explicit denials
    PermissionRule("subsidiary_beta", "AgentOS/tenants/agentos_internal",    read=False, write=False,
                   reason="Irrig8 must NOT access the Bxthre3 Master Ledger."),
    PermissionRule("subsidiary_beta", "AgentOS/kernel",                      read=False, write=False,
                   reason="Irrig8 must NOT access AgentOS kernel internals."),
    PermissionRule("subsidiary_beta", "AgentOS/tenants/starting5",           read=False, write=False,
                   reason="Irrig8 must NOT access Starting5 data."),
]


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------
class RegistryController:
    """Enforces multi-tenant R/W access control on all AgentOS paths."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or Path(__file__).parent.parent.parent
        self._audit: list[dict] = []

    # ------------------------------------------------------------------
    # Public assertion API
    # ------------------------------------------------------------------
    def assert_can_read(self, tenant_id: str, path: str) -> None:
        self._assert(tenant_id, path, "read")

    def assert_can_write(self, tenant_id: str, path: str) -> None:
        self._assert(tenant_id, path, "write")

    def can_read(self, tenant_id: str, path: str) -> bool:
        return self._check(tenant_id, path, "read")

    def can_write(self, tenant_id: str, path: str) -> bool:
        return self._check(tenant_id, path, "write")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    async def assert_can_access(self, tenant_id: str, path: str, op: Operation, emp_id: str | None = None) -> None:
        """Async version of access check that includes Clearance verification."""
        allowed = await self.check_access(tenant_id, path, op, emp_id)
        if not allowed:
            msg = f"[Registry] DENIED: tenant '{tenant_id}' {op} @ '{path}' (emp_id={emp_id})"
            self._log(tenant_id, path, op, allowed=False)
            logger.warning(msg)
            raise PermissionError(msg)
        self._log(tenant_id, path, op, allowed=True)

    async def check_access(self, tenant_id: str, path: str, op: Operation, emp_id: str | None = None) -> bool:
        """Check both tenant path rules and hierarchical employee clearance."""
        # 1. Tenant path check (sync)
        if not self._check(tenant_id, path, op):
            return False
        
        # 2. Clearance check (async)
        norm = self._normalise(path)
        match = self._find_rule(tenant_id, norm)
        
        if match and match.min_clearance > 1:
            if not emp_id:
                logger.warning("[Registry] No emp_id provided for path requiring Clearance %d", match.min_clearance)
                return False
            
            import db
            sql = "SELECT clearance_level FROM bxthre3_employees WHERE emp_id = $1"
            rows = await db.execute(sql, emp_id)
            level = rows[0]["clearance_level"] if rows else 0
            
            if level < match.min_clearance:
                logger.warning("[Registry] DENIED: emp %s has clearance %d, but %s requires %d", 
                               emp_id, level, path, match.min_clearance)
                return False
        
        return True

    def _find_rule(self, tenant_id: str, norm_path: str) -> PermissionRule | None:
        match: PermissionRule | None = None
        for rule in _RULES:
            if rule.tenant_id != tenant_id:
                continue
            rule_norm = self._normalise(rule.path_prefix)
            if norm_path.startswith(rule_norm):
                if match is None or len(rule.path_prefix) > len(match.path_prefix):
                    match = rule
        return match

    def _check(self, tenant_id: str, path: str, op: Operation) -> bool:
        norm = self._normalise(path)
        match = self._find_rule(tenant_id, norm)

        if match is None:
            return False

        allowed = match.read if op == "read" else match.write
        return allowed

    def _normalise(self, path: str) -> str:
        p = path.replace("\\", "/").strip("/")
        return p

    def _log(self, tenant_id: str, path: str, op: str, allowed: bool) -> None:
        self._audit.append({"tenant_id": tenant_id, "path": path,
                            "op": op, "allowed": allowed})

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------
    def audit_log(self) -> list[dict]:
        return list(self._audit)

    def clear_audit(self) -> None:
        self._audit.clear()


# ---------------------------------------------------------------------------
# Module-level singleton (import and use directly)
# ---------------------------------------------------------------------------
registry = RegistryController()
