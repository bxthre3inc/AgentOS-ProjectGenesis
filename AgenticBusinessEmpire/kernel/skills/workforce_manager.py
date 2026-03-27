"""
workforce_manager.py — AgenticBusinessEmpire Onboarding Utility
Simplifies hiring and assignment of employees across the conglomerate.
"""
from AgenticBusinessEmpire.core.db import RQE as db
import json
import logging
import asyncio
from typing import Dict, Any

logger = logging.getLogger("agenticbusinessempire.workforce_manager")

async def add_employee(company_id: str, dept_id: str, role: str, employee_type: str = "agentic", name: str = None):
    """Add a new employee to the workforce registry."""
    employee_id = f"{employee_type}_{role.lower()}_{name.lower().replace(' ', '_') if name else 'instance'}"
    
    await db.execute("""
        INSERT INTO workforce (employee_id, company_id, department_id, employee_type, name, role, status)
        VALUES ($1, $2, $3, $4, $5, $6, 'idle')
        ON CONFLICT (employee_id) DO UPDATE SET status = 'idle'
    """, employee_id, company_id, dept_id, employee_type, name or employee_id, role, fetch=False)
        
    logger.info(f"Hired {employee_type} as {role} in {dept_id} for {company_id}")
    return {"status": "ok", "employee_id": employee_id}

async def list_roster(company_id: str):
    """Get the full roster for a specific company."""
    return await db.execute("SELECT * FROM workforce WHERE company_id = $1", company_id)

async def delegate_task(employee_id: str, task_context: Dict[str, Any]):
    """Assign a task to an employee and update their status."""
    task_id = task_context.get("task_id")
    logger.info(f"Delegating task {task_id} to {employee_id}")
    
    # Update employee status to 'busy'
    await db.execute("UPDATE workforce SET status = 'busy' WHERE employee_id = $1", employee_id, fetch=False)
    
    # In a real implementation, this would trigger an agent action or notify a human.
    return {
        "status": "delegated",
        "employee_id": employee_id,
        "task_id": task_id
    }

async def report_task_completion(employee_id: str, task_id: str, result: str = "success"):
    """Update employee status to 'idle' and log completion."""
    logger.info(f"Employee {employee_id} completed task {task_id} with result: {result}")
    await db.execute("UPDATE workforce SET status = 'idle' WHERE employee_id = $1", employee_id, fetch=False)
    return {"status": "ok"}

async def get_workforce_capacity(company_id: str):
    """Calculate current idle vs busy agents."""
    roster = await list_roster(company_id)
    idle = [e for e in roster if e.get("status") == "idle"]
    busy = [e for e in roster if e.get("status") == "busy"]
    return {
        "total": len(roster),
        "idle": len(idle),
        "busy": len(busy),
        "availability_score": (len(idle) / len(roster)) if roster else 0
    }
