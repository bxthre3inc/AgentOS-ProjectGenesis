"""
task_injector.py — AgenticBusinessEmpire Manual Task Utility
Allows for manual injection of Task Context Objects (TCOs) into the kernel.
"""
import db
import json
import logging

logger = logging.getLogger("agenticbusinessempire.task_injector")

async def inject_task(company_id: str, dept_id: str, event_type: str, payload: dict, priority: int = 5):
    """Manually insert a TCO into the sync_events table."""
    async with await db.get_db() as conn:
        await conn.execute("""
            INSERT INTO sync_events (event_type, source, department_id, payload, tenant, importance)
            VALUES (?, 'manual_entry', ?, ?, ?, ?)
        """, (event_type, dept_id, json.dumps(payload), company_id, priority))
        
        await conn.commit()
        
    logger.info(f"Manually injected {event_type} for {dept_id} in {company_id} (Priority: {priority})")
    return {"status": "ok", "message": "TCO Injected Successfully"}

async def clear_pending_tasks(company_id: str):
    """Emergency flush of pending tasks for a specific company."""
    async with await db.get_db() as conn:
        await conn.execute(
            "UPDATE sync_events SET status = 'cancelled' WHERE tenant = ? AND status = 'pending'",
            (company_id,)
        )
        await conn.commit()
    return {"status": "ok", "message": f"Tasks flushed for {company_id}"}
