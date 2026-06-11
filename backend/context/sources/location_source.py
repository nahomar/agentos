from __future__ import annotations

import logging
import time
from backend.context.models import UserContext, Location

logger = logging.getLogger("context.location")


class LocationSource:
    def __init__(self, config: dict):
        self.config = config
        self._cache = None
        self._cache_time = 0
        self._cache_ttl = 300  # 5 minutes

    async def apply(self, ctx: UserContext):
        now = time.time()

        # Use cached location if fresh
        if self._cache and (now - self._cache_time) < self._cache_ttl:
            ctx.location = self._cache
            return

        # Try IP-based geolocation
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get("https://ipapi.co/json/", timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    ctx.location = Location(
                        lat=data.get("latitude", 0),
                        lon=data.get("longitude", 0),
                        city=data.get("city", ""),
                        region=data.get("region", ""),
                        country=data.get("country_name", ""),
                    )
                    self._cache = ctx.location
                    self._cache_time = now
                    return
        except Exception as e:
            logger.debug(f"IP geolocation error: {e}")

        # Default fallback
        ctx.location = Location(
            lat=9.0192, lon=38.7525, city="Addis Ababa",
            country="Ethiopia",
        )

    def update_from_device(self, lat: float, lon: float, city: str = ""):
        """Called when the mobile app reports location."""
        self._cache = Location(lat=lat, lon=lon, city=city, location_type="device")
        self._cache_time = time.time()
