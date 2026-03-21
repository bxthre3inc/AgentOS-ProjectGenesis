"""
corporate_handlers.py — Handlers for Bxthre3 corporate operations (HR & Ops)
"""
import logging
from task_context import TaskContext
from agents.hr_agent import HRAgent
from agents.ops_agent import OpsAgent

logger = logging.getLogger("agentos.handlers.corporate")

hr = HRAgent()
ops = OpsAgent()

async def handle_onboard(task: TaskContext) -> dict:
    """Action: onboard — calls HRAgent.onboard_employee"""
    name = task.payload.get("name")
    dept = task.payload.get("department")
    role = task.payload.get("role")
    clearance = task.payload.get("clearance", 1)
    
    if not all([name, dept, role]):
        return {"status": "failed", "error": "Missing name, department, or role in payload."}
    
    result = await hr.onboard_employee(name, dept, role, clearance)
    return result

async def handle_expense(task: TaskContext) -> dict:
    """Action: expense — calls OpsAgent.log_expense"""
    amount = task.payload.get("amount")
    description = task.payload.get("description")
    dept = task.payload.get("department")
    
    if amount is None or not description or not dept:
        return {"status": "failed", "error": "Missing amount, description, or department in payload."}
    
    result = await ops.log_expense(float(amount), description, dept)
    return result

async def handle_budget(task: TaskContext) -> dict:
    """Action: budget — calls OpsAgent.get_budget_status"""
    dept = task.payload.get("department")
    if not dept:
        return {"status": "failed", "error": "Missing department in payload."}
    
    result = await ops.get_budget_status(dept)
    return result
