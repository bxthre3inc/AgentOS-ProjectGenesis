# Tenant Zero — `agentos_internal`

**Role:** Self-improvement staging. AgentOS treats its own source code as **Client 0**.

## Directories
| Path | Purpose |
|------|---------|
| `logs/` | Maintenance Agent outputs, kernel audit trails |
| `staging/` | Experimental kernel patches before promotion to `/kernel/` |

## Constraints
- No external product code lives here.
- All writes must be attributed to a Maintenance Agent TCO.
