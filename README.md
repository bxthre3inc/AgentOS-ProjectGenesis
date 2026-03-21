# AgentOS

> **Bxthre3 Inc. — Recursive Systems Kernel**
> Version 1.0.0 · Zo-Native · Headless Build

AgentOS is a self-contained, self-evolving operating layer that manages three top-level tenants
and treats its own source code as its primary optimisation target (Tenant Zero).

---

## Hierarchy

| Tier | Codename | Role |
|------|----------|------|
| Tenant Zero | `agentos_internal` | Self-improvement staging |
| Product Alpha | `starting5` | R&D product (Starting5) |
| Subsidiary Beta | `irrig8` | Ag-Tech BU (Irrig8) |

---

## Quick Start

```bash
# 1 — Bootstrap the full directory tree
bash bootstrap.sh

# 2 — Run the kernel (dry-run probe)
python3 AgentOS/kernel/kernel_main.py --dry-run

# 3 — Run the Maintenance Agent (benchmarks TCO hand-off speed)
python3 AgentOS/agents/maintenance_agent.py
```

---

## Directory Layout

```
agentos/
├── system_manifest.json          ← Tenant boundary definitions
├── bootstrap.sh                  ← Idempotent setup script
├── AgentOS/
│   ├── kernel/                   ← Core reasoning engine
│   │   ├── kernel_main.py
│   │   ├── task_context.py
│   │   └── inference_node.py
│   ├── runtime/
│   │   └── tasks/
│   │       ├── pending/
│   │       ├── completed/
│   │       └── failed/
│   ├── agents/
│   │   ├── maintenance_agent.py
│   │   └── agent_manifest.json
│   └── tenants/
│       ├── agentos_internal/     ← Tenant Zero
│       ├── starting5/            ← Product Alpha
│       └── irrig8/               ← Subsidiary Beta
```

---

## Operational Constraints

- **Fully self-contained** — all logic and data stay on the Zo instance.
- **Headless** — managed via Antigravity IDE terminal.
- **Stateless execution** — state is persisted in Task Context Objects (JSON) on disk.
