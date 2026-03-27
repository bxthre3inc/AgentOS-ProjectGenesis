import logging
import asyncio
from AgenticBusinessEmpire.core.db import RQE as db

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
        total = rows[0]["total"] if rows else 0.0
        return {"department": dept, "total_spent": float(total or 0.0)}

    async def validate_budget(self, dept: str, request_amount: float) -> bool:
        """Enforce financial stops based on the Master Ledger budgets table."""
        status = await self.get_budget_status(dept)
        total_spent = status.get("total_spent", 0.0)
        
        # Fetch the real budget limit from the database
        sql = "SELECT amount FROM budgets WHERE dept_id = $1 AND status = 'active' LIMIT 1"
        try:
            rows = await db.execute(sql, dept, fetch=True)
            limit = float(rows[0]["amount"]) if rows else 1000.0 # Default fallback if no budget set
        except Exception:
            limit = 1000.0

        if total_spent + request_amount > limit:
            logger.warning("[Ops] Budget exceeded for %s. Limit: %.2f, Requested: %.2f, Spent: %.2f", 
                           dept, limit, request_amount, total_spent)
            return False
            
        logger.info("[Ops] Budget check passed for %s. Remaining: %.2f", dept, limit - (total_spent + request_amount))
        return True

if __name__ == "__main__":
    # Integration test for Ops Agent in a real env
    pass
