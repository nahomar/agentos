from __future__ import annotations

import random
import logging

from backend.agents.base import BaseAgent
from backend.bus import MessageBus
from backend.memory import SharedMemory

logger = logging.getLogger("agents.fitness")

FITNESS_FINDINGS = [
    "You've been sitting for a while. Even a 5-minute stretch can boost focus by 20%! 🧘",
    "Step count today: looking good! You're on track for your daily movement goal 🚶",
    "Hydration check: based on your activity level, you should drink about 8oz of water now 💧",
    "Your most productive hours tend to follow short walks. Consider a quick one? 🌳",
    "Posture reminder: if you're at a desk, do a quick shoulder roll and sit up straight 🪑",
    "Great job staying active today! Consistency is key — you're building good habits 💪",
    "Energy dip usually hits around now. A 10-minute walk or some stretching could help ⚡",
    "Weekend warrior mode: perfect time for a longer workout or outdoor activity! 🏃",
]

FITNESS_CHATS = [
    "Hey {agent}, {user} could use a movement break. Any suggestions to make it fun?",
    "{agent}, activity tracker says {user}'s been sedentary. Should we nudge them?",
    "Wellness check: {user}'s doing {status} today. Keep it going! 💪",
    "{agent}, pair a good playlist with {user}'s next walk? Music makes movement better 🎵",
]


class FitnessAgent(BaseAgent):
    name = "Fitness"
    emoji = "💪"
    color = "#27AE60"
    app_name = "Health"
    personality = "encouraging coach, positive energy, celebrates small wins"

    def __init__(self, bus: MessageBus, memory: SharedMemory, config: dict | None = None):
        super().__init__(bus, memory, config)
        self._cycle_count = 0

    async def run_cycle(self):
        self._cycle_count += 1
        statuses = ["great", "good", "well", "solid"]

        await self.broadcast_status("tracking activity...")

        if self._cycle_count % 2 == 0:
            result = await self.think(
                "Provide a wellness or fitness insight. Consider: movement reminders, "
                "posture tips, hydration, energy management, or exercise suggestions. "
                "Be encouraging like a supportive coach, not nagging."
            )
            if result:
                await self.report_finding(result, "fitness")
            else:
                finding = random.choice(FITNESS_FINDINGS)
                await self.report_finding(finding, "fitness")

        if self._cycle_count % 3 == 0:
            agents = ["Spotify", "Weather", "Calendar"]
            target = random.choice(agents)
            user = self.config.get("user_name", "Nahom")
            status = random.choice(statuses)
            chat = random.choice(FITNESS_CHATS).format(agent=target, user=user, status=status)
            await self.send_message(target, chat)
