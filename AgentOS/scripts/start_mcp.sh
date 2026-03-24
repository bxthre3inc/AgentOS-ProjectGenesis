#!/usr/bin/env bash
# Zo & Antigravity Sync — Start MCP stdio server (used by Gemini CLI / Zo.Computer)
set -e
WORKSPACE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WORKSPACE"
exec python3 main.py mcp
