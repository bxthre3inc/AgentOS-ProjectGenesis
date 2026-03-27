"""
Zo & Antigravity 2-Way Workspace Sync — Optimized Architecture
AgenticBusinessEmpire MCP Client: Antigravity can call AgenticBusinessEmpire workforce tools.

Wraps the peer_bridge cross-peer call mechanism with human-readable
AgenticBusinessEmpire-specific tool names. The actual HTTP call goes to whatever
URL AgenticBusinessEmpire has registered in the peer registry.

If AgenticBusinessEmpire is not online, returns a graceful degradation response.
"""
import asyncio
from typing import Optional
from . import peer_bridge, actions_log as alog

AGENTIC_BUSINESS_EMPIRE_PEER_ID = "agenticbusinessempire"


# ── Public API ────────────────────────────────────────────────────────────────

async def invoke_agent(agent_name: str, task: str,
                       context: Optional[dict] = None,
                       caller: str = "antigravity") -> dict:
    """
    Ask an AgenticBusinessEmpire agent (e.g. "Taylor", "Alex") to perform a task.
    Example: invoke_agent("Taylor", "fix bug in auth.py", {"file": "auth.py"})
    """
    alog.record("invoke_agenticbusinessempire_agent", caller, alog.CAT_COMMAND,
                target_agent=AGENTIC_BUSINESS_EMPIRE_PEER_ID,
                detail={"agent": agent_name, "task": task[:120]})
    return await peer_bridge.call_peer_tool(
        AGENTIC_BUSINESS_EMPIRE_PEER_ID, "invoke_agent",
        {"agent_name": agent_name, "task": task, "context": context or {}},
        caller=caller
    )


async def assign_task(task: str, priority: str = "normal",
                      assign_to: Optional[str] = None,
                      caller: str = "antigravity") -> dict:
    """Submit a task to the AgenticBusinessEmpire workforce queue."""
    alog.record("assign_agenticbusinessempire_task", caller, alog.CAT_COMMAND,
                target_agent=AGENTIC_BUSINESS_EMPIRE_PEER_ID,
                detail={"task": task[:120], "priority": priority})
    return await peer_bridge.call_peer_tool(
        AGENTIC_BUSINESS_EMPIRE_PEER_ID, "assign_task",
        {"task": task, "priority": priority, "assign_to": assign_to},
        caller=caller
    )


async def get_agent_status(agent_name: Optional[str] = None,
                           caller: str = "antigravity") -> dict:
    """Get status of a specific agent or the entire workforce."""
    return await peer_bridge.call_peer_tool(
        AGENTIC_BUSINESS_EMPIRE_PEER_ID, "get_agent_status",
        {"agent_name": agent_name} if agent_name else {},
        caller=caller
    )


async def query_memory(query: str, namespace: Optional[str] = None,
                       caller: str = "antigravity") -> dict:
    """Query AgenticBusinessEmpire's shared memory/knowledge base."""
    alog.record("query_agenticbusinessempire_memory", caller, alog.CAT_COMMAND,
                target_agent=AGENTIC_BUSINESS_EMPIRE_PEER_ID,
                detail={"query": query[:120], "namespace": namespace})
    return await peer_bridge.call_peer_tool(
        AGENTIC_BUSINESS_EMPIRE_PEER_ID, "query_memory",
        {"query": query, "namespace": namespace},
        caller=caller
    )


async def get_war_room(caller: str = "antigravity") -> dict:
    """Get the current AgenticBusinessEmpire War Room state (active projects, blockers, etc.)."""
    return await peer_bridge.call_peer_tool(
        AGENTIC_BUSINESS_EMPIRE_PEER_ID, "get_war_room", {}, caller=caller
    )


async def get_ledger(caller: str = "antigravity") -> dict:
    """Retrieve the AgenticBusinessEmpire Bxthre3 Ledger (financials, metrics)."""
    return await peer_bridge.call_peer_tool(
        AGENTIC_BUSINESS_EMPIRE_PEER_ID, "get_ledger", {}, caller=caller
    )


async def push_code_to_agenticbusinessempire(file_path: str, content: str,
                                message: str = "",
                                caller: str = "antigravity") -> dict:
    """Push a code file from Antigravity into the AgenticBusinessEmpire codebase."""
    import base64
    alog.record("push_code_agenticbusinessempire", caller, alog.CAT_RESOURCE,
                target_agent=AGENTIC_BUSINESS_EMPIRE_PEER_ID,
                detail={"path": file_path, "bytes": len(content)})
    return await peer_bridge.call_peer_tool(
        AGENTIC_BUSINESS_EMPIRE_PEER_ID, "receive_code",
        {"path": file_path,
         "content_b64": base64.b64encode(content.encode()).decode(),
         "commit_message": message},
        caller=caller
    )


async def is_online(caller: str = "antigravity") -> bool:
    """Check if the AgenticBusinessEmpire peer is reachable."""
    return await peer_bridge.probe_peer(AGENTIC_BUSINESS_EMPIRE_PEER_ID)


# ── MCP Tool wrappers (for embedding in main MCP server) ──────────────────────

AGENTIC_BUSINESS_EMPIRE_TOOLS = [
    {
        "name": "agenticbusinessempire_invoke_agent",
        "description": "Invoke a named AgenticBusinessEmpire agent to perform a task (e.g. Taylor, Alex).",
        "params": ["agent_name", "task", "context?"]
    },
    {
        "name": "agenticbusinessempire_assign_task",
        "description": "Submit a task to the AgenticBusinessEmpire workforce queue.",
        "params": ["task", "priority?", "assign_to?"]
    },
    {
        "name": "agenticbusinessempire_get_status",
        "description": "Get the status of AgenticBusinessEmpire agents or the full workforce.",
        "params": ["agent_name?"]
    },
    {
        "name": "agenticbusinessempire_query_memory",
        "description": "Query the AgenticBusinessEmpire shared memory and knowledge base.",
        "params": ["query", "namespace?"]
    },
    {
        "name": "agenticbusinessempire_war_room",
        "description": "Get the current AgenticBusinessEmpire War Room state.",
        "params": []
    },
    {
        "name": "agenticbusinessempire_push_code",
        "description": "Push a code file from Antigravity into the AgenticBusinessEmpire codebase.",
        "params": ["file_path", "content", "message?"]
    },
]


async def dispatch_agenticbusinessempire_tool(name: str, arguments: dict,
                                 caller: str = "antigravity") -> dict:
    """Route an agenticbusinessempire_* tool call from the main MCP server."""
    dispatch = {
        "agenticbusinessempire_invoke_agent": lambda a: invoke_agent(
            a["agent_name"], a["task"], a.get("context"), caller),
        "agenticbusinessempire_assign_task": lambda a: assign_task(
            a["task"], a.get("priority", "normal"), a.get("assign_to"), caller),
        "agenticbusinessempire_get_status": lambda a: get_agent_status(a.get("agent_name"), caller),
        "agenticbusinessempire_query_memory": lambda a: query_memory(
            a["query"], a.get("namespace"), caller),
        "agenticbusinessempire_war_room": lambda a: get_war_room(caller),
        "agenticbusinessempire_push_code": lambda a: push_code_to_agenticbusinessempire(
            a["file_path"], a["content"], a.get("message", ""), caller),
    }
    fn = dispatch.get(name)
    if not fn:
        return {"ok": False, "error": f"Unknown AgenticBusinessEmpire tool: {name}"}
    return await fn(arguments)
