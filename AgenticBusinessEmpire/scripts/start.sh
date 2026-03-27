#!/usr/bin/env bash
# Zo & Antigravity Sync — Start dashboard server
set -e
WORKSPACE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WORKSPACE"
echo "🚀 Starting Zo ↔ Antigravity Sync Dashboard on http://localhost:7880"
python3 main.py dashboard
