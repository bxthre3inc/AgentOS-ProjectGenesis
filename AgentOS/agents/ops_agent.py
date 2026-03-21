"""
ops_agent.py — Bxthre3 Inc. Operations Agent

Responsible for corporate resource allocation and budget tracking.
"""
import sys
from pathlib import Path

# Add project root to sys.path
root = Path(__file__).parent.parent
sys.path.append(str(root))

import logging
import asyncio
from kernel import db

logger = logging.getLogger("bxthre3.ops")

class OpsAgent:
    """
    Manages corporate resources and the ledger.
    """

    async def log_expense(self, amount: float, description: str, dept: str) -> dict:
        """Record a department expense in the corporate ledger."""
        sql = """
            INSERT INTO bxthre3_corporate_ledger (amount, description, department)
            VALUES ($1, $2, $3)
            RETURNING entry_id, recorded_at
        """
        try:
            rows = await db.execute(sql, amount, description, dept, fetch=True)
            result = rows[0] if rows else {}
            logger.info("[Ops] Recorded expense: %s (%.2f) to %s.", description, amount, dept)
            return {"status": "success", "entry_id": result.get("entry_id"), "date": result.get("recorded_at")}
        except Exception as exc:
            logger.error("[Ops] Ledger entry failed: %s", exc)
            return {"status": "failed", "error": str(exc)}

    async def get_budget_status(self, dept: str) -> dict:
        """Summarize expenses for a department."""
        sql = "SELECT SUM(amount) as total FROM bxthre3_corporate_ledger WHERE department = $1"
        rows = await db.execute(sql, dept)
        return {"department": dept, "total_spent": float(rows[0]["total"] or 0.0)}

if __name__ == "__main__":
    ops = OpsAgent()
    # Mock expense for testing
    asyncio.run(ops.log_expense(5000.0, "Infrastructure Bootstrap", "corp"))
