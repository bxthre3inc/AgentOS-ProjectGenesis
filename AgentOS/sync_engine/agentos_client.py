"""
Zo & Antigravity 2-Way Workspace Sync — Optimized Architecture
AgentOS MCP Client: Antigravity can call AgentOS workforce tools.

Wraps the peer_bridge cross-peer call mechanism with human-readable
AgentOS-specific tool names. The actual HTTP call goes to whatever
URL AgentOS has registered in the peer registry.

If AgentOS is not online, returns a graceful degradation response.
"""
import asyncio
from typing import Optional
from . import peer_bridge, actions_log as alog

AGENTOS_PEER_ID = "agentos"


# ── Public API ────────────────────────────────────────────────────────────────

async def invoke_agent(agent_name: str, task: str,
                       context: Optional[dict] = None,
                       caller: str = "antigravity") -> dict:
    """
    Ask an AgentOS agent (e.g. "Taylor", "Alex") to perform a task.
    Example: invoke_agent("Taylor", "fix bug in auth.py", {"file": "auth.py"})
    """
    alog.record("invoke_agentos_agent", caller, alog.CAT_COMMAND,
                target_agent=AGENTOS_PEER_ID,
                detail={"agent": agent_name, "task": task[:120]})
    return await peer_bridge.call_peer_tool(
        AGENTOS_PEER_ID, "invoke_agent",
        {"agent_name": agent_name, "task": task, "context": context or {}},
        caller=caller
    )


async def assign_task(task: str, priority: str = "normal",
                      assign_to: Optional[str] = None,
                      caller: str = "antigravity") -> dict:
    """Submit a task to the AgentOS workforce queue."""
    alog.record("assign_agentos_task", caller, alog.CAT_COMMAND,
                target_agent=AGENTOS_PEER_ID,
                detail={"task": task[:120], "priority": priority})
    return await peer_bridge.call_peer_tool(
        AGENTOS_PEER_ID, "assign_task",
        {"task": task, "priority": priority, "assign_to": assign_to},
        caller=caller
    )


async def get_agent_status(agent_name: Optional[str] = None,
                           caller: str = "antigravity") -> dict:
    """Get status of a specific agent or the entire workforce."""
    return await peer_bridge.call_peer_tool(
        AGENTOS_PEER_ID, "get_agent_status",
        {"agent_name": agent_name} if agent_name else {},
        caller=caller
    )


async def query_memory(query: str, namespace: Optional[str] = None,
                       caller: str = "antigravity") -> dict:
    """Query AgentOS's shared memory/knowledge base."""
    alog.record("query_agentos_memory", caller, alog.CAT_COMMAND,
                target_agent=AGENTOS_PEER_ID,
                detail={"query": query[:120], "namespace": namespace})
    return await peer_bridge.call_peer_tool(
        AGENTOS_PEER_ID, "query_memory",
        {"query": query, "namespace": namespace},
        caller=caller
    )


async def get_war_room(caller: str = "antigravity") -> dict:
    """Get the current AgentOS War Room state (active projects, blockers, etc.)."""
    return await peer_bridge.call_peer_tool(
        AGENTOS_PEER_ID, "get_war_room", {}, caller=caller
    )


async def get_ledger(caller: str = "antigravity") -> dict:
    """Retrieve the AgentOS Bxthre3 Ledger (financials, metrics)."""
    return await peer_bridge.call_peer_tool(
        AGENTOS_PEER_ID, "get_ledger", {}, caller=caller
    )


async def push_code_to_agentos(file_path: str, content: str,
                                message: str = "",
                                caller: str = "antigravity") -> dict:
    """Push a code file from Antigravity into the AgentOS codebase."""
    import base64
    alog.record("push_code_agentos", caller, alog.CAT_RESOURCE,
                target_agent=AGENTOS_PEER_ID,
                detail={"path": file_path, "bytes": len(content)})
    return await peer_bridge.call_peer_tool(
        AGENTOS_PEER_ID, "receive_code",
        {"path": file_path,
         "content_b64": base64.b64encode(content.encode()).decode(),
         "commit_message": message},
        caller=caller
    )


async def is_online(caller: str = "antigravity") -> bool:
    """Check if the AgentOS peer is reachable."""
    return await peer_bridge.probe_peer(AGENTOS_PEER_ID)


# ── MCP Tool wrappers (for embedding in main MCP server) ──────────────────────

AGENTOS_TOOLS = [
    {
        "name": "agentos_invoke_agent",
        "description": "Invoke a named AgentOS agent to perform a task (e.g. Taylor, Alex).",
        "params": ["agent_name", "task", "context?"]
    },
    {
        "name": "agentos_assign_task",
        "description": "Submit a task to the AgentOS workforce queue.",
        "params": ["task", "priority?", "assign_to?"]
    },
    {
        "name": "agentos_get_status",
        "description": "Get the status of AgentOS agents or the full workforce.",
        "params": ["agent_name?"]
    },
    {
        "name": "agentos_query_memory",
        "description": "Query the AgentOS shared memory and knowledge base.",
        "params": ["query", "namespace?"]
    },
    {
        "name": "agentos_war_room",
        "description": "Get the current AgentOS War Room state.",
        "params": []
    },
    {
        "name": "agentos_push_code",
        "description": "Push a code file from Antigravity into the AgentOS codebase.",
        "params": ["file_path", "content", "message?"]
    },
]


async def dispatch_agentos_tool(name: str, arguments: dict,
                                 caller: str = "antigravity") -> dict:
    """Route an agentos_* tool call from the main MCP server."""
    dispatch = {
        "agentos_invoke_agent": lambda a: invoke_agent(
            a["agent_name"], a["task"], a.get("context"), caller),
        "agentos_assign_task": lambda a: assign_task(
            a["task"], a.get("priority", "normal"), a.get("assign_to"), caller),
        "agentos_get_status": lambda a: get_agent_status(a.get("agent_name"), caller),
        "agentos_query_memory": lambda a: query_memory(
            a["query"], a.get("namespace"), caller),
        "agentos_war_room": lambda a: get_war_room(caller),
        "agentos_push_code": lambda a: push_code_to_agentos(
            a["file_path"], a["content"], a.get("message", ""), caller),
    }
    fn = dispatch.get(name)
    if not fn:
        return {"ok": False, "error": f"Unknown AgentOS tool: {name}"}
    return await fn(arguments)
