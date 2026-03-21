"""
kernel_main.py — AgentOS Kernel Entry Point

Usage
-----
  # Normal run — process all pending TCOs
  python3 AgentOS/kernel/kernel_main.py

  # Dry-run — scan inbox and report without processing
  python3 AgentOS/kernel/kernel_main.py --dry-run

  # Process a single TCO by file
  python3 AgentOS/kernel/kernel_main.py --task path/to/task.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import asyncio
from pathlib import Path

# ---------------------------------------------------------------------------
# Path bootstrap — so the kernel can always import its siblings.
# ---------------------------------------------------------------------------
_KERNEL_DIR  = Path(__file__).parent
_AGENTOS_DIR = _KERNEL_DIR.parent
_MANIFEST    = _AGENTOS_DIR.parent / "system_manifest.json"
_INBOX       = _AGENTOS_DIR / "runtime" / "tasks" / "pending"

sys.path.insert(0, str(_KERNEL_DIR))
sys.path.insert(0, str(_AGENTOS_DIR))
from task_context import TaskContext
import inference_node

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(name)s]  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger("agentos.kernel")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_manifest() -> dict:
    if _MANIFEST.exists():
        return json.loads(_MANIFEST.read_text())
    logger.warning("system_manifest.json not found at %s", _MANIFEST)
    return {}


def scan_inbox() -> list[Path]:
    if not _INBOX.exists():
        return []
    return sorted(_INBOX.glob("*.json"))


def process_all(dry_run: bool = False) -> int:
    pending = scan_inbox()
    logger.info("[AgentOS] %d pending task(s) in inbox.", len(pending))

    if not pending:
        logger.info("[AgentOS] Kernel idle — nothing to process.")
        return 0

    success, failed = 0, 0
    for path in pending:
        try:
            task = TaskContext.from_file(path)
            if dry_run:
                logger.info("[DRY-RUN] Would process task %s (action=%s, tenant=%s)",
                            task.task_id, task.payload.get("action"), task.tenant)
                continue

            logger.info("Processing task %s …", task.task_id)
            inference_node.process(task)

            # Remove from inbox after successful processing
            path.unlink(missing_ok=True)
            success += 1

        except Exception as exc:
            logger.error("Failed to process %s: %s", path.name, exc)
            failed += 1

    logger.info("[AgentOS] Done — %d succeeded, %d failed.", success, failed)
    return failed  # non-zero exit code if any failures


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="AgentOS Kernel")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Scan and report without executing any tasks."
    )
    parser.add_argument(
        "--task", metavar="FILE",
        help="Process a single TCO JSON file directly."
    )
    args = parser.parse_args()

    manifest = load_manifest()
    if manifest:
        logger.info("[AgentOS] System manifest loaded. Version: %s",
                    manifest.get("manifest_version", "?"))
    else:
        logger.warning("[AgentOS] Running without system_manifest.json.")

    # Initialize DB Layer
    import asyncio
    import db
    asyncio.run(db.init_pool())
    asyncio.run(db.migrate())

    if args.task:
        path = Path(args.task)
        if not path.exists():
            logger.error("Task file not found: %s", path)
            sys.exit(1)
        task = TaskContext.from_file(path)
        inference_node.process(task)
        sys.exit(0)

    exit_code = process_all(dry_run=args.dry_run)
    asyncio.run(db.close_pool())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
