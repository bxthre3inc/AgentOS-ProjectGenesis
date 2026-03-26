#!/usr/bin/env bash
# =============================================================================
# bootstrap.sh — AgentOS Project Genesis
# Idempotent: safe to re-run at any time.
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/AgentOS"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[AgentOS]${NC} $*"; }
ok()    { echo -e "${GREEN}  ✓${NC} $*"; }

info "Starting Project Genesis bootstrap..."
info "Root → $ROOT"

# ---------------------------------------------------------------------------
# Helper: create directory and confirm
# ---------------------------------------------------------------------------
mk() {
  mkdir -p "$1"
  ok "$1"
}

# ---------------------------------------------------------------------------
# Kernel
# ---------------------------------------------------------------------------
info "── Kernel"
mk "$ROOT/kernel"

# ---------------------------------------------------------------------------
# Runtime / Task Context Object store
# ---------------------------------------------------------------------------
info "── Runtime"
mk "$ROOT/runtime/tasks/pending"
mk "$ROOT/runtime/tasks/completed"
mk "$ROOT/runtime/tasks/failed"

# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------
info "── Agents"
mk "$ROOT/agents"

# ---------------------------------------------------------------------------
# Tenant Zero — agentos_internal
# ---------------------------------------------------------------------------
info "── Tenants"
mk "$ROOT/tenants/agentos_internal/logs"
mk "$ROOT/tenants/agentos_internal/staging"
touch "$ROOT/tenants/agentos_internal/logs/.gitkeep"
touch "$ROOT/tenants/agentos_internal/staging/.gitkeep"

# ---------------------------------------------------------------------------
# Product Alpha — starting5
# ---------------------------------------------------------------------------
mk "$ROOT/tenants/starting5/src"
mk "$ROOT/tenants/starting5/ui"
mk "$ROOT/tenants/starting5/dist"
touch "$ROOT/tenants/starting5/src/.gitkeep"
touch "$ROOT/tenants/starting5/ui/.gitkeep"
touch "$ROOT/tenants/starting5/dist/.gitkeep"

# ---------------------------------------------------------------------------
# Subsidiary Beta — irrig8
# ---------------------------------------------------------------------------
mk "$ROOT/tenants/irrig8/sensor_data"
mk "$ROOT/tenants/irrig8/mapping"
mk "$ROOT/tenants/irrig8/actuation"
touch "$ROOT/tenants/irrig8/sensor_data/.gitkeep"
touch "$ROOT/tenants/irrig8/mapping/.gitkeep"
touch "$ROOT/tenants/irrig8/actuation/.gitkeep"

# ---------------------------------------------------------------------------
# Security & Environment
# ---------------------------------------------------------------------------
info "── Security & Environment"
VAULT="$BASE_DIR/secrets/.vault"
mk "$VAULT"

if [ ! -f "$VAULT/mesh.key" ]; then
  info "Generating Mesh Key..."
  openssl rand -hex 32 > "$VAULT/mesh.key"
  ok "Generated $VAULT/mesh.key"
fi

if [ ! -f "$VAULT/ledger.key" ]; then
  info "Generating Ledger Key (Fernet)..."
  python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" > "$VAULT/ledger.key"
  ok "Generated $VAULT/ledger.key"
fi

if [ ! -f "$BASE_DIR/.env" ] && [ -f "$BASE_DIR/.env.example" ]; then
  info "Creating .env from .env.example..."
  cp "$BASE_DIR/.env.example" "$BASE_DIR/.env"
  ok "Created .env"
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
info ""
info "Bootstrap complete. Directory tree:"
if command -v tree &>/dev/null; then
  tree "$ROOT" --dirsfirst -a -I ".gitkeep" 2>/dev/null || true
else
  find "$ROOT" -type d | sort
fi

info ""
info "Next steps:"
echo "  python3 AgentOS/kernel/kernel_main.py --dry-run"
echo "  python3 AgentOS/agents/maintenance_agent.py"
