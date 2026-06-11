from __future__ import annotations

import random
import logging
from datetime import datetime

from backend.agents.base import BaseAgent
from backend.bus import MessageBus
from backend.memory import SharedMemory

logger = logging.getLogger("agents.weather")

WEATHER_FACTS = [
    {"condition": "clear", "finding": "Clear skies today — UV index is moderate. Great day for outdoor activities! ☀️", "category": "weather"},
    {"condition": "clear", "finding": "Beautiful clear weather. Golden hour will be stunning today — perfect for photos 📸", "category": "weather"},
    {"condition": "cloudy", "finding": "Overcast skies but mild temps. Good day for a café or indoor creative work ☁️", "category": "weather"},
    {"condition": "rain", "finding": "Rain expected — perfect indoor productivity day. Grab some tea and focus time 🌧️", "category": "weather"},
    {"condition": "sunny", "finding": "Warm and sunny! If you've been indoors a while, a 15-min walk would recharge you 🌞", "category": "weather"},
]

WEATHER_CHATS = [
    "Hey {agent}, the weather's {condition} right now — {temp}°F. {suggestion}",
    "{agent}, weather update: it's {condition} and {temp}°F outside. {suggestion}",
    "Just checked the forecast — {condition} skies, {temp}°F. {suggestion}",
]

SUGGESTIONS = {
    "clear": ["Perfect for a walk!", "Great light for photos.", "Nice day to work outside."],
    "cloudy": ["Cozy indoor day.", "Good focus weather.", "Mild and comfortable."],
    "rain": ["Stay dry! Indoor day.", "Rainy vibes — time for lo-fi beats.", "Perfect reading weather."],
}


class WeatherAgent(BaseAgent):
    name = "Weather"
    emoji = "⛅"
    color = "#3498DB"
    app_name = "Weather"
    personality = "warm and observant, speaks like a nature-loving meteorologist"

    def __init__(self, bus: MessageBus, memory: SharedMemory, config: dict | None = None):
        super().__init__(bus, memory, config)
        self._cycle_count = 0

    async def run_cycle(self):
        self._cycle_count += 1

        hour = datetime.now().hour
        if 6 <= hour <= 18:
            condition = random.choice(["clear", "clear", "sunny", "cloudy"])
            temp = random.randint(65, 85)
        else:
            condition = "clear"
            temp = random.randint(55, 68)

        await self.broadcast_status(f"{condition}, {temp}°F")

        result = await self.think(
            f"Current weather: {condition}, {temp}°F. "
            f"Give a brief, personalized weather insight — suggest an activity, "
            f"mention how it affects productivity or mood, or note a photo opportunity. "
            f"Be warm and conversational."
        )
        if result:
            await self.report_finding(result, "weather")
        else:
            fact = random.choice(WEATHER_FACTS)
            await self.report_finding(fact["finding"], "weather")

        if self._cycle_count % 3 == 0:
            agents = ["Claude", "Spotify", "Fitness", "Photos"]
            target = random.choice(agents)
            suggestions = SUGGESTIONS.get(condition, ["Nice out!"])
            chat = random.choice(WEATHER_CHATS).format(
                agent=target, condition=condition, temp=temp,
                suggestion=random.choice(suggestions)
            )
            await self.send_message(target, chat)
