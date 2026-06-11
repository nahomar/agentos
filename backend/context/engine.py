from __future__ import annotations

import asyncio
import logging
import time
from typing import List

from backend.context.models import UserContext, WeatherData, Location
from backend.context.sources.time_source import TimeSource
from backend.context.sources.weather_source import WeatherSource
from backend.context.sources.location_source import LocationSource
from backend.context.sources.device_source import DeviceSource
from backend.memory import SharedMemory
from backend.context.patterns import PatternEngine
from backend.database import store_context_snapshot

logger = logging.getLogger("context")


class ContextEngine:
    """Aggregates context from multiple sources into a unified UserContext."""

    def __init__(self, memory: SharedMemory, config: dict):
        self.memory = memory
        self.config = config
        self.current = UserContext()
        self._running = False

        self.patterns = PatternEngine()

        self._sources = [
            TimeSource(config),
            LocationSource(config),
            WeatherSource(config),
            DeviceSource(config, memory),
        ]

    async def start(self, interval: int = 30):
        self._running = True
        logger.info("Context engine starting...")
        while self._running:
            try:
                await self.update()
            except Exception as e:
                logger.error(f"Context update error: {e}")
            await asyncio.sleep(interval)

    async def stop(self):
        self._running = False

    async def update(self) -> UserContext:
        ctx = UserContext(timestamp=time.time())

        for source in self._sources:
            try:
                await source.apply(ctx)
            except Exception as e:
                logger.error(f"Source {source.__class__.__name__} error: {e}")

        # Infer mood from context
        ctx.inferred_mood = self._infer_mood(ctx)
        ctx.focus_score = self._calc_focus_score(ctx)

        self.current = ctx

        # Record for pattern learning + persist
        ctx_dict = ctx.to_dict()
        try:
            self.patterns.record(ctx_dict)
            store_context_snapshot(ctx_dict)
        except Exception as e:
            logger.error(f"Pattern/persistence error: {e}")

        return ctx

    def _infer_mood(self, ctx: UserContext) -> str:
        # Simple rule-based mood inference
        if ctx.current_app in ("Xcode", "VS Code", "Terminal", "Cursor", "Claude"):
            if ctx.app_duration_minutes > 10:
                return "focused"

        if ctx.activity_level == "exercising":
            return "energetic"

        if ctx.hour >= 22 or ctx.hour <= 5:
            return "winding_down"

        if ctx.is_weekend and ctx.activity_level == "sedentary":
            return "relaxed"

        if ctx.unread_messages > 10 or ctx.missed_calls > 2:
            return "busy"

        return "neutral"

    def _calc_focus_score(self, ctx: UserContext) -> float:
        score = 0.5
        coding_apps = {"Xcode", "VS Code", "Terminal", "Cursor", "Claude", "Gemini"}
        if ctx.current_app in coding_apps:
            score += 0.2
        if ctx.app_duration_minutes > 30:
            score += 0.1
        if ctx.unread_messages == 0:
            score += 0.1
        if ctx.time_of_day in ("morning", "late_night"):
            score += 0.05
        return min(score, 1.0)

    def get_context(self) -> UserContext:
        return self.current

    def get_context_dict(self) -> dict:
        return self.current.to_dict()
