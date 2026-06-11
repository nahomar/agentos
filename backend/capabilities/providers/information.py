from __future__ import annotations

import time
import logging
from datetime import datetime
from backend.capabilities.registry import CapabilityProvider, CapabilityResult

logger = logging.getLogger("capabilities.information")


class WeatherProvider(CapabilityProvider):
    id = "info.weather"
    name = "Weather"
    description = "Get current weather conditions"
    category = "information"

    @property
    def available(self) -> bool:
        return True  # Has demo fallback

    async def execute(self, params: dict) -> CapabilityResult:
        lat = params.get("lat")
        lon = params.get("lon")
        api_key = self.config.get("openweathermap_key", "")

        if api_key and lat and lon:
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        "https://api.openweathermap.org/data/2.5/weather",
                        params={"lat": lat, "lon": lon, "appid": api_key, "units": "imperial"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        return CapabilityResult(success=True, data={
                            "temperature_f": data["main"]["temp"],
                            "feels_like_f": data["main"]["feels_like"],
                            "humidity": data["main"]["humidity"],
                            "condition": data["weather"][0]["main"].lower(),
                            "description": data["weather"][0]["description"],
                            "wind_mph": data["wind"]["speed"],
                            "city": data.get("name", ""),
                        })
            except Exception as e:
                logger.error(f"Weather API error: {e}")

        # Demo data
        hour = datetime.now().hour
        if 6 <= hour <= 18:
            return CapabilityResult(success=True, data={
                "temperature_f": 72,
                "feels_like_f": 74,
                "humidity": 45,
                "condition": "clear",
                "description": "clear sky",
                "wind_mph": 5,
                "city": "Demo City",
                "demo": True,
            })
        else:
            return CapabilityResult(success=True, data={
                "temperature_f": 58,
                "feels_like_f": 55,
                "humidity": 60,
                "condition": "clear",
                "description": "clear night",
                "wind_mph": 3,
                "city": "Demo City",
                "demo": True,
            })


class LocationProvider(CapabilityProvider):
    id = "info.location"
    name = "Location"
    description = "Get user's current location"
    category = "information"

    @property
    def available(self) -> bool:
        return True

    async def execute(self, params: dict) -> CapabilityResult:
        # Try to get from device-reported context first
        lat = params.get("lat")
        lon = params.get("lon")

        if lat and lon:
            return CapabilityResult(success=True, data={
                "lat": lat, "lon": lon, "source": "device",
            })

        # IP-based geolocation fallback
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get("https://ipapi.co/json/", timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    return CapabilityResult(success=True, data={
                        "lat": data.get("latitude"),
                        "lon": data.get("longitude"),
                        "city": data.get("city", ""),
                        "region": data.get("region", ""),
                        "country": data.get("country_name", ""),
                        "source": "ip",
                    })
        except Exception:
            pass

        return CapabilityResult(success=True, data={
            "lat": 9.0192, "lon": 38.7525, "city": "Addis Ababa",
            "source": "default", "demo": True,
        })


class TimeProvider(CapabilityProvider):
    id = "info.time"
    name = "Time Context"
    description = "Get current time context"
    category = "information"

    @property
    def available(self) -> bool:
        return True

    async def execute(self, params: dict) -> CapabilityResult:
        now = datetime.now()
        hour = now.hour

        if 5 <= hour < 9:
            period = "early_morning"
        elif 9 <= hour < 12:
            period = "morning"
        elif 12 <= hour < 14:
            period = "midday"
        elif 14 <= hour < 17:
            period = "afternoon"
        elif 17 <= hour < 20:
            period = "evening"
        elif 20 <= hour < 23:
            period = "night"
        else:
            period = "late_night"

        # Golden hours
        is_golden_hour = (6 <= hour <= 8) or (17 <= hour <= 19)

        return CapabilityResult(success=True, data={
            "hour": hour,
            "minute": now.minute,
            "period": period,
            "day_of_week": now.strftime("%A").lower(),
            "is_weekend": now.weekday() >= 5,
            "is_golden_hour": is_golden_hour,
            "timestamp": time.time(),
            "date": now.strftime("%Y-%m-%d"),
        })
