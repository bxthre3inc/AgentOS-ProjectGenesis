import sys
from pathlib import Path

# Add kernel to path
sys.path.insert(0, str(Path(__file__).parent / "AgentOS" / "kernel"))

import resource_monitor
from resource_monitor import PerformanceProfile

def test_profiles():
    print("--- Testing AgentOS Resource Monitor ---")
    
    # Current Real Stats
    profile = resource_monitor.get_current_profile()
    print(f"Current System Profile: {profile.name}")
    
    # Test throttling (will sleep if non-ULTRA)
    start = time.time()
    resource_monitor.throttle()
    end = time.time()
    print(f"Throttled for {end - start:.2f} seconds.")

if __name__ == "__main__":
    import time
    test_profiles()
