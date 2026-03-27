"""
resource_monitor.py — AgenticBusinessEmpire Granular Resource Monitoring & Throttling
(Foxxd S67 / Mobile Optimized)
"""

import os
import time
import logging
from enum import Enum
from dataclasses import dataclass
from AgenticBusinessEmpire.core import config

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    _PSUTIL_AVAILABLE = False

logger = logging.getLogger("agenticbusinessempire.resource_monitor")

class PerformanceProfile(Enum):
    TURBO    = "turbo"     # Max speed, 0 delay, local LLM
    HIGH     = "performance" # High speed, tiny delay, local LLM
    BALANCED = "balanced"  # Mid speed, 500ms delay, local LLM
    LOW      = "low"       # Slow speed, 1s delay, minimal local LLM
    CRITICAL = "economy"   # Minimal speed, 3s delay, minimal local LLM

@dataclass
class Thresholds:
    ram_percent_min: float
    ram_gb_min: float
    cpu_percent_max: float
    delay_sec: float

# More dynamic scaling based on system percentages
PROFILES = {
    PerformanceProfile.TURBO:    Thresholds(ram_percent_min=80.0, ram_gb_min=4.0, cpu_percent_max=15.0, delay_sec=0.0),
    PerformanceProfile.HIGH:     Thresholds(ram_percent_min=60.0, ram_gb_min=2.0, cpu_percent_max=35.0, delay_sec=0.1),
    PerformanceProfile.BALANCED: Thresholds(ram_percent_min=40.0, ram_gb_min=1.5, cpu_percent_max=60.0, delay_sec=0.5),
    PerformanceProfile.LOW:      Thresholds(ram_percent_min=20.0, ram_gb_min=1.0, cpu_percent_max=85.0, delay_sec=1.5),
    PerformanceProfile.CRITICAL: Thresholds(ram_percent_min=0.0,  ram_gb_min=0.0, cpu_percent_max=100.0, delay_sec=3.0),
}

def get_current_profile() -> PerformanceProfile:
    """Assess system state and return the most adaptive performance profile."""
    if not _PSUTIL_AVAILABLE:
        return PerformanceProfile.BALANCED

    try:
        mem = psutil.virtual_memory()
        available_gb = mem.available / (1024**3)
        available_p = (mem.available / mem.total) * 100
        cpu_p = psutil.cpu_percent(interval=0.1)
        
        # Foxxd S67 / Mobile Battery Awareness
        battery = psutil.sensors_battery()
        if battery:
            # Force CRITICAL if battery < 15% and not charging
            if battery.percent < 15 and not battery.power_plugged:
                logger.warning("[Resource Monitor] Battery %d%% (Critical) — Forcing ECONOMY mode.", battery.percent)
                return PerformanceProfile.CRITICAL
            # Force LOW if battery < 30% and not charging
            if battery.percent < 30 and not battery.power_plugged:
                return PerformanceProfile.LOW

        # Iterate through profiles from highest to lowest
        for profile in [PerformanceProfile.TURBO, PerformanceProfile.HIGH, PerformanceProfile.BALANCED, PerformanceProfile.LOW]:
            t = PROFILES[profile]
            if available_p >= t.ram_percent_min and available_gb >= t.ram_gb_min and cpu_p <= t.cpu_percent_max:
                return profile

        return PerformanceProfile.CRITICAL
    except Exception as e:
        logger.warning("Dynamic monitoring failed: %s. Defaulting to BALANCED.", e)
        return PerformanceProfile.BALANCED

def get_pressure_report() -> dict:
    """Return a comprehensive health report for mesh orchestration."""
    if not _PSUTIL_AVAILABLE:
        return {"profile": "balanced", "cpu_p": 0, "ram_p": 0, "battery_p": 100}

    try:
        mem = psutil.virtual_memory()
        cpu_p = psutil.cpu_percent(interval=0.1)
        battery = psutil.sensors_battery()
        
        return {
            "profile": get_current_profile().value,
            "cpu_p": round(cpu_p, 1),
            "ram_p": round((mem.available / mem.total) * 100, 1),
            "battery_p": battery.percent if battery else 100,
            "is_charging": battery.power_plugged if battery else True,
            "is_server": config.IS_SERVER
        }
    except Exception:
        return {"profile": "balanced", "cpu_p": 0, "ram_p": 0}

import signal

# Track suspended agents
_suspended_pids = set()

def check_and_throttle_system():
    """Evaluate system state and apply throttling or suspension."""
    profile = get_current_profile()
    
    if profile == PerformanceProfile.CRITICAL:
        logger.warning("[Resource Monitor] CRITICAL PRESSURE: Suspending non-core agent processes.")
        if _PSUTIL_AVAILABLE:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    # Skip self and critical system components
                    cmdline = " ".join(proc.info['cmdline'] or [])
                    if any(x in cmdline for x in ["inference_node.py", "ag_server", "mcp_server", "sshd"]):
                        continue
                    
                    if proc.pid == os.getpid():
                        continue
                        
                    # Suspend non-critical agents
                    if proc.pid not in _suspended_pids:
                        logger.info("Suspending low-priority process: %s (PID: %d)", proc.info['name'], proc.pid)
                        proc.suspend()
                        _suspended_pids.add(proc.pid)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        return True
    
    # If pressure is relieved, resume everything
    if profile != PerformanceProfile.CRITICAL and _suspended_pids:
        logger.info("[Resource Monitor] Pressure relieved. Resuming agents.")
        for pid in list(_suspended_pids):
            try:
                p = psutil.Process(pid)
                p.resume()
                logger.info("Resumed PID: %d", pid)
            except Exception:
                pass
        _suspended_pids.clear()
        
    return False

def throttle() -> float:
    """Inject a dynamic sleep duration based on systemic pressure."""
    profile = get_current_profile()
    delay = PROFILES[profile].delay_sec
    
    # Auto-suspend logic if memory is very tight
    check_and_throttle_system()

    if delay > 0:
        logger.info("[Resource Monitor] Pressure Level: %s | Delay: %.2fs", profile.value.upper(), delay)
        time.sleep(delay)
    
    return delay
