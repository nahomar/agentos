from __future__ import annotations

import random
import logging

from backend.agents.base import BaseAgent
from backend.bus import MessageBus
from backend.memory import SharedMemory

logger = logging.getLogger("agents.contacts")

CONTACT_FINDINGS = [
    "You haven't called Mom in a few days. A quick 5-minute call would make her day 📞",
    "Your friend group chat has been active — might be worth catching up with them!",
    "Noticed you read a message from your colleague but didn't reply. Want me to remind you later?",
    "It's been a while since you connected with your close friends. How about a group hangout?",
    "Birthday coming up for someone in your contacts next week — might want to plan something 🎂",
    "You usually call home on weekends. It's a good time now if you're free 🏠",
    "Your team lead sent a message earlier. Looks like it might need a response by end of day.",
    "Quick reminder: you mentioned wanting to reach out to your mentor this week.",
]

CONTACT_CHATS = [
    "Hey {agent}, {user} has been pretty focused lately. Should we remind them to check in with family?",
    "{agent}, noticed some unread messages piling up. Should I prioritize the important ones?",
    "Social connection check: {user} might benefit from a break to call a friend 📱",
    "{agent}, {user}'s communication patterns show they're due for a catch-up with close contacts.",
]


class ContactsAgent(BaseAgent):
    name = "Contacts"
    emoji = "👥"
    color = "#2ECC71"
    app_name = "Contacts"
    personality = "caring, socially aware, reminds you to stay connected"

    def __init__(self, bus: MessageBus, memory: SharedMemory, config: dict | None = None):
        super().__init__(bus, memory, config)
        self._cycle_count = 0

    async def run_cycle(self):
        self._cycle_count += 1
        await self.broadcast_status("checking communication patterns...")

        if self._cycle_count % 2 == 0:
            result = await self.think(
                "Check communication patterns. Suggest who the user should reach out to, "
                "remind about unreplied messages, or note relationship maintenance tips. "
                "Be caring and specific — mention types of contacts (family, friends, colleagues)."
            )
            if result:
                await self.report_finding(result, "contacts")
            else:
                finding = random.choice(CONTACT_FINDINGS)
                await self.report_finding(finding, "contacts")

        if self._cycle_count % 3 == 0:
            agents = ["Claude", "Spotify", "Calendar"]
            target = random.choice(agents)
            user = self.config.get("user_name", "Nahom")
            chat = random.choice(CONTACT_CHATS).format(agent=target, user=user)
            await self.send_message(target, chat)

        await self.broadcast_status("monitoring communication")
