import logging
from AgentOS.core.db import RQE
from AgentOS.core.models import TaskContext
from AgentOS.kernel.registry import registry
from . import provisioner

logger = logging.getLogger("agentos.logic.corporate")

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
    
    # We use RQE which handles the Master Shard for workforce
    await RQE.execute("""
        INSERT INTO workforce (entity_id, tier, department, skills)
        VALUES ($1, $2, $3, $4)
    """, entity_id, tier, dept, json.dumps(skills), fetch=False)
    
    return {"status": "ok", "entity_id": entity_id}
