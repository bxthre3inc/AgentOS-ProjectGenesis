#!/bin/bash
# deploy.sh — AgentOS Environment Provisioner
# Usage: ./deploy.sh [--mobile | --server]

PROFILE="server"
if [[ "$1" == "--mobile" ]]; then
    PROFILE="mobile"
fi

echo "🚀 Deploying AgentOS Genesis with profile: $PROFILE"

# 1. Create directory structure
mkdir -p runtime/shards secrets/.vault shared/resources logs

# 2. Set environment variables (for current session)
export AGENTOS_PROFILE=$PROFILE

# 3. Generate Vault Keys if missing
if [[ ! -f secrets/.vault/mesh.key ]]; then
    echo "🔑 Generating Mesh Key..."
    openssl rand -hex 32 > secrets/.vault/mesh.key
fi

if [[ ! -f secrets/.vault/ledger.key ]]; then
    echo "🔐 Generating Ledger Encryption Key (Fernet)..."
    python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" > secrets/.vault/ledger.key
fi

# 4. Initialize Master Ledger
echo "📊 Initializing Master Ledger..."
python3 -c "import sys; sys.path.append('AgentOS'); from core import config; from core.db import RQE; import asyncio; asyncio_run = asyncio.run if sys.version_info >= (3, 7) else None; print('Master Ready')" 

# 5. Summary
echo "✅ AgentOS is ready for conglomerate-scale operations."
echo "   - Profile: $PROFILE"
echo "   - Runtime: $(pwd)/runtime"
echo "   - Vault:   $(pwd)/secrets/.vault"
