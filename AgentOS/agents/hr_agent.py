"""
hr_agent.py — Bxthre3 Inc. HR Agent

Responsible for the Employee Registry and Clearance levels.
"""
import sys
from pathlib import Path

# Add project root to sys.path
root = Path(__file__).parent.parent
sys.path.append(str(root))

import logging
import asyncio
from kernel import db

logger = logging.getLogger("bxthre3.hr")

class HRAgent:
    """
    Manages employee records and clearance levels.
    """

    async def onboard_employee(self, name: str, dept: str, role: str, clearance: int) -> dict:
        """Add a new employee (human or agent) to the Bxthre3 registry."""
        sql = """
            INSERT INTO bxthre3_employees (name, department, role, clearance_level)
            VALUES ($1, $2, $3, $4)
            RETURNING emp_id, joined_at
        """
        try:
            rows = await db.execute(sql, name, dept, role, clearance)
            result = rows[0] if rows else {}
            logger.info("[HR] Onboarded %s (%s) to %s.", name, role, dept)
            return {"status": "success", "emp_id": str(result.get("emp_id")), "joined_at": result.get("joined_at")}
        except Exception as exc:
            logger.error("[HR] Onboarding failed: %s", exc)
            return {"status": "failed", "error": str(exc)}

    async def audit_clearance(self, emp_id: str) -> int:
        """Fetch the clearance level for an employee."""
        sql = "SELECT clearance_level FROM bxthre3_employees WHERE emp_id = $1"
        rows = await db.execute(sql, emp_id)
        return rows[0]["clearance_level"] if rows else 0

if __name__ == "__main__":
    hr = HRAgent()
    # Mock onboarding for testing
    asyncio.run(hr.onboard_employee("Dev Lead", "kernel", "L5 Engineer", 5))
