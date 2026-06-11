from __future__ import annotations

import random
import logging
from datetime import datetime

from backend.agents.base import BaseAgent
from backend.bus import MessageBus
from backend.memory import SharedMemory

logger = logging.getLogger("agents.calendar")

CALENDAR_FINDINGS = [
    "Your next focus block starts in 30 minutes. Wrapping up current tasks now would help the transition 📋",
    "No meetings for the next 3 hours — this is your golden window for deep work 🎯",
    "Weekly review is coming up. I've compiled key highlights from your agents to prep you 📊",
    "Tomorrow looks packed — 4 meetings back-to-back. Consider prepping tonight or blocking buffer time ⏰",
    "You have a free afternoon today. Great time for that side project or learning session 💡",
    "Reminder: your 1:1 is in 45 minutes. Want me to pull up recent team updates for context?",
    "End of day approaching — good time to review what was accomplished and plan tomorrow 📝",
    "Weekend is coming up with a clear schedule. Perfect time for the projects you've been postponing!",
]

CALENDAR_CHATS = [
    "Hey {agent}, {user} has a meeting soon. Can you help prep some context?",
    "{agent}, schedule check — {user} has a clear block coming up. Good time for deep work.",
    "Heads up {agent}: busy day ahead for {user}. Let's prioritize notifications accordingly.",
    "{agent}, {user}'s schedule just opened up. Want to suggest something productive?",
]


class CalendarAgent(BaseAgent):
    name = "Calendar"
    emoji = "📅"
    color = "#F39C12"
    app_name = "Calendar"
    personality = "organized, proactive, always thinking ahead"

    def __init__(self, bus: MessageBus, memory: SharedMemory, config: dict | None = None):
        super().__init__(bus, memory, config)
        self._cycle_count = 0

    async def run_cycle(self):
        self._cycle_count += 1
        hour = datetime.now().hour

        if 8 <= hour <= 9:
            await self.broadcast_status("preparing daily briefing...")
        elif 17 <= hour <= 18:
            await self.broadcast_status("end-of-day review...")
        else:
            await self.broadcast_status("monitoring schedule...")

        if self._cycle_count % 2 == 0:
            hour = datetime.now().hour
            result = await self.think(
                f"It's {hour}:00. Provide a schedule-aware productivity insight. "
                f"Consider: upcoming meetings, focus blocks, end-of-day reviews, "
                f"or preparation reminders. Be proactive and actionable."
            )
            if result:
                await self.report_finding(result, "calendar")
            else:
                finding = random.choice(CALENDAR_FINDINGS)
                await self.report_finding(finding, "calendar")

        if self._cycle_count % 3 == 0:
            agents = ["Claude", "News", "Contacts"]
            target = random.choice(agents)
            user = self.config.get("user_name", "Nahom")
            chat = random.choice(CALENDAR_CHATS).format(agent=target, user=user)
            await self.send_message(target, chat)
