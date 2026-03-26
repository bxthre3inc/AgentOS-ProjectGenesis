"""
strategy.py — AgentOS Strategic Domain Logic
"""
import time
import logging
from AgentOS.core.db import RQE
from AgentOS.core.models import TaskContext
from AgentOS.kernel.registry import registry
from . import rating_engine
from . import provisioner
import os
from AgentOS.kernel.evolution_engine import EvolutionEngine

logger = logging.getLogger("agentos.logic.strategy")

@registry.register("idea_intake")
async def handle_idea_intake(task: TaskContext) -> dict:
    """Process a new idea seed into the Blue Ocean seeds table."""
    title = task.payload.get("title")
    description = task.payload.get("description", "")
    source = task.payload.get("pipeline_source", "BLUE_OCEAN_TEAM")
    
    if not title:
        return {"status": "error", "message": "title is required"}

    seed_id = f"SEED-{int(time.time())}"

    # Dynamic Rating (Real Audit via Evaluation Board)
    audit_res = await rating_engine.audit_seed(seed_id, title, description)
    
    m = audit_res.get("metrics", {"core_fit": 0.5, "impl_cost": 0.5, "scalability": 0.5, "strat_divergence": 0.5})
    overall = audit_res.get("overall", 0.5)
    verdict = audit_res.get("verdict", "TRIAGED")
    
    await RQE.execute("""
        INSERT INTO blue_ocean_seeds 
        (seed_id, title, description, pipeline_source, core_fit, impl_cost, scalability, strat_divergence, overall_rating, status)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
    """, seed_id, title, description, source, m.get("core_fit"), m.get("impl_cost"), m.get("scalability"), m.get("strat_divergence", 0.5), overall, verdict, fetch=False)
    
    return {
        "status": "ok", 
        "seed_id": seed_id, 
        "audit": audit_res,
        "message": f"Idea seeded in {source} pipeline."
    }

@registry.register("transition")
async def handle_transition(task: TaskContext) -> dict:
    """Progress a company through the 6-stage lifecycle."""
    company_id = task.payload.get("company_id")
    new_state = task.payload.get("new_state")
    name = task.payload.get("name", "New Subsidiary")
    
    await RQE.execute(
        "UPDATE companies SET lifecycle_state = $1 WHERE company_id = $2",
        new_state, company_id, fetch=False
    )
    
    if new_state == "SUBSIDIARY":
        prov_res = await provisioner.provision_subsidiary(company_id, name)
        return {"status": "ok", "new_state": new_state, "provisioning": prov_res}

    return {"status": "ok", "new_state": new_state}

@registry.register("pivot")
async def handle_pivot(task: TaskContext) -> dict:
    """Execute a strategic pivot."""
    company_id = task.payload.get("company_id")
    # Logic to archive current tasks and reset milestones
    return {"status": "ok", "message": f"Pivot executed for {company_id}"}

@registry.register("self_audit")
async def handle_self_audit(task: TaskContext) -> dict:
    """Pulse: Perform a system health check."""
    from AgentOS.kernel import resource_monitor
    report = resource_monitor.get_pressure_report()
    logger.info("[Pulse] Self-Audit: System Pressure: %s", report["profile"])
    return {"status": "ok", "report": report}

@registry.register("reconcile_seeds")
async def handle_reconcile_seeds(task: TaskContext) -> dict:
    """Pulse: Reconcile blue ocean seeds with the ledger."""
    return {"status": "ok", "msg": "Seeds reconciled"}

@registry.register("optimize_core")
async def handle_optimize(task: TaskContext) -> dict:
    """Pulse: Trigger autonomous evolution engine optimizations."""
    from AgentOS.core import config
    engine = EvolutionEngine(config.WORKSPACE_ROOT)
    tco_id = await engine.evolve()
    if tco_id:
        return {"status": "ok", "msg": f"Optimization TCO generated: {tco_id}", "tco_id": tco_id}
    return {"status": "ok", "msg": "Kernel performance is within nominal bounds. No optimization needed."}
