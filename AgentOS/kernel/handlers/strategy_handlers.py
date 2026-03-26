import sys
import os
import logging
import json
import time

# Add kernel to path
_KERNEL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(_KERNEL_DIR)
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
from . import rating_engine
from . import provisioner

async def handle_idea_intake(task: TaskContext) -> dict:
    """Process a new idea seed into the Blue Ocean seeds table."""
    title = task.payload.get("title")
    description = task.payload.get("description", "")
    source = task.payload.get("pipeline_source", "BLUE_OCEAN_TEAM") # CHAIRMAN | BLUE_OCEAN_TEAM
    
    if not title:
        return {"status": "error", "message": "title is required"}

    # Dynamic Rating (Audit)
    audit_res = await rating_engine.audit_seed(title, description)

    async with await db.get_db() as conn:
        seed_id = f"SEED-{int(time.time())}"
        m = audit_res["metrics"]
        
        await conn.execute("""
            INSERT INTO blue_ocean_seeds 
            (seed_id, title, description, pipeline_source, core_fit, impl_cost, scalability, strat_divergence, overall_rating, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (seed_id, title, description, source, m["core_fit"], m["impl_cost"], m["scalability"], m["strat_divergence"], audit_res["overall"], audit_res["verdict"]))
        
        await conn.commit()
        
    return {
        "status": "ok", 
        "seed_id": seed_id, 
        "audit": audit_res,
        "message": f"Idea seeded in {source} pipeline with overall rating {audit_res['overall']}."
    }

async def handle_lifecycle_transition(task: TaskContext) -> dict:
    """Progress a company through the 6-stage lifecycle."""
    company_id = task.payload.get("company_id")
    new_state = task.payload.get("new_state")
    name = task.payload.get("name", "New Subsidiary")
    
    VALID_STATES = ["BLUE_OCEAN", "IDEA", "VALIDATION", "PROJECT", "DIVISION", "SUBSIDIARY", "EXIT"]
    if new_state not in VALID_STATES:
        return {"status": "error", "message": f"Invalid state. Must be one of {VALID_STATES}"}

    async with await db.get_db() as conn:
        await conn.execute(
            "UPDATE companies SET lifecycle_state = ? WHERE company_id = ?",
            (new_state, company_id)
        )
        await conn.commit()
        
    # If moving to SUBSIDIARY, trigger autonomous provisioner
    if new_state == "SUBSIDIARY":
        prov_res = await provisioner.provision_subsidiary(company_id, name)
        return {"status": "ok", "new_state": new_state, "provisioning": prov_res}

    return {"status": "ok", "new_state": new_state}
