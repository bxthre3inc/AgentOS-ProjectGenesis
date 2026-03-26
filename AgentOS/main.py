#!/usr/bin/env python3
"""
Zo & Antigravity 2-Way Workspace Sync
Entry point — starts MCP stdio server OR HTTP dashboard server
"""
import argparse
import asyncio
import subprocess
import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
# Ensure both the current dir and its parent are in path for flexible execution
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(ROOT))


from sync_engine.mcp_server import run_mcp
from sync_engine.api import run_dashboard
from kernel import schema


def run_ide_server():
    """Start the Antigravity IDE MCP server (HTTP/SSE)."""
    import uvicorn
    from sync_engine.antigravity_server import ag_server
    from fastapi import FastAPI
    # This server provides SSE for IDE connections
    uvicorn.run(ag_server, host="0.0.0.0", port=7881, log_level="error")


def run_both():
    """Start Hub MCP Server (stdio) + Dashboard (HTTP) concurrently."""
    import threading
    t = threading.Thread(target=run_dashboard, daemon=True)
    t.start()
    run_mcp()


def run_mesh():
    """Start the full 3-way symmetric mesh (Hub + IDE Server + Dashboard)."""
    import threading
    import time

    print("\n\033[1;35m Zo ↔ Antigravity ↔ AgentOS 3-Way Mesh starting...\033[0m")
    
    # Initialize Standalone DB
    print("\033[34m[0/4] Initializing AgentOS Master Ledger (Chromebox Profile)...\033[0m")
    asyncio.run(schema.apply())

    print("\033[34m[1/4] Launching Sync Engine Dashboard on :7880...\033[0m")
    threading.Thread(target=run_dashboard, daemon=True).start()

    print("\033[34m[3/4] Launching Antigravity IDE Server on :7881...\033[0m")
    threading.Thread(target=run_ide_server, daemon=True).start()

    time.sleep(1)
    print("\033[34m[4/4] Launching Hub MCP Server on stdio (READY)\033[0m\n")
    asyncio.run(run_mcp())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Zo ↔ Antigravity ↔ AgentOS 3-Way MCP Mesh")
    parser.add_argument("mode", nargs="?", default="mesh",
                        choices=["mcp", "dashboard", "both", "mesh"],
                        help="mcp=stdio Hub | dashboard=HTTP UI | both=mcp+dashboard | mesh=full 3-way")
    args = parser.parse_args()

    if args.mode == "mcp":
        asyncio.run(run_mcp())
    elif args.mode == "both":
        run_both()
    elif args.mode == "mesh":
        run_mesh()
    else:
        run_dashboard()

