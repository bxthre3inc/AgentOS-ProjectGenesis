"""
ctc_engine.py — AgentOS Zero-Latency Mandate
Calculates Compute-Time-to-Completion (CTC) for agentic handoffs.
Formula: ETA = T_exec + T_wait
"""
import time
import random

def calculate_ctc(prompt_len: int, expected_output_tokens: int = 512) -> dict:
    """
    Predictive CTC calculation.
    T_exec: Based on a baseline of 50 tokens/sec (simulated).
    T_wait: Based on current API latency + dependency overhead.
    """
    # Baseline metrics (could be dynamic in a real cluster)
    tokens_per_sec = 45.0 
    base_latency_sec = 1.2 # TLS handshake + mesh routing
    
    # T_exec calculation
    t_exec = expected_output_tokens / tokens_per_sec
    
    # T_wait calculation (simulated jitter/congestion)
    t_wait = base_latency_sec + (prompt_len / 1000.0) * 0.5
    
    total_sec = t_exec + t_wait
    
    # Format to human readable
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
        "logic": "T_exec (Tokens/TPS) + T_wait (Mesh_Latency)"
    }

def inject_ctc_header(response: dict, prompt: str) -> dict:
    """Inject the CTC header into the response dict."""
    ctc = calculate_ctc(len(prompt))
    response["_ctc_eta"] = ctc["eta_human"]
    response["_compute_metrics"] = {
        "execution_volume": "T+ tokens",
        "wait_state": "Async Buffer",
        "cycle_count": "N Cycles"
    }
    return response
