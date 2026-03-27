"""
Zo & Antigravity 2-Way Workspace Sync
MCP Server — exposes all sync tools to both Zo.Computer and Antigravity
"""
import asyncio
import base64
import json
import os
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool, TextContent, Resource,
    ReadResourceResult, ListResourcesResult,
    CallToolResult, ListToolsResult
)

from . import secrets_vault, feature_flags, extensions_manager, command_bus, core
from . import actions_log as alog
from . import peer_bridge, session_sync, agenticbusinessempire_client
from .antigravity_server import ag_server as _ag, call_tool as _ag_call_tool, list_tools as _ag_list_tools

from AgenticBusinessEmpire.core import config
from AgenticBusinessEmpire.core.db import RQE

app = Server("zo-antigravity-sync")


# ── Tool definitions ───────────────────────────────────────────────────────────

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(name="ping",
             description="Check if the sync server is alive and get workspace status.",
             inputSchema={"type": "object", "properties": {
                 "agent_id": {"type": "string", "description": "Your agent ID (zo | antigravity)"}
             }, "required": ["agent_id"]}),

        Tool(name="sync_resource",
             description="Push a file resource into the shared workspace.",
             inputSchema={"type": "object", "properties": {
                 "agent_id": {"type": "string"},
                 "dest_path": {"type": "string", "description": "Relative path under shared/resources/"},
                 "content_b64": {"type": "string", "description": "Base64-encoded file content"},
                 "overwrite": {"type": "boolean", "default": True}
             }, "required": ["agent_id", "dest_path", "content_b64"]}),

        Tool(name="read_resource",
             description="Read a file from the shared workspace.",
             inputSchema={"type": "object", "properties": {
                 "agent_id": {"type": "string"},
                 "path": {"type": "string", "description": "Relative path in workspace"}
             }, "required": ["agent_id", "path"]}),

        Tool(name="delete_resource",
             description="Delete a shared resource.",
             inputSchema={"type": "object", "properties": {
                 "agent_id": {"type": "string"},
                 "path": {"type": "string"}
             }, "required": ["agent_id", "path"]}),

        Tool(name="list_workspace",
             description="List all files in the shared workspace with checksums.",
             inputSchema={"type": "object", "properties": {
                 "agent_id": {"type": "string"}
             }, "required": ["agent_id"]}),

        Tool(name="set_secret",
             description="Store an encrypted secret in the vault.",
             inputSchema={"type": "object", "properties": {
                 "agent_id": {"type": "string"},
                 "name": {"type": "string"},
                 "value": {"type": "string"},
                 "visibility": {"type": "string", "enum": ["shared", "zo", "antigravity"],
                                "default": "shared"}
             }, "required": ["agent_id", "name", "value"]}),

        Tool(name="get_secret",
             description="Retrieve a secret from the vault (respects visibility).",
             inputSchema={"type": "object", "properties": {
                 "agent_id": {"type": "string"},
                 "name": {"type": "string"}
             }, "required": ["agent_id", "name"]}),

        Tool(name="list_secrets",
             description="List available secrets for your agent.",
             inputSchema={"type": "object", "properties": {
                 "agent_id": {"type": "string"}
             }, "required": ["agent_id"]}),

        Tool(name="toggle_feature",
             description="Enable or disable a feature flag (globally or for your agent).",
             inputSchema={"type": "object", "properties": {
                 "agent_id": {"type": "string"},
                 "flag": {"type": "string"},
                 "enabled": {"type": "boolean"},
                 "global": {"type": "boolean", "default": False,
                            "description": "If true, applies globally (not just for your agent)"}
             }, "required": ["agent_id", "flag", "enabled"]}),

        Tool(name="list_features",
             description="List all feature flags and their current state for your agent.",
             inputSchema={"type": "object", "properties": {
                 "agent_id": {"type": "string"}
             }, "required": ["agent_id"]}),

        Tool(name="issue_command",
             description="Send a control command to the other agent.",
             inputSchema={"type": "object", "properties": {
                 "agent_id": {"type": "string", "description": "Issuing agent"},
                 "target": {"type": "string", "description": "Target agent (zo | antigravity)"},
                 "command": {"type": "string",
                             "description": "One of: ping, sync_now, push_resource, pull_resource, toggle_feature, load_extension, unload_extension, send_message, set_secret, shell, restart_sync"},
                 "args": {"type": "object", "default": {}}
             }, "required": ["agent_id", "target", "command"]}),

        Tool(name="poll_commands",
             description="Fetch and execute any commands queued for your agent.",
             inputSchema={"type": "object", "properties": {
                 "agent_id": {"type": "string"}
             }, "required": ["agent_id"]}),

        Tool(name="send_message",
             description="Post a message to the other agent's inbox.",
             inputSchema={"type": "object", "properties": {
                 "agent_id": {"type": "string"},
                 "to": {"type": "string"},
                 "topic": {"type": "string"},
                 "body": {}
             }, "required": ["agent_id", "to", "topic", "body"]}),

        Tool(name="get_messages",
             description="Read messages in your inbox.",
             inputSchema={"type": "object", "properties": {
                 "agent_id": {"type": "string"},
                 "unread_only": {"type": "boolean", "default": True}
             }, "required": ["agent_id"]}),

        Tool(name="list_extensions",
             description="List available extensions for your agent.",
             inputSchema={"type": "object", "properties": {
                 "agent_id": {"type": "string"}
             }, "required": ["agent_id"]}),

        Tool(name="toggle_extension",
             description="Enable or disable an extension.",
             inputSchema={"type": "object", "properties": {
                 "agent_id": {"type": "string"},
                 "extension_id": {"type": "string"},
                 "enabled": {"type": "boolean"}
             }, "required": ["agent_id", "extension_id", "enabled"]}),

        Tool(name="register_extension",
             description="Register a custom extension in the workspace.",
             inputSchema={"type": "object", "properties": {
                 "agent_id": {"type": "string"},
                 "extension": {"type": "object",
                               "description": "Extension manifest with id, name, version, description, capabilities"}
             }, "required": ["agent_id", "extension"]}),

        Tool(name="get_events",
             description="Retrieve recent sync events from the event log.",
             inputSchema={"type": "object", "properties": {
                 "agent_id": {"type": "string"},
                 "limit": {"type": "integer", "default": 50}
             }, "required": ["agent_id"]}),

        Tool(name="get_actions_log",
             description="Read the shared actions log — every action ever taken by either agent.",
             inputSchema={"type": "object", "properties": {
                 "agent_id": {"type": "string"},
                 "limit": {"type": "integer", "default": 100},
                 "filter_agent": {"type": "string", "description": "Filter by agent id"},
                 "filter_category": {"type": "string", "description": "Filter by category"},
                 "filter_action": {"type": "string", "description": "Filter by action name"}
             }, "required": ["agent_id"]}),

        # ── Peer Mesh (3-way: Zo + Antigravity + AgenticBusinessEmpire) ──
        Tool(name="register_peer",
             description="Register this agent's outward-facing MCP server URL so other peers can call it. Required for full-mesh operation.",
             inputSchema={"type": "object", "properties": {
                 "agent_id": {"type": "string"},
                 "mcp_server_url": {"type": "string", "description": "URL peers will call (e.g. http://host:port/mcp)"},
                 "capabilities": {"type": "array", "items": {"type": "string"}},
                 "api_key": {"type": "string", "description": "Optional API key peers must include"}
             }, "required": ["agent_id", "mcp_server_url"]}),

        Tool(name="get_peers",
             description="List all registered peers in the 3-way mesh (Zo, Antigravity, AgenticBusinessEmpire) and their status.",
             inputSchema={"type": "object", "properties": {
                 "agent_id": {"type": "string"}
             }, "required": ["agent_id"]}),

        Tool(name="get_session",
             description="Get the current IDE session context for any agent (open files, cursor, debugger, terminals).",
             inputSchema={"type": "object", "properties": {
                 "agent_id": {"type": "string", "description": "Requesting agent"},
                 "target_agent": {"type": "string", "description": "Agent whose session to read (zo | antigravity | agenticbusinessempire | all)"}
             }, "required": ["agent_id"]}),

        Tool(name="call_peer_tool",
             description="Call any MCP tool on a remote peer agent directly (requires peer to be registered).",
             inputSchema={"type": "object", "properties": {
                 "agent_id": {"type": "string"},
                 "target_agent": {"type": "string", "description": "zo | antigravity | agenticbusinessempire"},
                 "tool_name": {"type": "string"},
                 "arguments": {"type": "object", "default": {}}
             }, "required": ["agent_id", "target_agent", "tool_name"]}),

        # ── AgenticBusinessEmpire workforce tools (proxied via peer bridge) ──
        Tool(name="agenticbusinessempire_invoke_agent",
             description="Invoke a named AgenticBusinessEmpire workforce agent (e.g. Taylor, Alex) to perform a task.",
             inputSchema={"type": "object", "properties": {
                 "agent_id": {"type": "string"},
                 "agent_name": {"type": "string", "description": "AgenticBusinessEmpire agent name"},
                 "task": {"type": "string"},
                 "context": {"type": "object", "default": {}}
             }, "required": ["agent_id", "agent_name", "task"]}),

        Tool(name="agenticbusinessempire_assign_task",
             description="Submit a task to the AgenticBusinessEmpire workforce queue.",
             inputSchema={"type": "object", "properties": {
                 "agent_id": {"type": "string"},
                 "task": {"type": "string"},
                 "priority": {"type": "string", "enum": ["low", "normal", "high", "urgent"], "default": "normal"},
                 "assign_to": {"type": "string"}
             }, "required": ["agent_id", "task"]}),

        Tool(name="agenticbusinessempire_query_memory",
             description="Query the AgenticBusinessEmpire shared memory and knowledge base.",
             inputSchema={"type": "object", "properties": {
                 "agent_id": {"type": "string"},
                 "query": {"type": "string"},
                 "namespace": {"type": "string"}
             }, "required": ["agent_id", "query"]}),

        Tool(name="agenticbusinessempire_war_room",
             description="Get the current AgenticBusinessEmpire War Room state (active projects, blockers, metrics).",
             inputSchema={"type": "object", "properties": {
                 "agent_id": {"type": "string"}
             }, "required": ["agent_id"]}),

        # ── Antigravity IDE tools (proxied via ag_server) ──
        Tool(name="ide_open_file",
             description="Open a file in Antigravity IDE. AgenticBusinessEmpire and Zo can trigger this.",
             inputSchema={"type": "object", "properties": {
                 "agent_id": {"type": "string"},
                 "path": {"type": "string"}
             }, "required": ["agent_id", "path"]}),

        Tool(name="ide_edit_file",
             description="Apply an edit to a file via Antigravity IDE.",
             inputSchema={"type": "object", "properties": {
                 "agent_id": {"type": "string"},
                 "path": {"type": "string"},
                 "content": {"type": "string"},
                 "start_line": {"type": "integer"},
                 "end_line": {"type": "integer"}
             }, "required": ["agent_id", "path", "content"]}),

        Tool(name="ide_run_terminal",
             description="Run a shell command in Antigravity IDE's terminal.",
             inputSchema={"type": "object", "properties": {
                 "agent_id": {"type": "string"},
                 "command": {"type": "string"},
                 "cwd": {"type": "string"},
                 "timeout": {"type": "integer", "default": 30}
             }, "required": ["agent_id", "command"]}),

        Tool(name="ide_get_diagnostics",
             description="Get linting errors and warnings from Antigravity IDE.",
             inputSchema={"type": "object", "properties": {
                 "agent_id": {"type": "string"},
                 "file": {"type": "string"}
             }, "required": ["agent_id"]}),
    ]


# ── Tool handlers ──────────────────────────────────────────────────────────────

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    agent_id = arguments.get("agent_id", "unknown")
    trace_id = arguments.get("correlation_id")

    # Heartbeat + session
    await RQE.update_agent_session(agent_id, "online")
    # Log every tool invocation with performance tracking and trace context
    alog.record(action=name, agent=agent_id, category=_tool_category(name),
                trace_id=trace_id,
                detail={k: v for k, v in arguments.items() if k not in ("content_b64", "value", "correlation_id")})

    def ok(data: Any) -> list[TextContent]:
        return [TextContent(type="text", text=json.dumps({"ok": True, **data}
                                                         if isinstance(data, dict) else {"ok": True, "result": data}))]

    def err(msg: str) -> list[TextContent]:
        return [TextContent(type="text", text=json.dumps({"ok": False, "error": msg}))]

    # ── ping ──
    if name == "ping":
        snap = core.snapshot_workspace()
        alog.record("ping", agent_id, alog.CAT_SESSION, detail={"files": len(snap)})
        return ok({"status": "online", "workspace_files": len(snap),
                   "agent": agent_id, "server": "zo-antigravity-sync v1"})

    # ── resource ops ──
    elif name == "sync_resource":
        try:
            raw = base64.b64decode(arguments["content_b64"])
            rel = os.path.join("shared", "resources", arguments["dest_path"])
            result = core.write_resource(rel, raw, overwrite=arguments.get("overwrite", True))
            await RQE.log_event("resource_push", agent_id, path=rel, payload={"size": len(raw)})
            alog.record("sync_resource", agent_id, alog.CAT_RESOURCE, path=rel,
                        detail={"size": len(raw), "overwrite": arguments.get("overwrite", True)})
            return ok(result)
        except Exception as e:
            alog.record("sync_resource", agent_id, alog.CAT_RESOURCE, status="error", error=str(e))
            return err(str(e))

    elif name == "read_resource":
        raw = core.read_resource(arguments["path"])
        if raw is None:
            alog.record("read_resource", agent_id, alog.CAT_RESOURCE,
                        path=arguments["path"], status="not_found")
            return err("File not found")
        alog.record("read_resource", agent_id, alog.CAT_RESOURCE,
                    path=arguments["path"], detail={"size": len(raw)})
        return ok({"path": arguments["path"],
                   "content_b64": base64.b64encode(raw).decode(),
                   "size": len(raw)})

    elif name == "delete_resource":
        deleted = core.delete_resource(arguments["path"])
        await RQE.log_event("resource_delete", agent_id, path=arguments["path"])
        alog.record("delete_resource", agent_id, alog.CAT_RESOURCE,
                    path=arguments["path"], detail={"deleted": deleted})
        return ok({"deleted": deleted})

    elif name == "list_workspace":
        snap = core.snapshot_workspace()
        return ok({"files": snap, "count": len(snap)})

    # ── secrets ──
    elif name == "set_secret":
        secrets_vault.set_secret(arguments["name"], arguments["value"],
                                 owner=agent_id,
                                 visibility=arguments.get("visibility", "shared"))
        await RQE.log_event("secret_set", agent_id, payload={"name": arguments["name"]})
        alog.record("set_secret", agent_id, alog.CAT_SECRET,
                    detail={"name": arguments["name"],
                            "visibility": arguments.get("visibility", "shared")})
        return ok({"stored": arguments["name"]})

    elif name == "get_secret":
        val = secrets_vault.get_secret(arguments["name"], agent_id)
        if val is None:
            alog.record("get_secret", agent_id, alog.CAT_SECRET,
                        detail={"name": arguments["name"]}, status="denied")
            return err("Secret not found or not authorized")
        alog.record("get_secret", agent_id, alog.CAT_SECRET,
                    detail={"name": arguments["name"]})
        return ok({"name": arguments["name"], "value": val})

    elif name == "list_secrets":
        alog.record("list_secrets", agent_id, alog.CAT_SECRET)
        return ok({"secrets": secrets_vault.list_secrets(agent_id)})

    # ── features ──
    elif name == "toggle_feature":
        target_agent = None if arguments.get("global") else agent_id
        result = feature_flags.set_flag(arguments["flag"], arguments["enabled"],
                                        agent_id=target_agent, issuer=agent_id)
        await RQE.log_event("feature_toggle", agent_id,
                                 payload={"flag": arguments["flag"],
                                          "enabled": arguments["enabled"]})
        alog.record("toggle_feature", agent_id, alog.CAT_FEATURE,
                    detail={"flag": arguments["flag"], "enabled": arguments["enabled"],
                            "global": arguments.get("global", False)})
        return ok({"flag": arguments["flag"], **result})

    elif name == "list_features":
        alog.record("list_features", agent_id, alog.CAT_FEATURE)
        return ok({"features": feature_flags.list_flags(agent_id)})

    # ── commands ──
    elif name == "issue_command":
        cmd_id = await command_bus.issue_command(
            agent_id, arguments["target"],
            arguments["command"], arguments.get("args", {}))
        await RQE.log_event("command_issued", agent_id, target=arguments["target"],
                                 payload={"command": arguments["command"], "cmd_id": cmd_id})
        alog.record("issue_command", agent_id, alog.CAT_COMMAND,
                    target_agent=arguments["target"],
                    detail={"command": arguments["command"], "cmd_id": cmd_id,
                            "args": arguments.get("args", {})})
        return ok({"command_id": cmd_id, "status": "queued"})

    elif name == "poll_commands":
        results = await command_bus.poll_commands(agent_id)
        alog.record("poll_commands", agent_id, alog.CAT_COMMAND,
                    detail={"executed_count": len(results)})
        return ok({"executed": results, "count": len(results)})

    # ── messages ──
    elif name == "send_message":
        await command_bus.post_message(agent_id, arguments["to"],
                                       arguments["topic"], arguments["body"])
        alog.record("send_message", agent_id, alog.CAT_MESSAGE,
                    target_agent=arguments["to"],
                    detail={"topic": arguments["topic"]})
        return ok({"sent": True})

    elif name == "get_messages":
        msgs = await command_bus.get_messages(agent_id,
                                              arguments.get("unread_only", True))
        alog.record("get_messages", agent_id, alog.CAT_MESSAGE,
                    detail={"unread_only": arguments.get("unread_only", True),
                            "count": len(msgs)})
        return ok({"messages": msgs, "count": len(msgs)})

    # ── extensions ──
    elif name == "list_extensions":
        alog.record("list_extensions", agent_id, alog.CAT_EXTENSION)
        return ok({"extensions": extensions_manager.list_extensions(agent_id)})

    elif name == "toggle_extension":
        result = extensions_manager.toggle_extension(
            arguments["extension_id"], arguments["enabled"])
        if not result:
            return err("Extension not found")
        await RQE.log_event("extension_toggle", agent_id,
                                 payload={"id": arguments["extension_id"],
                                          "enabled": arguments["enabled"]})
        alog.record("toggle_extension", agent_id, alog.CAT_EXTENSION,
                    detail={"id": arguments["extension_id"],
                            "enabled": arguments["enabled"]})
        return ok(result)

    elif name == "register_extension":
        result = extensions_manager.register_extension(arguments["extension"])
        alog.record("register_extension", agent_id, alog.CAT_EXTENSION,
                    detail={"id": arguments["extension"].get("id"),
                            "name": arguments["extension"].get("name")})
        return ok(result)

    elif name == "get_events":
        events = await RQE.get_recent_events(arguments.get("limit", 50))
        return ok({"events": events})

    elif name == "get_actions_log":
        entries = alog.search(
            agent=arguments.get("filter_agent"),
            category=arguments.get("filter_category"),
            action=arguments.get("filter_action"),
            limit=arguments.get("limit", 100)
        )
        return ok({"entries": entries, "count": len(entries),
                   "log_path": "shared/actions.log"})

    # ── Peer Mesh ──
    elif name == "register_peer":
        peer = peer_bridge.register_peer(
            agent_id,
            arguments["mcp_server_url"],
            arguments.get("capabilities", []),
            arguments.get("api_key", "")
        )
        await RQE.update_agent_session(agent_id, "online")
        alog.record("register_peer", agent_id, alog.CAT_SESSION,
                    detail={"url": arguments["mcp_server_url"]})
        return ok({"registered": peer})

    elif name == "get_peers":
        peers = peer_bridge.get_peers()
        return ok({"peers": peers, "count": len(peers)})

    elif name == "get_session":
        target = arguments.get("target_agent", "all")
        sess = session_sync.get_session(None if target == "all" else target)
        return ok({"session": sess, "target": target})

    elif name == "call_peer_tool":
        result = await peer_bridge.call_peer_tool(
            arguments["target_agent"],
            arguments["tool_name"],
            arguments.get("arguments", {}),
            caller=agent_id
        )
        return ok(result)

    # ── AgenticBusinessEmpire workforce (proxied via peer bridge) ──
    elif name in ("agenticbusinessempire_invoke_agent", "agenticbusinessempire_assign_task",
                  "agenticbusinessempire_query_memory", "agenticbusinessempire_war_room"):
        result = await agenticbusinessempire_client.dispatch_agenticbusinessempire_tool(name, arguments, caller=agent_id)
        return ok(result)

    # ── Antigravity IDE tools (called by AgenticBusinessEmpire / Zo) ──
    elif name in ("ide_open_file", "ide_edit_file", "ide_run_terminal", "ide_get_diagnostics"):
        # Remap ide_* → antigravity_server tool name
        ide_name = name.replace("ide_", "")
        mapped_args = {k: v for k, v in arguments.items() if k != "agent_id"}
        mapped_args["caller"] = agent_id
        # If Antigravity IDE peer is registered, proxy to it; else run locally
        if peer_bridge.get_peer("antigravity"):
            result = await peer_bridge.call_peer_tool(
                "antigravity", ide_name, mapped_args, caller=agent_id)
            return ok(result)
        else:
            # Fall back to local execution
            from .antigravity_server import call_tool as ag_tool
            return await ag_tool(ide_name, mapped_args)

    alog.record(f"unknown_tool:{name}", agent_id, alog.CAT_SYSTEM, status="error")
    return err(f"Unknown tool: {name}")


# ── Resources ──────────────────────────────────────────────────────────────────

@app.list_resources()
async def list_resources() -> list[Resource]:
    snap = core.snapshot_workspace()
    return [
        Resource(
            uri=f"file://workspace/{path}",
            name=os.path.basename(path),
            description=f"Shared workspace file ({info['size']} bytes)",
            mimeType="application/octet-stream"
        )
        for path, info in snap.items()
    ]


@app.read_resource()
async def read_resource_handler(uri: str) -> str:
    rel = uri.replace("file://workspace/", "")
    raw = core.read_resource(rel)
    if raw is None:
        raise FileNotFoundError(f"Resource not found: {uri}")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return base64.b64encode(raw).decode()


# ── Helper: map tool name → category ─────────────────────────────────────────
def _tool_category(tool: str) -> str:
    cats = {
        "ping": alog.CAT_SESSION, "list_workspace": alog.CAT_RESOURCE,
        "sync_resource": alog.CAT_RESOURCE, "read_resource": alog.CAT_RESOURCE,
        "delete_resource": alog.CAT_RESOURCE,
        "set_secret": alog.CAT_SECRET, "get_secret": alog.CAT_SECRET,
        "list_secrets": alog.CAT_SECRET,
        "toggle_feature": alog.CAT_FEATURE, "list_features": alog.CAT_FEATURE,
        "issue_command": alog.CAT_COMMAND, "poll_commands": alog.CAT_COMMAND,
        "send_message": alog.CAT_MESSAGE, "get_messages": alog.CAT_MESSAGE,
        "list_extensions": alog.CAT_EXTENSION, "toggle_extension": alog.CAT_EXTENSION,
        "register_extension": alog.CAT_EXTENSION,
        "get_events": alog.CAT_SYSTEM, "get_actions_log": alog.CAT_SYSTEM,
    }
    return cats.get(tool, alog.CAT_SYSTEM)


# ── Entry point ────────────────────────────────────────────────────────────────

async def run_mcp():
    await RQE.init_db()
    loop = asyncio.get_event_loop()
    core.start_watcher(loop)
    alog.record("server_start", "system", alog.CAT_SYSTEM,
                detail={"mode": "mcp_stdio"})
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())
