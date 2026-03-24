"""
Zo & Antigravity 2-Way Workspace Sync — Optimized Architecture
Antigravity IDE MCP Server: exposes IDE capabilities as MCP tools.

This turns Antigravity from a pure MCP CLIENT into a full MCP SERVER
that AgentOS agents (and Zo) can call to control the IDE directly.

Tools exposed:
  open_file       — open a file in the IDE editor
  edit_file       — apply edits to a file (line ranges or full replace)
  create_file     — create a new file with content
  delete_file     — delete a file from the workspace
  get_file_tree   — browse the file system tree
  read_file       — read a file's content
  run_terminal    — execute a command in a terminal
  get_terminals   — list running terminals + recent output
  get_diagnostics — get linting/error diagnostics
  set_breakpoint  — add/remove a debugger breakpoint
  get_session     — get the current IDE session context
  update_cursor   — move cursor to file:line
  search_files    — search across files
  invoke_antigravity — send a natural language instruction to Antigravity
"""
import asyncio
import json
import os
import subprocess
from typing import Any

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent

from . import session_sync, actions_log as alog, core

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ag_server = Server("antigravity-ide")


def _ok(data: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(
        {"ok": True, **data} if isinstance(data, dict) else {"ok": True, "result": data}))]


def _err(msg: str) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps({"ok": False, "error": msg}))]


@ag_server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(name="open_file",
             description="Open a file in Antigravity IDE editor.",
             inputSchema={"type": "object", "properties": {
                 "caller": {"type": "string"},
                 "path": {"type": "string", "description": "Absolute or workspace-relative path"}
             }, "required": ["caller", "path"]}),

        Tool(name="edit_file",
             description="Apply an edit to a file in the IDE. Supports full replace or line-range patch.",
             inputSchema={"type": "object", "properties": {
                 "caller": {"type": "string"},
                 "path": {"type": "string"},
                 "content": {"type": "string", "description": "New full content OR replacement text"},
                 "start_line": {"type": "integer", "description": "Start line for range edit (1-indexed, optional)"},
                 "end_line": {"type": "integer", "description": "End line for range edit (inclusive, optional)"}
             }, "required": ["caller", "path", "content"]}),

        Tool(name="create_file",
             description="Create a new file with given content.",
             inputSchema={"type": "object", "properties": {
                 "caller": {"type": "string"},
                 "path": {"type": "string"},
                 "content": {"type": "string"},
                 "overwrite": {"type": "boolean", "default": False}
             }, "required": ["caller", "path", "content"]}),

        Tool(name="delete_file",
             description="Delete a file from the workspace.",
             inputSchema={"type": "object", "properties": {
                 "caller": {"type": "string"},
                 "path": {"type": "string"}
             }, "required": ["caller", "path"]}),

        Tool(name="read_file",
             description="Read the full content of a file.",
             inputSchema={"type": "object", "properties": {
                 "caller": {"type": "string"},
                 "path": {"type": "string"},
                 "start_line": {"type": "integer"},
                 "end_line": {"type": "integer"}
             }, "required": ["caller", "path"]}),

        Tool(name="get_file_tree",
             description="List the file tree of the workspace or a subdirectory.",
             inputSchema={"type": "object", "properties": {
                 "caller": {"type": "string"},
                 "root": {"type": "string", "default": "."},
                 "max_depth": {"type": "integer", "default": 3}
             }, "required": ["caller"]}),

        Tool(name="search_files",
             description="Search for a pattern across all workspace files (grep).",
             inputSchema={"type": "object", "properties": {
                 "caller": {"type": "string"},
                 "pattern": {"type": "string"},
                 "path": {"type": "string", "default": "."},
                 "case_sensitive": {"type": "boolean", "default": False}
             }, "required": ["caller", "pattern"]}),

        Tool(name="run_terminal",
             description="Execute a shell command in the workspace. Returns stdout/stderr.",
             inputSchema={"type": "object", "properties": {
                 "caller": {"type": "string"},
                 "command": {"type": "string"},
                 "cwd": {"type": "string", "description": "Working dir (defaults to workspace root)"},
                 "timeout": {"type": "integer", "default": 30}
             }, "required": ["caller", "command"]}),

        Tool(name="get_diagnostics",
             description="Get current linting errors and warnings for a file or all open files.",
             inputSchema={"type": "object", "properties": {
                 "caller": {"type": "string"},
                 "file": {"type": "string", "description": "Specific file (optional, omit for all)"}
             }, "required": ["caller"]}),

        Tool(name="set_breakpoint",
             description="Add or remove a debugger breakpoint at a specific file:line.",
             inputSchema={"type": "object", "properties": {
                 "caller": {"type": "string"},
                 "file": {"type": "string"},
                 "line": {"type": "integer"},
                 "add": {"type": "boolean", "default": True}
             }, "required": ["caller", "file", "line"]}),

        Tool(name="get_session",
             description="Get the current Antigravity IDE session context (open files, cursor, debugger state).",
             inputSchema={"type": "object", "properties": {
                 "caller": {"type": "string"}
             }, "required": ["caller"]}),

        Tool(name="update_cursor",
             description="Move the editor cursor to a specific file and line.",
             inputSchema={"type": "object", "properties": {
                 "caller": {"type": "string"},
                 "file": {"type": "string"},
                 "line": {"type": "integer"},
                 "col": {"type": "integer", "default": 0}
             }, "required": ["caller", "file", "line"]}),

        Tool(name="invoke_antigravity",
             description="Send a natural-language instruction to Antigravity. Returns queued task ID.",
             inputSchema={"type": "object", "properties": {
                 "caller": {"type": "string"},
                 "instruction": {"type": "string"},
                 "context_files": {"type": "array", "items": {"type": "string"}}
             }, "required": ["caller", "instruction"]}),
    ]


@ag_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    caller = arguments.get("caller", "unknown")
    alog.record(name, caller, alog.CAT_RESOURCE,
                detail={k: v for k, v in arguments.items() if k not in ("content",)})

    # ── open_file ──
    if name == "open_file":
        path = arguments["path"]
        session_sync.open_file("antigravity", path)
        return _ok({"opened": path, "session": session_sync.get_session("antigravity")})

    # ── edit_file ──
    elif name == "edit_file":
        path = arguments["path"]
        content = arguments["content"]
        abs_path = path if os.path.isabs(path) else os.path.join(WORKSPACE_ROOT, path)
        try:
            if "start_line" in arguments and "end_line" in arguments:
                with open(abs_path) as f:
                    lines = f.readlines()
                s, e = arguments["start_line"] - 1, arguments["end_line"]
                new_lines = content.splitlines(keepends=True)
                lines[s:e] = new_lines
                with open(abs_path, "w") as f:
                    f.writelines(lines)
            else:
                with open(abs_path, "w") as f:
                    f.write(content)
            session_sync.open_file("antigravity", path)
            alog.record("edit_file", caller, alog.CAT_RESOURCE, path=path,
                        detail={"chars": len(content)})
            return _ok({"edited": path, "chars": len(content)})
        except Exception as e:
            return _err(str(e))

    # ── create_file ──
    elif name == "create_file":
        path = arguments["path"]
        abs_path = path if os.path.isabs(path) else os.path.join(WORKSPACE_ROOT, path)
        if os.path.exists(abs_path) and not arguments.get("overwrite", False):
            return _err("File already exists. Set overwrite=true to replace.")
        try:
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "w") as f:
                f.write(arguments["content"])
            session_sync.open_file("antigravity", path)
            return _ok({"created": path})
        except Exception as e:
            return _err(str(e))

    # ── delete_file ──
    elif name == "delete_file":
        path = arguments["path"]
        abs_path = path if os.path.isabs(path) else os.path.join(WORKSPACE_ROOT, path)
        if not os.path.exists(abs_path):
            return _err("File not found")
        os.remove(abs_path)
        session_sync.close_file("antigravity", path)
        return _ok({"deleted": path})

    # ── read_file ──
    elif name == "read_file":
        path = arguments["path"]
        abs_path = path if os.path.isabs(path) else os.path.join(WORKSPACE_ROOT, path)
        try:
            with open(abs_path) as f:
                lines = f.readlines()
            s = arguments.get("start_line", 1) - 1
            e = arguments.get("end_line", len(lines))
            content = "".join(lines[s:e])
            return _ok({"path": path, "content": content, "total_lines": len(lines)})
        except Exception as ex:
            return _err(str(ex))

    # ── get_file_tree ──
    elif name == "get_file_tree":
        root = arguments.get("root", ".")
        max_depth = arguments.get("max_depth", 3)
        abs_root = root if os.path.isabs(root) else os.path.join(WORKSPACE_ROOT, root)
        tree = []
        for dirpath, dirnames, filenames in os.walk(abs_root):
            depth = dirpath.replace(abs_root, "").count(os.sep)
            if depth >= max_depth:
                dirnames.clear()
                continue
            indent = "  " * depth
            rel = os.path.relpath(dirpath, WORKSPACE_ROOT)
            tree.append(f"{indent}{rel}/")
            for fname in sorted(filenames):
                tree.append(f"{indent}  {fname}")
        return _ok({"tree": "\n".join(tree), "root": root})

    # ── search_files ──
    elif name == "search_files":
        pattern = arguments["pattern"]
        path = arguments.get("path", ".")
        cs = arguments.get("case_sensitive", False)
        abs_path = path if os.path.isabs(path) else os.path.join(WORKSPACE_ROOT, path)
        flags = [] if cs else ["-i"]
        try:
            result = subprocess.run(
                ["grep", "-rn", "--include=*", *flags, pattern, abs_path],
                capture_output=True, text=True, timeout=15
            )
            matches = result.stdout.strip().splitlines()[:100]
            return _ok({"matches": matches, "count": len(matches)})
        except Exception as ex:
            return _err(str(ex))

    # ── run_terminal ──
    elif name == "run_terminal":
        command = arguments["command"]
        cwd = arguments.get("cwd", WORKSPACE_ROOT)
        timeout = arguments.get("timeout", 30)
        alog.record("run_terminal", caller, alog.CAT_SYSTEM,
                    detail={"command": command[:120]})
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                cwd=cwd, timeout=timeout
            )
            terminal_entry = {
                "command": command,
                "cwd": cwd,
                "exit_code": result.returncode,
                "stdout": result.stdout[-2000:],
                "stderr": result.stderr[-500:]
            }
            # Update session with terminal history
            sess = session_sync.get_session("antigravity")
            terms = sess.get("running_terminals", [])[-9:]
            terms.append(terminal_entry)
            session_sync.update_session("antigravity", {"running_terminals": terms})
            return _ok(terminal_entry)
        except subprocess.TimeoutExpired:
            return _err(f"Command timed out after {timeout}s")
        except Exception as ex:
            return _err(str(ex))

    # ── get_diagnostics ──
    elif name == "get_diagnostics":
        sess = session_sync.get_session("antigravity")
        diags = sess.get("diagnostics", [])
        file_filter = arguments.get("file")
        if file_filter:
            diags = [d for d in diags if d.get("file") == file_filter]
        return _ok({"diagnostics": diags, "count": len(diags)})

    # ── set_breakpoint ──
    elif name == "set_breakpoint":
        sess = session_sync.set_breakpoint(
            "antigravity", arguments["file"],
            arguments["line"], arguments.get("add", True))
        return _ok({"breakpoints": sess["debugger"]["breakpoints"]})

    # ── get_session ──
    elif name == "get_session":
        return _ok({"session": session_sync.get_session("antigravity")})

    # ── update_cursor ──
    elif name == "update_cursor":
        session_sync.set_cursor("antigravity", arguments["file"],
                                arguments["line"], arguments.get("col", 0))
        return _ok({"cursor": {"file": arguments["file"],
                               "line": arguments["line"],
                               "col": arguments.get("col", 0)}})

    # ── invoke_antigravity ──
    elif name == "invoke_antigravity":
        # Queue the instruction as a command for Antigravity to pick up
        from . import command_bus
        cmd_id = await command_bus.issue_command(
            caller, "antigravity", "send_message",
            {"topic": "agent_instruction",
             "body": {"instruction": arguments["instruction"],
                      "context_files": arguments.get("context_files", [])}}
        )
        alog.record("invoke_antigravity", caller, alog.CAT_COMMAND,
                    target_agent="antigravity",
                    detail={"instruction": arguments["instruction"][:120]})
        return _ok({"queued": True, "cmd_id": cmd_id,
                    "instruction": arguments["instruction"]})

    return _err(f"Unknown tool: {name}")
