from __future__ import annotations

import logging
from backend.capabilities.registry import CapabilityProvider, CapabilityResult

logger = logging.getLogger("capabilities.device")


class NotificationProvider(CapabilityProvider):
    id = "device.notification"
    name = "Local Notification"
    description = "Send a notification to the user via WebSocket"
    category = "device"

    @property
    def available(self) -> bool:
        return True

    async def execute(self, params: dict) -> CapabilityResult:
        title = params.get("title", "AgentOS")
        body = params.get("body", "")
        return CapabilityResult(success=True, data={
            "type": "notification",
            "title": title,
            "body": body,
        })


class ShortcutTriggerProvider(CapabilityProvider):
    id = "device.shortcut"
    name = "iOS Shortcut"
    description = "Trigger an iOS Shortcut via Pushcut webhook"
    category = "device"

    @property
    def available(self) -> bool:
        return bool(self.config.get("pushcut_webhook"))

    async def execute(self, params: dict) -> CapabilityResult:
        shortcut_name = params.get("shortcut_name", "")
        input_data = params.get("input", "")
        pushcut_url = self.config.get("pushcut_webhook", "")

        if not self.available:
            return CapabilityResult(success=True, data={
                "demo": True,
                "message": f"[Demo] Would trigger shortcut: {shortcut_name}",
            })

        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{pushcut_url}/{shortcut_name}",
                    json={"input": input_data},
                )
                return CapabilityResult(
                    success=resp.status_code == 200,
                    data={"shortcut": shortcut_name, "status": resp.status_code},
                )
        except Exception as e:
            return CapabilityResult(success=False, error=str(e))
