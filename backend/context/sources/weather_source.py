from __future__ import annotations

import logging
import time
from backend.context.models import UserContext, WeatherData

logger = logging.getLogger("context.weather")


class WeatherSource:
    def __init__(self, config: dict):
        self.config = config
        self._cache = None
        self._cache_time = 0
        self._cache_ttl = 600  # 10 minutes

    async def apply(self, ctx: UserContext):
        if not ctx.location:
            ctx.weather = self._demo_weather(ctx.hour)
            return

        now = time.time()
        if self._cache and (now - self._cache_time) < self._cache_ttl:
            ctx.weather = self._cache
            return

        api_key = self.config.get("openweathermap_key", "")
        if not api_key:
            ctx.weather = self._demo_weather(ctx.hour)
            return

        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api.openweathermap.org/data/2.5/weather",
                    params={
                        "lat": ctx.location.lat,
                        "lon": ctx.location.lon,
                        "appid": api_key,
                        "units": "imperial",
                    },
                    timeout=5,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    ctx.weather = WeatherData(
                        temperature_f=data["main"]["temp"],
                        feels_like_f=data["main"]["feels_like"],
                        humidity=data["main"]["humidity"],
                        condition=data["weather"][0]["main"].lower(),
                        description=data["weather"][0]["description"],
                        wind_mph=data["wind"]["speed"],
                        city=data.get("name", ""),
                    )
                    self._cache = ctx.weather
                    self._cache_time = now
                    return
        except Exception as e:
            logger.error(f"Weather fetch error: {e}")

        ctx.weather = self._demo_weather(ctx.hour)

    def _demo_weather(self, hour: int) -> WeatherData:
        if 6 <= hour <= 18:
            return WeatherData(
                temperature_f=72, feels_like_f=74, humidity=45,
                condition="clear", description="clear sky",
                wind_mph=5, city="Demo City",
            )
        else:
            return WeatherData(
                temperature_f=58, feels_like_f=55, humidity=60,
                condition="clear", description="clear night",
                wind_mph=3, city="Demo City",
            )
