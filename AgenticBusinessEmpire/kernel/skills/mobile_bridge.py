"""
mobile_bridge.py — AgenticBusinessEmpire Mobile Integration
Provides a bridge for state synchronization and push notifications for the Android client.
"""
import logging
from AgenticBusinessEmpire.kernel.registry import registry
from AgenticBusinessEmpire.core.models import TaskContext

logger = logging.getLogger("agenticbusinessempire.mobile_bridge")

class MobileBridge:
    def __init__(self):
        self.connected_devices = []

    async def sync_state(self, device_id: str, state_delta: dict):
        """Syncs kernel state delta to the mobile device."""
        logger.info(f"Syncing state to mobile device {device_id}: {list(state_delta.keys())}")
        return {"status": "synced", "device_id": device_id}

    async def send_push_notification(self, device_id: str, title: str, message: str):
        """Stub for sending FCM or native push notifications."""
        logger.info(f"Pushing notification to {device_id}: {title} - {message}")
        return {"status": "sent", "device_id": device_id}

mobile_bridge = MobileBridge()

@registry.register("mobile_sync")
async def handle_mobile_sync(task: TaskContext) -> dict:
    """Entry point for mobile synchronization tasks."""
    action = task.payload.get("sub_action", "sync_state")
    device_id = task.payload.get("device_id", "emulator_0")
    
    if action == "sync_state":
        delta = task.payload.get("delta", {})
        return await mobile_bridge.sync_state(device_id, delta)
    elif action == "push_notification":
        title = task.payload.get("title", "AgenticBusinessEmpire Alert")
        msg = task.payload.get("message", "A task requires your attention.")
        return await mobile_bridge.send_push_notification(device_id, title, msg)
    
    return {"error": f"Unknown mobile action: {action}"}
