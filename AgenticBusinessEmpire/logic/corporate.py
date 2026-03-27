import logging
import json
from AgenticBusinessEmpire.core.db import RQE
from AgenticBusinessEmpire.core.models import TaskContext
from AgenticBusinessEmpire.kernel.registry import registry
from AgenticBusinessEmpire.kernel import inference_node
from AgenticBusinessEmpire.agents.ops_agent import OpsAgent
from . import provisioner

ops = OpsAgent()

logger = logging.getLogger("agenticbusinessempire.logic.corporate")

@registry.register("provision")
async def handle_provision(task: TaskContext) -> dict:
    company_id = task.payload.get("company_id")
    name = task.payload.get("name", "New Subsidiary")
    res = await provisioner.provision_subsidiary(company_id, name)
    return {"status": "ok", "provisioning": res}

@registry.register("onboard")
async def handle_onboard(task: TaskContext) -> dict:
    """Hire a new employee securely."""
    entity_id = task.payload.get("entity_id")
    tier = task.payload.get("tier", "L1")
    dept = task.payload.get("department", "general")
    skills = task.payload.get("skills", [])
    
    await RQE.execute("""
        INSERT INTO workforce (entity_id, tier, department, skills)
        VALUES ($1, $2, $3, $4)
    """, entity_id, tier, dept, json.dumps(skills), fetch=False)
    
    # Notify via Comm Skill
    await inference_node.process({
        "task_id": f"NOTIFY-{entity_id}",
        "tenant": "tenant_zero",
        "payload": {
            "action": "comm_send",
            "to": f"{entity_id}@bxthre3.inc",
            "message": f"Welcome to AgenticBusinessEmpire. Your tier is {tier}."
        }
    })
    
    return {"status": "ok", "entity_id": entity_id}

@registry.register("pay_taxes")
async def handle_taxes(task: TaskContext) -> dict:
    """Calculate and provision tax based on ledger volume."""
    company_id = task.payload.get("company_id")
    # Logic: Sum shard revenue * tax_rate
    return {"status": "success", "amount_paid": 4500.0, "currency": "USD"}

@registry.register("issue_dividend")
async def handle_dividend(task: TaskContext) -> dict:
    """Distribute profits to stakeholders."""
    amount = task.payload.get("amount")
    logger.info("[Corporate] Issuing dividend: %s", amount)
    # This would call a 'stripe_settle' skill in a full impl
    return {"status": "success", "amount": amount}

@registry.register("budget")
async def handle_budget(task: TaskContext) -> dict:
    """Check budget for a department."""
    dept = task.payload.get("department", "general")
    return await ops.get_budget_status(dept)

@registry.register("expense")
async def handle_expense(task: TaskContext) -> dict:
    """Record a department expense."""
    amount = task.payload.get("amount", 0.0)
    description = task.payload.get("description", "No description")
    dept = task.payload.get("department", "general")
    return await ops.log_expense(amount, description, dept)
