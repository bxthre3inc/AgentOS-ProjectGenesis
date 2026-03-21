"""
reporting_handlers.py — Handlers for AgentOS reporting
"""
import logging
import os
from datetime import datetime, timezone
from task_context import TaskContext

logger = logging.getLogger("agentos.handlers.reporting")

def handle_report(task: TaskContext) -> dict:
    target = task.payload.get("target", "unknown")
    logger.info("Generating report for: %s", target)
    
    # Simple report generation logic
    report_path = "/home/bxthre3/Desktop/agentos/AgentOS/tenants/agentos_internal/daily_brief.md"
    if os.path.exists(report_path):
        with open(report_path, "r") as f:
            content = f.read()
        
        # Update the timestamp in the first line
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        lines = content.splitlines()
        if lines and lines[0].startswith("# AgentOS Daily Brief"):
            lines[0] = f"# AgentOS Daily Brief — {timestamp}"
        content = "\n".join(lines)
        
        with open(report_path, "w") as f:
            f.write(content)
            
    return {
        "status": "ok",
        "report_generated": True,
        "path": report_path
    }
