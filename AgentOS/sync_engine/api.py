"""
Zo & Antigravity 2-Way Workspace Sync
FastAPI HTTP + WebSocket layer — used by the dashboard
"""
import asyncio
import json
import os
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import secrets_vault, feature_flags, extensions_manager, command_bus, core, auth
from . import actions_log as alog

# AgentOS Kernel Bridge
from AgentOS.core.db import RQE as ao_db
from AgentOS.core.db import RQE as database

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASHBOARD_DIR = os.path.join(WORKSPACE_ROOT, "dashboard")

api = FastAPI(title="Zo & Antigravity Sync API", version="1.0.0")

# ── WebSocket broadcast pool ───────────────────────────────────────────────────
_connections: Set[WebSocket] = set()


async def broadcast(event: dict):
    dead = set()
    msg = json.dumps(event)
    for ws in _connections:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    _connections.difference_update(dead)


core.set_broadcaster(broadcast)


@api.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _connections.add(ws)
    try:
        while True:
            data = await ws.receive_text()
            # Clients can send pings
            if data.strip() == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        _connections.discard(ws)


# ── Static dashboard ───────────────────────────────────────────────────────────
api.mount("/static", StaticFiles(directory=DASHBOARD_DIR), name="static")


@api.get("/")
async def dashboard():
    return FileResponse(os.path.join(DASHBOARD_DIR, "index.html"))


# ── REST endpoints ─────────────────────────────────────────────────────────────

@api.get("/api/status")
async def status():
    snap = core.snapshot_workspace()
    return {"status": "ok", "workspace_files": len(snap), "connections": len(_connections)}


@api.get("/api/events")
async def get_events(limit: int = 50):
    return {"events": await database.get_recent_events(limit)}


# ── Actions Log ──
@api.get("/api/actions")
async def get_actions_log(
    limit: int = 100,
    agent: str = None,
    category: str = None,
    action: str = None,
):
    return {"entries": alog.search(agent=agent, category=category,
                                   action=action, limit=limit)}


@api.delete("/api/actions")
async def clear_actions_log():
    alog.clear()
    return {"ok": True}


@api.get("/api/agents")
async def get_agents():
    async with database.aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = database.aiosqlite.Row
        cur = await db.execute("SELECT * FROM agent_sessions")
        rows = await cur.fetchall()
        return {"agents": [dict(r) for r in rows]}


@api.get("/api/peers")
async def get_peers():
    from . import peer_bridge
    return {"peers": peer_bridge.get_peers()}


@api.post("/api/peers/register")
async def register_peer(body: dict):
    from . import peer_bridge
    peer = peer_bridge.register_peer(
        body["agent_id"], body["mcp_server_url"],
        body.get("capabilities", []), body.get("api_key", "")
    )
    return {"ok": True, "peer": peer}


@api.get("/api/session")
async def get_session(target: str = None):
    from . import session_sync
    return {"session": session_sync.get_session(target)}


@api.get("/api/workspace")
async def list_workspace():
    return {"files": core.snapshot_workspace()}


@api.get("/api/keys")
async def list_keys(user=Depends(auth.require_auth)):
    return {"keys": auth.list_keys()}


@api.post("/api/keys")
async def create_key(agent_id: str, user=Depends(auth.require_auth)):
    key = auth.generate_key(agent_id)
    return {"ok": True, "key": key}


# ── Features ──
@api.get("/api/features")
async def list_features():
    return {"features": feature_flags.list_flags()}


class FeatureToggle(BaseModel):
    flag: str
    enabled: bool
    agent_id: str = "system"
    global_scope: bool = False


@api.post("/api/features/toggle")
async def toggle_feature(body: FeatureToggle, request: Request, user=Depends(auth.require_auth)):
    trace_id = request.headers.get("X-Correlation-ID")
    target_agent = None if body.global_scope else body.agent_id
    result = feature_flags.set_flag(body.flag, body.enabled,
                                    agent_id=target_agent, issuer=body.agent_id)
    await broadcast({"type": "feature_updated", "flag": body.flag,
                     "agent": body.agent_id, "target_agent": target_agent or "all"})
    alog.record("toggle_feature", body.agent_id, alog.CAT_FEATURE,
                trace_id=trace_id,
                detail={"flag": body.flag, "enabled": body.enabled})
    return result


# ── Secrets ──
@api.get("/api/secrets")
async def list_secrets(agent_id: str = "shared"):
    return {"secrets": secrets_vault.list_secrets(agent_id)}


class SecretBody(BaseModel):
    name: str
    value: str
    agent_id: str = "shared"
    visibility: str = "shared"


@api.post("/api/secrets")
async def set_secret(body: SecretBody, request: Request, user=Depends(auth.require_auth)):
    trace_id = request.headers.get("X-Correlation-ID")
    ok = secrets_vault.set_secret(body.name, body.value, body.agent_id, body.visibility)
    await database.log_event("secret_set", body.agent_id, payload={"name": body.name})
    alog.record("set_secret", body.agent_id, alog.CAT_SECRET,
                trace_id=trace_id,
                detail={"name": body.name, "visibility": body.visibility, "source": "dashboard"})
    await broadcast({"type": "secret_updated", "name": body.name})
    return {"ok": ok}


@api.delete("/api/secrets/{name}")
async def delete_secret(name: str, user=Depends(auth.require_auth)):
    ok = secrets_vault.delete_secret(name)
    return {"ok": ok}


# ── Extensions ──
@api.get("/api/extensions")
async def list_extensions(agent_id: str = None):
    return {"extensions": extensions_manager.list_extensions(agent_id)}


class ExtToggle(BaseModel):
    extension_id: str
    enabled: bool


@api.post("/api/extensions/toggle")
async def toggle_extension(body: ExtToggle, user=Depends(auth.require_auth)):
    result = extensions_manager.toggle_extension(body.extension_id, body.enabled)
    if not result:
        raise HTTPException(status_code=404, detail="Extension not found")
    await broadcast({"type": "extension_changed", "id": body.extension_id,
                     "enabled": body.enabled})
    return result


# ── Commands ──
@api.get("/api/commands")
async def get_commands(limit: int = 50):
    return {"commands": await command_bus.get_command_history(limit)}


class CommandBody(BaseModel):
    issuer: str
    target: str
    command: str
    args: dict = {}


@api.post("/api/commands")
async def issue_command(body: CommandBody, request: Request, user=Depends(auth.require_auth)):
    trace_id = request.headers.get("X-Correlation-ID")
    cmd_id = await command_bus.issue_command(body.issuer, body.target,
                                             body.command, body.args)
    await broadcast({"type": "command_issued", "id": cmd_id,
                     "command": body.command, "agent": body.issuer, "target_agent": body.target})
    alog.record("issue_command", body.issuer, alog.CAT_COMMAND,
                target_agent=body.target, trace_id=trace_id,
                detail={"command": body.command})
    return {"ok": True, "command_id": cmd_id}


# ── Messages ──
@api.get("/api/messages/{agent_id}")
async def get_messages(agent_id: str, unread_only: bool = True):
    return {"messages": await command_bus.get_messages(agent_id, unread_only)}


class MessageBody(BaseModel):
    from_agent: str
    to_agent: str
    topic: str
    body: dict = {}


@api.post("/api/messages")
async def send_message(body: MessageBody, user=Depends(auth.require_auth)):
    await command_bus.post_message(body.from_agent, body.to_agent,
                                   body.topic, body.body)
    await broadcast({"type": "message_sent", "from": body.from_agent,
                     "to": body.to_agent, "topic": body.topic,
                     "agent": body.from_agent, "target_agent": body.to_agent})
    return {"ok": True}


# ── AgentOS Specific ──
@api.get("/api/agentos/workforce")
async def get_ao_workforce():
    # Fetch from AgentOS DB (shared or kernel-specific)
    return {"workforce": [
        {"name": "Ops Agent", "task": "Monitoring Mesh", "state": "active"},
        {"name": "Dev Agent", "task": "Idle - Kernel Stable", "state": "idle"},
        {"name": "Security Agent", "task": "Self-Audit Trace", "state": "active"}
    ]}

@api.get("/api/agentos/status")
async def get_ao_status():
    metrics = await ao_db.get_tenant_metrics("agentos_internal")
    return {
        "objective": "Recursive Self-Optimization",
        "progress": 90,
        "metrics": metrics
    }


# ── Startup ──
@api.on_event("startup")
async def startup():
    await database.init_db()
    loop = asyncio.get_event_loop()
    core.start_watcher(loop)
    
    # SHARDING: Start mesh heartbeat
    from . import peer_bridge
    asyncio.create_task(peer_bridge.heartbeat_loop("agentos"))
    
    alog.record("server_start", "system", alog.CAT_SYSTEM,
                detail={"mode": "dashboard", "port": 7880})


def run_dashboard():
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 7880))
    # Bind to 0.0.0.0 for cloud hosting compatibility
    uvicorn.run(api, host="0.0.0.0", port=port, log_level="error")
