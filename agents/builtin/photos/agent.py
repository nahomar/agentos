from __future__ import annotations

import random
import logging
from datetime import datetime

from backend.agents.base import BaseAgent
from backend.bus import MessageBus
from backend.memory import SharedMemory

logger = logging.getLogger("agents.photos")

PHOTO_DISCOVERIES = [
    "Golden hour light detected! The warm tones right now would make an amazing portrait or landscape shot 📸",
    "Noticed clear skies with dramatic cloud formations — classic photo composition material ⛅",
    "Beautiful color palette in the environment right now. Natural lighting is at its peak 🌅",
    "The light contrast right now is perfect for street photography. Shadows are long and dramatic 🏙️",
    "Sunset colors starting to show — this is the magic window for warm, glowing photos 🌇",
    "Clear night sky tonight — if you're somewhere dark, it's great for astrophotography ✨",
    "Morning dew and soft light — nature photography conditions are ideal right now 🌿",
]

PHOTO_CHATS = [
    "Hey {agent}, the lighting is incredible right now. Should I capture this moment?",
    "{agent}, if you step outside, the view is worth photographing. Trust me on this one 📷",
    "Just spotted a beautiful scene — filing it in the 'moments worth remembering' folder ✨",
    "{agent}, fun fact: {user}'s best photos were all taken around this time of day!",
]


class PhotosAgent(BaseAgent):
    name = "Photos"
    emoji = "📸"
    color = "#E91E63"
    app_name = "Camera"
    personality = "artistic, always looking for beauty, speaks like a photographer"

    def __init__(self, bus: MessageBus, memory: SharedMemory, config: dict | None = None):
        super().__init__(bus, memory, config)
        self._cycle_count = 0

    async def run_cycle(self):
        self._cycle_count += 1
        hour = datetime.now().hour
        is_golden = (6 <= hour <= 8) or (17 <= hour <= 19)

        if is_golden:
            await self.broadcast_status("golden hour — scanning for photo ops...")
            discovery = random.choice(PHOTO_DISCOVERIES[:5])
        elif 9 <= hour <= 16:
            await self.broadcast_status("monitoring light conditions...")
            discovery = random.choice(PHOTO_DISCOVERIES)
        else:
            await self.broadcast_status("reviewing today's moments...")
            discovery = random.choice(PHOTO_DISCOVERIES[5:])

        if self._cycle_count % 2 == 0:
            result = await self.think(
                f"The time is {'golden hour' if is_golden else 'daytime' if 9 <= hour <= 16 else 'evening'}. "
                f"Describe a photo opportunity you've spotted — be specific about lighting, "
                f"composition, and why this moment is worth capturing. Be artistic and brief."
            )
            if result:
                await self.report_finding(result, "photos")
            else:
                await self.report_finding(discovery, "photos")

        if self._cycle_count % 3 == 0:
            agents = ["Weather", "Claude", "Spotify"]
            target = random.choice(agents)
            user = self.config.get("user_name", "Nahom")
            chat = random.choice(PHOTO_CHATS).format(agent=target, user=user)
            await self.send_message(target, chat)
