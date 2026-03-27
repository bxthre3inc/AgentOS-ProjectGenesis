"""
ctc_engine.py — AgenticBusinessEmpire Zero-Latency Mandate
Calculates Compute-Time-to-Completion (CTC) for agentic handoffs.
Formula: ETA = T_exec + T_wait
"""
import time
import random

from AgenticBusinessEmpire.core.db import RQE

async def calculate_ctc(action: str, prompt_len: int, expected_output_tokens: int = 512) -> dict:
    """
    Predictive CTC calculation using historical metrics.
    Fallbacks to baseline if no history exists.
    """
    history = await RQE.get_performance_stats(action, limit=5)
    
    if history:
        # Calculate moving average
        avg_ms_per_token = sum(h["elapsed_ms"] / (h["output_tokens"] or 1) for h in history) / len(history)
        avg_wait_ms = sum(h["elapsed_ms"] - (h["output_tokens"] * avg_ms_per_token) for h in history) / len(history)
        
        t_exec = (expected_output_tokens * avg_ms_per_token) / 1000.0
        t_wait = max(0.2, avg_wait_ms / 1000.0)
    else:
        # Baseline: 45 tokens/sec, 1.2s latency
        t_exec = expected_output_tokens / 45.0
        t_wait = 1.2 + (prompt_len / 1000.0) * 0.5
    
    total_sec = t_exec + t_wait
    
    # Format to human-readable
    if total_sec < 60:
        human_readable = f"{round(total_sec, 1)} seconds"
    elif total_sec < 3600:
        human_readable = f"{round(total_sec / 60.0, 1)} minutes"
    else:
        human_readable = f"{round(total_sec / 3600.0, 1)} hours"
        
    return {
        "t_exec": round(t_exec, 3),
        "t_wait": round(t_wait, 3),
        "total_sec": round(total_sec, 3),
        "eta_human": human_readable,
        "source": "live_metrics" if history else "baseline_projection",
        "tokens": expected_output_tokens,
        "action": action
    }

async def inject_ctc_header(response: dict, prompt: str, action: str = "default") -> dict:
    """Inject the CTC header into the response dict."""
    ctc = await calculate_ctc(action, len(prompt))
    response["_ctc_eta"] = ctc["eta_human"]
    response["_compute_metrics"] = {
        "execution_volume": f"{ctc['tokens']} tokens",
        "wait_state": "Buffer Saturated" if ctc['t_wait'] > 2.0 else "Nominal Latency",
        "cycle_count": f"{round(ctc['total_sec'] * 10)} ops",
        "t_wait_ms": round(ctc['t_wait'] * 1000, 2)
    }
    return response
