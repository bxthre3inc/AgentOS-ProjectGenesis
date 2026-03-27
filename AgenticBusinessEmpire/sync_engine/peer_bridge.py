"""
Zo & Antigravity 2-Way Workspace Sync — Optimized Architecture
Peer Bridge: symmetric MCP mesh where both agents are server AND client.

Each peer registers itself with a URL where it serves MCP tools.
The bridge routes cross-peer tool calls transparently.
"""
import asyncio
import json
import os
import time
from typing import Optional, Callable
import httpx
from . import actions_log as alog, core
from AgenticBusinessEmpire.core import config

# ── Registry ──────────────────────────────────────────────────────────────────

def register_peer(agent_id: str, mcp_server_url: str,
                  capabilities: list[str] = None, api_key: str = "") -> dict:
    """Register a peer's outward-facing MCP server URL."""
    peer = {
        "agent_id": agent_id,
        "mcp_server_url": mcp_server_url,
        "capabilities": capabilities or [],
        "api_key": api_key,
        "registered_at": time.time(),
        "last_seen": time.time(),
        "status": "online",
        "pressure": {} # Real-time health report
    }
    _peers[agent_id] = peer
    _save_registry()
    alog.record("peer_registered", agent_id, alog.CAT_SESSION,
                detail={"url": mcp_server_url, "capabilities": capabilities})
    return peer


def unregister_peer(agent_id: str) -> bool:
    if agent_id in _peers:
        del _peers[agent_id]
        _save_registry()
        alog.record("peer_unregistered", agent_id, alog.CAT_SESSION)
        return True
    return False


def heartbeat(agent_id: str, pressure_report: dict = None) -> bool:
    if agent_id in _peers:
        _peers[agent_id]["last_seen"] = time.time()
        _peers[agent_id]["status"] = "online"
        if pressure_report:
            _peers[agent_id]["pressure"] = pressure_report
        _save_registry()
        return True
    return False


def get_peers() -> list[dict]:
    _prune_stale()
    return list(_peers.values())


def get_healthiest_peer(exclude_agent: str = "", requirements: dict = None) -> Optional[str]:
    """Return the ID of the peer with the highest weighted compute score."""
    _prune_stale()
    candidates = []
    
    for aid, p in _peers.items():
        if aid == exclude_agent or p.get("status") != "online":
            continue
        
        pressure = p.get("pressure", {})
        profile = pressure.get("profile", "balanced")
        is_server = pressure.get("is_server", False)
        
        # We only delegate to nodes that are at least BALANCED (or better)
        # unless it's a server (servers can handle more)
        if profile in ["turbo", "performance", "balanced"] or is_server:
            # Weighted Score: (RAM_GB * 10) + CPU_Idle - Latency_penalty + Server_Bonus
            # This favors servers and high-resource nodes with low latency.
            ram_gb = pressure.get("ram_p", 0) / 10.0 # Approximation if real GB is missing
            cpu_idle = 100 - pressure.get("cpu_p", 100)
            latency_ms = p.get("latency_ms", 50)
            
            score = (ram_gb * 10) + cpu_idle - (latency_ms / 5.0)
            if is_server:
                score += 200 # Significant server priority
                
            candidates.append((score, aid))
            
    if not candidates:
        return None
        
    # Sort by score descending
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]

def is_mesh_saturated() -> bool:
    """Check if all nodes in the mesh are under pressure."""
    _prune_stale()
    if not _peers:
        return False
    
    rank = {"turbo": 4, "performance": 3, "balanced": 2, "low": 1, "economy": 0}
    for p in _peers.values():
        if p.get("status") == "online":
            profile = p.get("pressure", {}).get("profile", "balanced")
            if rank.get(profile, 0) >= 2: # At least one node is BALANCED or better
                return False
    return True


def get_peer(agent_id: str) -> Optional[dict]:
    return _peers.get(agent_id)

def get_master_peer() -> Optional[str]:
    """Elect the 'Primary Master' node based on health and uptime."""
    # We use the same 'healthiest' logic for now, but a master-specific 
    # selection can be refined here (e.g. favoring stable Server nodes).
    return get_healthiest_peer()

def is_master(agent_id: str) -> bool:
    """Check if the given agent_id is the currently elected master."""
    master = get_master_peer()
    return master == agent_id or (master is None and agent_id == "agenticbusinessempire")

def _prune_stale(timeout_s: int = 60):
    """Mark peers as offline if not seen in timeout_s seconds."""
    now = time.time()
    for peer in _peers.values():
        if now - peer.get("last_seen", 0) > timeout_s:
            peer["status"] = "offline"


def _save_registry():
    os.makedirs(os.path.dirname(config.PEER_REGISTRY_PATH), exist_ok=True)
    with open(config.PEER_REGISTRY_PATH, "w") as f:
        json.dump(_peers, f, indent=2)


def _load_registry():
    global _peers
    if os.path.exists(config.PEER_REGISTRY_PATH):
        with open(config.PEER_REGISTRY_PATH) as f:
            _peers = json.load(f)


_load_registry()


# ── Cross-peer tool call ───────────────────────────────────────────────────────

async def call_peer_tool(target_agent: str, tool_name: str,
                         arguments: dict, caller: str = "system",
                         correlation_id: Optional[str] = None) -> dict:
    """
    Call an MCP tool on a remote peer's server.
    Returns the parsed JSON result or an error dict.
    """
    import uuid
    trace_id = correlation_id or f"trace-{uuid.uuid4().hex[:8]}"

    peer = get_peer(target_agent)
    if not peer:
        return {"ok": False, "error": f"Peer '{target_agent}' not registered"}

    url = peer["mcp_server_url"]
    api_key = peer.get("api_key", "")

    headers = {
        "Content-Type": "application/json",
        "X-Correlation-ID": trace_id,
        "X-Timestamp": str(int(time.time())),
        "X-Nonce": f"nonce-{uuid.uuid4().hex[:8]}"
    }

    # Generate HMAC Signature
    if os.path.exists(config.MESH_KEY_PATH):
        import hmac
        import hashlib
        with open(config.MESH_KEY_PATH, 'r') as f:
            key = f.read().strip().encode()
        
        payload_str = f"{headers['X-Timestamp']}{headers['X-Nonce']}{json.dumps(arguments)}"
        signature = hmac.new(key, payload_str.encode(), hashlib.sha256).hexdigest()
        headers["X-Signature"] = signature

    if api_key:
        headers["X-API-Key"] = api_key

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments}
    }

    alog.record("cross_peer_call", caller, alog.CAT_COMMAND,
                target_agent=target_agent, trace_id=trace_id,
                detail={"tool": tool_name})

    # Visual Pulse for the dashboard
    await core.broadcast_event({"type": "peer_call", "agent": caller, "target_agent": target_agent})

    start_t = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            latency = (time.perf_counter() - start_t) * 1000
            data = resp.json()
            result = data.get("result", {})

            # Update peer latency stats
            if target_agent in _peers:
                _peers[target_agent]["latency_ms"] = round(latency, 2)
                _peers[target_agent]["last_seen"] = time.time()
                _save_registry()

            alog.record("cross_peer_result", caller, alog.CAT_COMMAND,
                        target_agent=target_agent, trace_id=trace_id,
                        latency_ms=latency,
                        detail={"tool": tool_name, "status": "ok"})
            return {"ok": True, "result": result}
    except httpx.RequestError as e:
        alog.record("cross_peer_error", caller, alog.CAT_COMMAND,
                    target_agent=target_agent, trace_id=trace_id,
                    status="error", error=str(e))
        if target_agent in _peers:
            _peers[target_agent]["status"] = "error"
            _save_registry()
        return {"ok": False, "error": f"Connection failed: {e}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def delegate_task(task_obj: dict, caller: str = "agent_id", requirements: dict = None) -> bool:
    """Find a healthy peer and offload the task to them."""
    target = get_healthiest_peer(exclude_agent=caller, requirements=requirements)
    if not target:
        logger.info("[Bridge] No healthy peers available for delegation.")
        return False
        
    logger.info("[Bridge] Delegating task %s to peer: %s", task_obj.get("task_id"), target)
    
    # We use assign_task tool on the peer, passing the full task structure
    result = await call_peer_tool(
        target, "assign_task", 
        {
            "task": task_obj.get("payload", {}).get("prompt") or task_obj.get("task_id"), 
            "priority": "high",
            "metadata": {
                "original_task_id": task_obj.get("task_id"),
                "tenant": task_obj.get("tenant"),
                "payload": task_obj.get("payload")
            }
        },
        caller=caller
    )
    
    return result.get("ok", False)


async def heartbeat_loop(agent_id: str):
    """Periodically announce presence and resource pressure to the mesh."""
    from AgenticBusinessEmpire.kernel import resource_monitor
    while True:
        try:
            pressure = resource_monitor.get_pressure_report()
            heartbeat(agent_id, pressure_report=pressure)
            
            # Master Election Awareness
            if is_master(agent_id):
                await core.broadcast_event({"type": "mesh_status", "msg": "NODE_IS_MASTER", "node": agent_id})
        except Exception as e:
            # logger.error("Heartbeat failed: %s", e)
            pass
        await asyncio.sleep(15) # 15s mesh heartbeat


async def probe_peer(agent_id: str) -> bool:
    """Check if a peer's MCP server is reachable."""
    result = await call_peer_tool(agent_id, "ping",
                                  {"agent_id": "bridge"}, "bridge")
    alive = result.get("ok", False)
    if agent_id in _peers:
        _peers[agent_id]["status"] = "online" if alive else "unreachable"
        _save_registry()
    return alive
