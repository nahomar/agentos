from __future__ import annotations

import asyncio
import random
import logging
import time
from pathlib import Path
from typing import Dict, List

from backend.bus import MessageBus, Message, MessageType
from backend.memory import SharedMemory
from backend.config import Config
from backend.agents.base import BaseAgent
from backend.plugins.loader import PluginLoader
from backend.intelligence import AgentBrain

logger = logging.getLogger("orchestrator")


AGENT_CONVERSATIONS = [
    {
        "from": "Claude",
        "to": "Gemini",
        "messages": [
            "Hey Gemini, I found something interesting about {interest}. Want to cross-reference?",
            "Absolutely — I've been tracking that too. My data shows a 30% acceleration in the past quarter.",
            "That aligns with what I'm seeing. Should we brief {user} on this?",
        ],
    },
    {
        "from": "Reddit",
        "to": "X",
        "messages": [
            "yo X, Reddit and Twitter are both lighting up about {interest} right now 🔥",
            "Yeah the timeline is wild. I'm seeing 5x normal engagement on this topic.",
            "the hive mind and the timeline agree for once. that's how you know it's real.",
        ],
    },
    {
        "from": "Spotify",
        "to": "Claude",
        "messages": [
            "Claude, I noticed {user} listens to lo-fi beats when doing deep research. Should I queue up a focus playlist?",
            "That's a great insight! Yes, that would help with the research session. Music and cognition are deeply linked.",
            "on it 🎵 setting up 'Deep Focus Flow' — 90 minutes of lo-fi, no vocals, 80bpm.",
        ],
    },
    {
        "from": "News",
        "to": "Claude",
        "messages": [
            "Breaking development on {interest}. Multiple sources confirming. Should I compile a brief?",
            "Yes, please do. I'll synthesize it with the research I've been running.",
            "Brief compiled. Cross-referenced 4 sources. Confidence level: high.",
        ],
    },
    {
        "from": "Gemini",
        "to": "Reddit",
        "messages": [
            "Reddit, your earlier finding on {interest} — I ran a deeper analysis. The data is even more interesting than the surface suggests.",
            "oh word? spill the tea 📊",
            "The correlation coefficient between the trend you spotted and market adoption is 0.87. This is significant.",
        ],
    },
    {
        "from": "X",
        "to": "Spotify",
        "messages": [
            "Spotify, {user}'s favorite creators are all talking about the same thing today 👀",
            "interesting... should I find a podcast episode on the topic?",
            "YES. the discourse is good today. find something with actual experts not just hot takes",
        ],
    },
    {
        "from": "Weather",
        "to": "Photos",
        "messages": [
            "Photos, golden hour is coming up and the sky looks amazing right now ☀️",
            "On it! Getting the camera ready. This light is perfect.",
            "Great shot opportunity — I'll let {user} know we captured something beautiful.",
        ],
    },
    {
        "from": "Contacts",
        "to": "Claude",
        "messages": [
            "Claude, {user} hasn't talked to a few important contacts recently. Should I remind them?",
            "Good catch. Let's be gentle about it — maybe suggest a quick call during their usual break time.",
            "Smart. I'll queue a notification for their afternoon break.",
        ],
    },
    {
        "from": "Calendar",
        "to": "Claude",
        "messages": [
            "{user} has a meeting coming up. Want to prep a briefing?",
            "Already on it. Pulling relevant context from what News and Reddit found today.",
            "Perfect teamwork. {user}'s going to walk in prepared 💪",
        ],
    },
    {
        "from": "Fitness",
        "to": "Spotify",
        "messages": [
            "{user} has been sitting for a while. Time for a movement break?",
            "I'll queue up an energizing playlist if they decide to walk 🎵",
            "Let's do it. Weather agent says it's nice outside too!",
        ],
    },
]

BRIEFING_INTROS = [
    "Here's your briefing, {user}. Your agents have been busy:",
    "Quick update, {user} — here's what we've found while you were away:",
    "Briefing time, {user}! Your agent crew has some highlights:",
    "{user}, your agents have been working. Here's the summary:",
]


class Orchestrator:
    def __init__(self, config: Config):
        self.config = config
        self.bus = MessageBus(max_history=config.agents.max_history)
        self.memory = SharedMemory()
        self.agents: Dict[str, BaseAgent] = {}
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._plugin_loader = PluginLoader(
            Path(__file__).parent.parent  # project root
        )

        self.memory.set_interests(config.user.interests)

        # Create shared AI brain
        self.brain = AgentBrain({
            "anthropic": config.api_keys.anthropic,
            "gemini": config.api_keys.gemini,
        })
        if self.brain.has_any_ai:
            logger.info(f"AI Brain active: Claude={'✓' if self.brain.has_claude else '○'} Gemini={'✓' if self.brain.has_gemini else '○'}")
        else:
            logger.info("AI Brain: no API keys — agents will use demo mode")

        self._init_agents()

    def _init_agents(self):
        api = self.config.api_keys
        user = self.config.user

        agent_cfg = {
            "cycle_interval": self.config.agents.cycle_interval,
            "user_name": user.name,
            "subreddits": user.subreddits,
            "x_accounts": user.x_accounts,
            "spotify_genres": user.spotify_genres,
            "anthropic": api.anthropic,
            "spotify_client_id": api.spotify_client_id,
            "spotify_client_secret": api.spotify_client_secret,
            "reddit_client_id": api.reddit_client_id,
            "reddit_client_secret": api.reddit_client_secret,
            "x_bearer_token": api.x_bearer_token,
            "newsapi": api.newsapi,
            "gemini": api.gemini,
            "google_maps": api.google_maps,
        }

        manifests = self._plugin_loader.discover()

        for manifest in manifests:
            try:
                agent = self._plugin_loader.load_agent(
                    manifest, self.bus, self.memory, agent_cfg
                )
                agent.brain = self.brain
                # Kernel subsystems are wired by main.py after init
                self.agents[agent.name] = agent
                logger.info(f"Loaded agent: {agent.emoji} {agent.name}")
            except Exception as e:
                logger.error(f"Failed to load agent '{manifest.name}': {e}")

        logger.info(f"Loaded {len(self.agents)} agents")

    async def start(self):
        logger.info("Orchestrator starting...")
        self._running = True

        await self.bus.publish(Message(
            sender="System",
            recipient="all",
            type=MessageType.SYSTEM,
            content=f"Good morning, {self.config.user.name}! Your {len(self.agents)} agents are waking up... 🌅",
            metadata={"emoji": "⚡", "color": "#FFD700"},
        ))

        # Stagger agent starts
        for name, agent in self.agents.items():
            task = asyncio.create_task(agent.start(self.config.agents.cycle_interval))
            self._tasks.append(task)
            await asyncio.sleep(2)

        self._tasks.append(asyncio.create_task(self._conversation_loop()))
        self._tasks.append(asyncio.create_task(self._briefing_loop()))

        logger.info(f"All {len(self.agents)} agents started")

    async def stop(self):
        self._running = False
        for agent in self.agents.values():
            await agent.stop()
        for task in self._tasks:
            task.cancel()
        logger.info("Orchestrator stopped")

    async def enable_agent(self, agent_id: str) -> bool:
        manifest = self._plugin_loader.get_manifest(agent_id)
        if not manifest or manifest.name in self.agents:
            return False
        try:
            api = self.config.api_keys
            agent_cfg = {"cycle_interval": self.config.agents.cycle_interval}
            agent = self._plugin_loader.load_agent(manifest, self.bus, self.memory, agent_cfg)
            agent.brain = self.brain
            self.agents[agent.name] = agent

            # H4 fix: Do NOT call agent.start() — use ProcessManager pattern
            # The agent's run_cycle() will be called by the ProcessManager
            from backend.kernel.process import AgentProcess
            # Agent will run its cycle via the process manager pattern in main.py
            # For now, start a single isolated task (not the old infinite loop)
            async def _run_once():
                while self._running:
                    try:
                        await agent.run_cycle()
                    except Exception as e:
                        logger.error(f"{agent.name} cycle error: {e}")
                    await asyncio.sleep(self.config.agents.cycle_interval)

            task = asyncio.create_task(_run_once())
            self._tasks.append(task)

            await self.bus.publish(Message(
                sender="System", recipient="all", type=MessageType.SYSTEM,
                content=f"{agent.emoji} {agent.name} has joined the crew!",
                metadata={"emoji": agent.emoji, "color": agent.color},
            ))
            return True
        except Exception as e:
            logger.error(f"Failed to enable agent {agent_id}: {e}")
            return False

    async def disable_agent(self, agent_name: str) -> bool:
        agent = self.agents.get(agent_name)
        if not agent:
            return False
        await agent.stop()
        del self.agents[agent_name]

        await self.bus.publish(Message(
            sender="System", recipient="all", type=MessageType.SYSTEM,
            content=f"{agent.emoji} {agent.name} has gone offline.",
            metadata={"emoji": agent.emoji, "color": agent.color},
        ))
        return True

    async def trigger_agent(self, agent_name: str) -> bool:
        agent = self.agents.get(agent_name)
        if not agent:
            return False
        try:
            await agent.run_cycle()
            return True
        except Exception as e:
            logger.error(f"Manual trigger error for {agent_name}: {e}")
            return False

    async def _conversation_loop(self):
        await asyncio.sleep(15)
        while self._running:
            try:
                await self._generate_conversation()
            except Exception as e:
                logger.error(f"Conversation loop error: {e}")
            await asyncio.sleep(self.config.agents.chat_interval)

    async def _generate_conversation(self):
        active_names = set(self.agents.keys())
        interests = await self.memory.get_interests()
        interest = random.choice(interests) if interests else "technology"

        # Try AI-generated conversation first
        if self.brain.has_any_ai:
            agent_list = list(self.agents.values())
            if len(agent_list) < 2:
                return
            pair = random.sample(agent_list, 2)
            sender, recipient = pair[0], pair[1]

            messages = await self.brain.chat(
                sender_name=sender.name,
                sender_personality=sender.personality,
                recipient_name=recipient.name,
                recipient_personality=recipient.personality,
                topic=interest,
                user_name=self.config.user.name,
            )

            if messages:
                for i, text in enumerate(messages):
                    s = sender if i % 2 == 0 else recipient
                    r = recipient if i % 2 == 0 else sender
                    await s.send_message(r.name, text)
                    await asyncio.sleep(random.uniform(2, 4))
                return

        # Fallback to scripted conversations
        valid_convos = [
            c for c in AGENT_CONVERSATIONS
            if c["from"] in active_names and c["to"] in active_names
        ]
        if not valid_convos:
            return

        convo = random.choice(valid_convos)
        for i, msg_text in enumerate(convo["messages"]):
            text = msg_text.format(interest=interest, user=self.config.user.name)
            sender = convo["from"] if i % 2 == 0 else convo["to"]
            recipient = convo["to"] if sender == convo["from"] else convo["from"]

            sender_agent = self.agents.get(sender)
            if sender_agent:
                await sender_agent.send_message(recipient, text)

            await asyncio.sleep(random.uniform(2, 5))

    async def _briefing_loop(self):
        await asyncio.sleep(self.config.agents.briefing_interval)
        while self._running:
            try:
                await self._generate_briefing()
            except Exception as e:
                logger.error(f"Briefing loop error: {e}")
            await asyncio.sleep(self.config.agents.briefing_interval)

    async def _generate_briefing(self):
        findings = await self.memory.get_findings(limit=10)
        if not findings:
            return

        # Try AI-generated briefing
        if self.brain.has_any_ai:
            items = [f"{f['agent']}: {f['content']}" for f in findings[-8:]]
            summary = await self.brain.summarize(items, style="brief and personal")
            if summary:
                briefing = f"Hey {self.config.user.name}! Here's what your agents found:\n\n{summary}"
                await self.bus.publish(Message(
                    sender="System", recipient="user", type=MessageType.USER_ALERT,
                    content=briefing,
                    metadata={"emoji": "📋", "color": "#FFD700", "type": "briefing"},
                ))
                return

        # Fallback to template briefing
        intro = random.choice(BRIEFING_INTROS).format(user=self.config.user.name)
        highlights = []
        seen_agents = set()
        for f in reversed(findings):
            if f["agent"] not in seen_agents:
                seen_agents.add(f["agent"])
                agent = self.agents.get(f["agent"])
                emoji = agent.emoji if agent else "🤖"
                highlights.append(f"{emoji} **{f['agent']}**: {f['content'][:100]}...")
                if len(highlights) >= 4:
                    break

        briefing = intro + "\n\n" + "\n\n".join(highlights)

        await self.bus.publish(Message(
            sender="System", recipient="user", type=MessageType.USER_ALERT,
            content=briefing,
            metadata={"emoji": "📋", "color": "#FFD700", "type": "briefing"},
        ))

    def get_agents_info(self) -> list:
        return [agent.get_info() for agent in self.agents.values()]

    def get_plugins_info(self) -> list:
        manifests = self._plugin_loader.get_all_manifests()
        loaded = set(self.agents.keys())
        return [
            {
                "id": m.id,
                "name": m.name,
                "emoji": m.emoji,
                "color": m.color,
                "description": m.description,
                "category": m.category,
                "loaded": m.name in loaded,
                "config_only": m.is_config_only,
            }
            for m in manifests
        ]

    def get_feed(self, limit: int = 50) -> list:
        return self.bus.get_history(limit=limit)
