from __future__ import annotations

import time
from backend.context.models import UserContext
from backend.memory import SharedMemory


class DeviceSource:
    def __init__(self, config: dict, memory: SharedMemory):
        self.config = config
        self.memory = memory
        self._app_start_time = 0.0
        self._last_app = ""

    async def apply(self, ctx: UserContext):
        user_ctx = await self.memory.get_user_context()

        ctx.current_app = user_ctx.get("current_app", "") or ""
        ctx.screen_on = user_ctx.get("screen_on", True)
        ctx.battery_level = user_ctx.get("battery_level", 100)
        ctx.unread_messages = user_ctx.get("unread_messages", 0)
        ctx.missed_calls = user_ctx.get("missed_calls", 0)

        # Track app duration
        if ctx.current_app != self._last_app:
            self._last_app = ctx.current_app
            self._app_start_time = time.time()

        if self._app_start_time > 0:
            ctx.app_duration_minutes = int((time.time() - self._app_start_time) / 60)

        # Infer engagement from last_seen
        last_seen = user_ctx.get("last_seen", 0)
        idle_minutes = (time.time() - last_seen) / 60 if last_seen else 999

        if idle_minutes < 2:
            ctx.engagement_level = "active"
        elif idle_minutes < 15:
            ctx.engagement_level = "passive"
        else:
            ctx.engagement_level = "idle"

        ctx.sedentary_minutes = user_ctx.get("sedentary_minutes", int(idle_minutes))
