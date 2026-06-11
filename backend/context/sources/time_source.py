from __future__ import annotations

import time
from datetime import datetime
from backend.context.models import UserContext


class TimeSource:
    def __init__(self, config: dict):
        self.config = config

    async def apply(self, ctx: UserContext):
        now = datetime.now()
        ctx.timestamp = time.time()
        ctx.hour = now.hour
        ctx.day_of_week = now.strftime("%A").lower()
        ctx.is_weekend = now.weekday() >= 5

        hour = now.hour
        if 5 <= hour < 9:
            ctx.time_of_day = "early_morning"
        elif 9 <= hour < 12:
            ctx.time_of_day = "morning"
        elif 12 <= hour < 14:
            ctx.time_of_day = "midday"
        elif 14 <= hour < 17:
            ctx.time_of_day = "afternoon"
        elif 17 <= hour < 20:
            ctx.time_of_day = "evening"
        elif 20 <= hour < 23:
            ctx.time_of_day = "night"
        else:
            ctx.time_of_day = "late_night"

        ctx.is_golden_hour = (6 <= hour <= 8) or (17 <= hour <= 19)
