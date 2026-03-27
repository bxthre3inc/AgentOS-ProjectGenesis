"""
roster_api.py — Starting5 Local Roster API

A minimal, self-contained API layer over the Roster model.
This is what UI code (desktop, web, or CLI) calls — it never
touches AgenticBusinessEmpire kernel internals or Bxthre3 financial/asset data.

Data isolation guarantees
--------------------------
- No imports from AgenticBusinessEmpire kernel (`task_context`, `inference_node`, `db`).
- Persists rosters to a local JSON store under the starting5 tenant.
- The roster file format contains ONLY Starting5 data (no Bxthre3 ledger refs).

Usage
-----
    api = RosterAPI()
    rid = api.create("My Team")
    api.set_agent(rid, "PG", name="Alpha", model="gemini-2.5-pro",
                  system_prompt="You route tasks.")
    api.set_agent(rid, "SG", ...)  # repeat for SG, SF, PF, C
    roster = api.get(rid)
    roster.validate()   # raises if lineup is incomplete
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from roster import AgentSlot, Position, Roster

logger = logging.getLogger("starting5.roster_api")

# Persisted to the starting5 tenant's src/ directory by default.
_DEFAULT_STORE = Path(__file__).parent / "data" / "rosters"


class RosterAPI:

    def __init__(self, store_dir: Path = _DEFAULT_STORE) -> None:
        self.store_dir = store_dir
        store_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def create(self, name: str) -> str:
        """Create a new empty Roster.  Returns its roster_id."""
        roster = Roster.create(name)
        self._save(roster)
        logger.info("Created roster %s ('%s')", roster.roster_id, name)
        return roster.roster_id

    def get(self, roster_id: str) -> Roster:
        path = self._path(roster_id)
        if not path.exists():
            raise KeyError(f"Roster '{roster_id}' not found.")
        return Roster.from_json(path.read_text())

    def list_all(self) -> list[dict]:
        result = []
        for p in sorted(self.store_dir.glob("*.json")):
            try:
                r = Roster.from_json(p.read_text())
                result.append({
                    "roster_id":   r.roster_id,
                    "name":        r.name,
                    "is_complete": r.is_complete,
                    "created_at":  r.created_at,
                })
            except Exception as exc:
                logger.warning("Skipping malformed roster %s: %s", p.name, exc)
        return result

    def delete(self, roster_id: str) -> None:
        path = self._path(roster_id)
        if path.exists():
            path.unlink()
            logger.info("Deleted roster %s", roster_id)

    # ------------------------------------------------------------------
    # Slot management
    # ------------------------------------------------------------------
    def set_agent(
        self,
        roster_id: str,
        position: Position,
        name: str,
        model: str,
        system_prompt: str,
        enabled: bool = True,
    ) -> None:
        roster = self.get(roster_id)
        slot = AgentSlot(
            position=position,
            name=name,
            model=model,
            system_prompt=system_prompt,
            enabled=enabled,
        )
        roster.set(slot)
        self._save(roster)
        logger.info("Set %s → %s in roster %s", position, name, roster_id)

    def remove_agent(self, roster_id: str, position: Position) -> None:
        roster = self.get(roster_id)
        roster.remove(position)
        self._save(roster)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _path(self, roster_id: str) -> Path:
        return self.store_dir / f"{roster_id}.json"

    def _save(self, roster: Roster) -> None:
        self._path(roster.roster_id).write_text(roster.to_json())
