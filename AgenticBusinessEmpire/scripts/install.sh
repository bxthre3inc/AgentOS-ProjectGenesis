#!/usr/bin/env bash
# Zo & Antigravity Sync — Install dependencies
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="$SCRIPT_DIR/.."

echo "📦 Installing Python dependencies..."
cd "$WORKSPACE"
pip install -r requirements.txt --quiet

echo "✅ Done. Run ./scripts/start.sh to launch the server."
