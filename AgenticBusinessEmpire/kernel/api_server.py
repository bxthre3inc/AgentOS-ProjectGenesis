from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import os
import json
import asyncio
from pathlib import Path
import sys

# Bootstrap paths
_KERNEL_DIR = Path(__file__).parent
_AGENTIC_BUSINESS_EMPIRE_DIR = _KERNEL_DIR.parent
_MANIFEST_PATH = _AGENTIC_BUSINESS_EMPIRE_DIR.parent / "system_manifest.json"

sys.path.insert(0, str(_KERNEL_DIR))
sys.path.insert(0, str(_AGENTIC_BUSINESS_EMPIRE_DIR))

import db
from task_context import TaskContext
from voice_service import voice_service

app = FastAPI(title="AgenticBusinessEmpire Kernel API", version="1.0.0")

# --- Models ---
class SystemStatus(BaseModel):
    system: str
    version: str
    manifest_loaded: bool
    db_status: str

class TenantMetric(BaseModel):
    id: str
    codename: str
    total_tasks: int
    pending: int
    completed: int
    readiness: int

# --- Lifecycle ---
@app.on_event("startup")
async def startup_event():
    await db.init_pool()
    # Note: migrate() is usually called by kernel_main, but we can do it here too if needed.
    # await db.migrate()

@app.on_event("shutdown")
async def shutdown_event():
    await db.close_pool()

# --- Endpoints ---

@app.get("/status", response_model=SystemStatus)
async def get_status():
    manifest = {}
    if _MANIFEST_PATH.exists():
        manifest = json.loads(_MANIFEST_PATH.read_text())
    
    return {
        "system": manifest.get("system", "AgenticBusinessEmpire"),
        "version": manifest.get("manifest_version", "1.0.0"),
        "manifest_loaded": bool(manifest),
        "db_status": "connected" if db._PG_AVAILABLE and db._pool else "stub/disconnected"
    }

@app.get("/tenants", response_model=List[dict])
async def get_tenants():
    if not _MANIFEST_PATH.exists():
        raise HTTPException(status_code=404, detail="Manifest not found")
    
    manifest = json.loads(_MANIFEST_PATH.read_text())
    tenants = manifest.get("tenants", {})
    
    results = []
    for t_id, t_info in tenants.items():
        metrics = await db.get_tenant_metrics(t_id)
        results.append({
            "id": t_id,
            "codename": t_info.get("codename"),
            "role": t_info.get("role"),
            "priority": t_info.get("priority"),
            "metrics": metrics or {"total_tasks": 0, "pending": 0, "completed": 0}
        })
    return results

@app.get("/tasks/pending", response_model=List[dict])
async def get_pending_tasks(tenant: Optional[str] = None):
    # This fetches from the DB if available, otherwise would need to scan filesystem
    # For now, let's assume DB is primary source of truth if connected.
    if tenant:
        return await db.get_tasks(tenant, status="pending")
    
    # Generic fetch - we might need a db helper for "all pending"
    sql = "SELECT * FROM tasks WHERE status = 'pending' ORDER BY priority, created_at"
    return await db.execute(sql)

@app.post("/tasks/submit")
async def submit_task(task: dict):
    # In a real scenario, we'd validate against TaskContext
    try:
        await db.upsert_task(task)
        return {"status": "accepted", "task_id": task.get("task_id")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Voice & IVR Routes ---

@app.all("/ivr/callback")
async def ivr_callback(msg: str = "Updating AgenticBusinessEmpire status."):
    """SignalWire IVR Callback: Responses in LAML (XML)."""
    return {
        "Response": {
            "Say": msg,
            "Pause": {"length": 1},
            "Hangup": {}
        }
    }

@app.post("/voice/vocalize")
async def api_vocalize(payload: dict):
    """API endpoint for live agent vocalization."""
    text = payload.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="Text required")
    return await voice_service.vocalize(text)

@app.post("/voice/listen")
async def api_listen(audio_file: bytes):
    """API endpoint for live speech-to-text."""
    return await voice_service.listen(audio_file)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
