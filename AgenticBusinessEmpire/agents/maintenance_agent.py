"""
maintenance_agent.py — AgenticBusinessEmpire Maintenance Agent

First task (hard-coded per spec):
    Benchmark TCO serialise/deserialise round-trip speed and log an
    optimisation recommendation to:
        AgenticBusinessEmpire/tenants/agenticbusinessempire_internal/logs/maintenance_<UTC-timestamp>.log

The agent is designed to run headlessly from the terminal:
    python3 AgenticBusinessEmpire/agents/maintenance_agent.py

It is also callable from the kernel dispatch loop via its registered
action key:  { "action": "maintenance_benchmark" }
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

_AGENTS_DIR  = Path(__file__).parent
_AGENTIC_BUSINESS_EMPIRE_DIR = _AGENTS_DIR.parent
_LOG_DIR     = _AGENTIC_BUSINESS_EMPIRE_DIR / "tenants" / "agenticbusinessempire_internal" / "logs"
_KERNEL_DIR  = _AGENTIC_BUSINESS_EMPIRE_DIR / "kernel"

sys.path.insert(0, str(_KERNEL_DIR))
from task_context import benchmark_roundtrip, TaskContext


# ---------------------------------------------------------------------------
# Logging — file + console
# ---------------------------------------------------------------------------
def _setup_logging(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fmt = "%(asctime)s  [%(levelname)s]  %(message)s"
    logger = logging.getLogger("agenticbusinessempire.maintenance")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    fh = logging.FileHandler(log_path)
    fh.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%dT%H:%M:%SZ"))
    logger.addHandler(fh)

    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%dT%H:%M:%SZ"))
    logger.addHandler(ch)
    return logger


# ---------------------------------------------------------------------------
# Benchmark task
# ---------------------------------------------------------------------------
def run_benchmark(logger: logging.Logger) -> dict:
    ITERATIONS = [100, 1_000, 10_000]
    results = {}

    logger.info("="*60)
    logger.info("AgenticBusinessEmpire Maintenance Agent — TCO Hand-off Benchmark")
    logger.info("="*60)

    for n in ITERATIONS:
        µs = benchmark_roundtrip(n)
        results[n] = µs
        verdict = "✓ FAST" if µs < 50 else ("⚠ MODERATE" if µs < 200 else "✗ SLOW")
        logger.info("  n=%-7d  %.2f µs/op  %s", n, µs, verdict)

    # Recommendation
    best = min(results.values())
    logger.info("")
    logger.info("Best observed: %.2f µs/op", best)

    if best < 50:
        rec = "TCO hand-off is within target (<50 µs). No changes required."
    elif best < 200:
        rec = (
            "TCO hand-off is moderate (50–200 µs). "
            "Consider switching JSON backend to `orjson` for a 2–4× speedup."
        )
    else:
        rec = (
            "TCO hand-off is slow (>200 µs). "
            "Profile `task_context.py` — likely cause is dataclass `asdict()` "
            "deep-copy overhead.  Switch to `__slots__` + manual dict build."
        )

    logger.info("RECOMMENDATION: %s", rec)
    logger.info("="*60)
    return {"benchmark_µs": results, "recommendation": rec}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    ts  = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = _LOG_DIR / f"maintenance_{ts}.log"
    logger   = _setup_logging(log_path)
    result   = run_benchmark(logger)

    # Save a TCO result artefact so the kernel can track this run
    tco = TaskContext.new(
        tenant="tenant_zero",
        payload={"action": "maintenance_benchmark", "result": result},
        priority=0,
        tags=["maintenance", "benchmark"],
        assigned_agent="maintenance_agent",
    )
    tco.completed_at = datetime.now(timezone.utc).isoformat()
    tco.result = result
    completed_dir = _AGENTIC_BUSINESS_EMPIRE_DIR / "runtime" / "tasks" / "completed"
    saved = tco.save(completed_dir)
    logger.info("TCO result saved → %s", saved)
    print(f"\n[AgenticBusinessEmpire] Log written to: {log_path}")


if __name__ == "__main__":
    main()
