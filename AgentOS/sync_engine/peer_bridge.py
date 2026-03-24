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

REGISTRY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "shared", "peer_registry.json"
)

# In-memory peer table
_peers: dict[str, dict] = {}
_call_hooks: list[Callable] = []


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
        "status": "online"
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


def heartbeat(agent_id: str) -> bool:
    if agent_id in _peers:
        _peers[agent_id]["last_seen"] = time.time()
        _peers[agent_id]["status"] = "online"
        _save_registry()
        return True
    return False


def get_peers() -> list[dict]:
    _prune_stale()
    return list(_peers.values())


def get_peer(agent_id: str) -> Optional[dict]:
    return _peers.get(agent_id)


def _prune_stale(timeout_s: int = 60):
    """Mark peers as offline if not seen in timeout_s seconds."""
    now = time.time()
    for peer in _peers.values():
        if now - peer.get("last_seen", 0) > timeout_s:
            peer["status"] = "offline"


def _save_registry():
    os.makedirs(os.path.dirname(REGISTRY_FILE), exist_ok=True)
    with open(REGISTRY_FILE, "w") as f:
        json.dump(_peers, f, indent=2)


def _load_registry():
    global _peers
    if os.path.exists(REGISTRY_FILE):
        with open(REGISTRY_FILE) as f:
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
        "X-Correlation-ID": trace_id
    }
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


async def probe_peer(agent_id: str) -> bool:
    """Check if a peer's MCP server is reachable."""
    result = await call_peer_tool(agent_id, "ping",
                                  {"agent_id": "bridge"}, "bridge")
    alive = result.get("ok", False)
    if agent_id in _peers:
        _peers[agent_id]["status"] = "online" if alive else "unreachable"
        _save_registry()
    return alive
