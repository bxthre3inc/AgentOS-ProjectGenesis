# AgenticBusinessEmpire CI/CD Gap Analysis — Zo Hosting Integration

**Date:** 2026-03-26  
**Pipeline Status:** 🟠 PARTIAL — Native builds work, Zo deployment missing

---

## Current State: CI/CD Pipeline

### What Works (`main.yml`)

| Job | Status | Output |
|-----|--------|--------|
| `test` | ✅ | Python 3.13, pytest runs 4 test files |
| `build-native` | ✅ | Android APK + Linux .deb generated |
| `package-server` | ✅ | `agenticbusinessempire-server.zip` artifact |
| `deploy-server` | ❌ **SIMULATION ONLY** | Echoes fake success message |
| `release` | ✅ | GitHub release with artifacts |

### Critical Gap

**Line 122 of `main.yml`:**
```yaml
- name: Trigger Zo Mesh Slot Update
  run: |
    echo "Deploying to Zo Hosted ID: zag-mesh-single-slot"
    # Simulated deployment success as in the original deploy-server.yml
```

**This does NOTHING.** It doesn't call Zo APIs, doesn't update routes, doesn't deploy.

---

## Current State: Zo.space Deployed Routes

These routes **already exist** on `brodiblanco.zo.space` but are **NOT** deployed by CI/CD:

### AgenticBusinessEmpire API Routes (public)
| Route | Status | Authenticated | Notes |
|-------|--------|---------------|-------|
| `/api/agenticbusinessempire/status` | ✅ | Yes (Bearer token) | Returns dashboard data |
| `/api/agenticbusinessempire/integrations` | ✅ | No | 13 integrations listed |
| `/api/agenticbusinessempire/org` | ✅ | No | Org chart hierarchy |
| `/api/agenticbusinessempire/workforce/metrics` | ✅ | No | Workforce analytics |
| `/api/agenticbusinessempire/tasks` | ✅ | No | Task list endpoint |
| `/api/agenticbusinessempire/starting5` | ✅ | No | Starting 5 data |
| `/api/agenticbusinessempire/projects` | ✅ | No | Projects data |
| `/api/agenticbusinessempire/agents` | ✅ | No | Agent roster |
| `/api/agenticbusinessempire/escalations` | ✅ | No | P0/P1 escalations |
| `/api/agenticbusinessempire/workqueue` | ✅ | No | Background tasks |

### AgenticBusinessEmpire Web Routes
| Route | Auth | Notes |
|-------|------|-------|
| `/aos` | Private | React dashboard (v4) — current build |
| `/mesh` | Public | Status page |

---

## What's Missing

### 1. Actual Zo Deployment in CI/CD

**Current zo_deploy.json:**
```json
{
  "name": "zag-mesh-single-slot",
  "runtime": "python3",
  "entrypoint": "python3 main.py mesh"
}
```

**Problem:** Zo.space runs **Hono + React** (TypeScript), not Python.

The `zo_deploy.json` references a Python server that **cannot** run on Zo.space. The actual routes are manually created via `update_space_route()` API.

### 2. Route Deployment via GitHub Actions

Need to add to `main.yml`:
```yaml
- name: Deploy to Zo.space
  uses: zocomputer/zo-action@v1
  with:
    token: ${{ secrets.ZO_API_TOKEN }}
    routes: |
      /api/agenticbusinessempire/status
      /api/agenticbusinessempire/integrations
      /aos
```

### 3. Build Artifact Sync

Android APK builds but **NOT** automatically published to download endpoint:

```
Trash/ARCHIVED_2026-03-26/the-agenticbusinessempire-native/releases/agenticbusinessempire-6.0.0-debug.apk
```

This should be deployed to `/download/agenticbusinessempire.apk` route.

---

## Required Actions

### Immediate (P0)

| Action | Assignee | Effort |
|--------|----------|--------|
| Create Zo API deploy script in CI | Dev | 4h |
| Generate `ZO_API_TOKEN` secret | brodiblanco | 10m |
| Update `main.yml` with real deploy step | Dev | 2h |

### Short-term (P1)

| Action | Assignee | Effort |
|--------|----------|--------|
| Auto-deploy APK to `/download/agenticbusinessempire.apk` | Dev | 3h |
| Add route health check post-deploy | Dev | 2h |
| Version pinning for API routes | Dev | 4h |

---

## Key Insight

Your **AgenticBusinessEmpire v6.0.0 server** (Python) runs FastAPI on port 7880-7881 locally, but **Zo.space uses Hono routes**. These are two different deployment targets:

1. **Local/Tauri/Python:** The `main.py mesh` server (ports 7880-7881)
2. **Zo.space Routes:** TypeScript files deployed via `update_space_route()`

The CI/CD currently only handles #1. It needs to handle #2.

---

## Recommended CI/CD Split

```yaml
# main.yml additions
jobs:
  deploy-zo-routes:
    needs: package-server
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy API Routes
        run: |
          curl -X POST https://api.zo.computer/space/update-route \
            -H "Authorization: Bearer ${{ secrets.ZO_API_TOKEN }}" \
            --data-binary @routes/api-agenticbusinessempire-status.ts
      - name: Deploy Dashboard
        run: |
          curl -X POST https://api.zo.computer/space/update-route \
            -H "Authorization: Bearer ${{ secrets.ZO_API_TOKEN }}" \
            --data-binary @routes/aos.tsx
```

Or use the `service_doctor` pattern for the Python server on a different hosting provider.
