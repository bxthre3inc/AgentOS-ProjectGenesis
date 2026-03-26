"""
strategy_handlers.py — AgentOS Strategic Orchestration
Handles milestone decomposition and autonomous pivoting.
"""
import json
import logging
import db
from task_context import TaskContext

logger = logging.getLogger("agentos.strategy_handlers")

async def handle_milestone_sync(task: TaskContext) -> dict:
    """Decompose milestones into actionable TCOs."""
    company_id = task.payload.get("company_id")
    
    async with await db.get_db() as conn:
        # Fetch unplanned/pending milestones
        cursor = await conn.execute(
            "SELECT * FROM milestones WHERE tenant = ? AND status = 'planned'",
            (company_id,)
        )
        milestones = await cursor.fetchall()
        
        tasks_created = 0
        for m in milestones:
            # Generate a "Decomposition Request" TCO for the CEO or R&D Agent
            await conn.execute("""
                INSERT INTO sync_events (event_type, source, department_id, payload, tenant)
                VALUES ('task_decomposition', 'strategy_engine', ?, ?, ?)
            """, (m['dept_id'], json.dumps({
                "milestone_id": m['id'],
                "title": m['title'],
                "action": "decompose_to_tasks"
            }), company_id))
            
            # Update milestone to in_progress
            await conn.execute(
                "UPDATE milestones SET status = 'in_progress' WHERE id = ?",
                (m['id'],)
            )
            tasks_created += 1
            
        await conn.commit()
        
    return {"status": "ok", "message": f"Generated {tasks_created} decomposition TCOs."}

async def handle_pivot(task: TaskContext) -> dict:
    """Re-align the company by flushing obsolete tasks and updating milestones."""
    new_strategy = task.payload.get("new_strategy")
    company_id = task.payload.get("company_id")
    
    if not new_strategy:
        return {"status": "error", "message": "new_strategy is required"}

    async with await db.get_db() as conn:
        # 1. Archive pending tasks for this company
        await conn.execute(
            "UPDATE sync_events SET status = 'cancelled' WHERE tenant = ? AND status = 'pending'",
            (company_id,)
        )
        
        # 2. Inject the New Strategy TCO
        await conn.execute("""
            INSERT INTO sync_events (event_type, source, department_id, payload, tenant)
            VALUES ('strategic_pivot', 'kernel', 'board', ?, ?)
        """, (json.dumps({"description": new_strategy}), company_id))
        
        await conn.commit()

    return {"status": "ok", "message": f"Pivot executed for {company_id}. Pending tasks archived."}
