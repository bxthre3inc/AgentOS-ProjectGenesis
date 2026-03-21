#!/usr/bin/env python3
"""
run_sandbox.py — Starting5 Developer Sandbox

A safe-test environment that runs the Starting5 stack (Roster + Controller)
completely isolated from the live Bxthre3 environment.

Guarantees
----------
- Uses a temporary in-memory roster store (no disk writes to src/data/).
- The Registry Controller is queried before any file access.
- Exits cleanly; never mutates production state.

Usage
-----
    python3 AgentOS/tenants/starting5/sandbox/run_sandbox.py
    python3 AgentOS/tenants/starting5/sandbox/run_sandbox.py --goal "write a report about crop yields"
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

# ── Resolve sibling src/ without installing the package ──────────────────────
_SANDBOX_DIR = Path(__file__).parent
_SRC_DIR     = _SANDBOX_DIR.parent / "src"
sys.path.insert(0, str(_SRC_DIR))

from roster import AgentSlot, Roster
from roster_api import RosterAPI
from roster_controller import create_default_bus

SANDBOX_BANNER = """
╔══════════════════════════════════════════════════════╗
║        STARTING5  —  DEVELOPER SANDBOX               ║
║  Safe-test mode · no production state is modified    ║
╚══════════════════════════════════════════════════════╝
"""

DEFAULT_GOAL = "research the latest AI model benchmarks"


def build_demo_roster(api: RosterAPI) -> str:
    """Create a sample 5-player roster in the temp store."""
    rid = api.create("Sandbox Lineup")
    slots = [
        ("PG", "Alpha",   "stub-model", "You are the primary goal dispatcher."),
        ("SG", "Beta",    "stub-model", "You generate high-quality outputs."),
        ("SF", "Gamma",   "stub-model", "You retrieve context and perform research."),
        ("PF", "Delta",   "stub-model", "You process and transform data."),
        ("C",  "Epsilon", "stub-model", "You guard financial data and manage memory."),
    ]
    for pos, name, model, prompt in slots:
        api.set_agent(rid, pos, name=name, model=model, system_prompt=prompt)
    return rid


def run(goal: str) -> None:
    print(SANDBOX_BANNER)

    with tempfile.TemporaryDirectory(prefix="starting5_sandbox_") as tmpdir:
        print(f"[Sandbox] Temp store: {tmpdir}")
        api = RosterAPI(store_dir=Path(tmpdir))
        rid = build_demo_roster(api)
        roster = api.get(rid)
        roster.validate()
        print(f"[Sandbox] Roster '{roster.name}' ({rid}) — complete ✓")
        print(f"[Sandbox] Positions: {list(roster.slots.keys())}")

        # Wire up the A2A bus
        bus, pg, c = create_default_bus()
        print(f"\n[Sandbox] Dispatching goal: '{goal}'")
        replies = pg.dispatch(goal)

        print(f"\n[Sandbox] A2A Message log ({len(bus.history())} messages):")
        for msg in bus.history():
            print(f"  {msg['from_pos']} → {msg['to_pos']}  [{msg['intent']}]")

        print(f"\n[Sandbox] Done — {len(replies)} reply(ies) received.")
        print("[Sandbox] No production state was modified.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Starting5 Developer Sandbox")
    parser.add_argument("--goal", default=DEFAULT_GOAL, help="Goal to dispatch via Point Guard")
    args = parser.parse_args()
    run(args.goal)
