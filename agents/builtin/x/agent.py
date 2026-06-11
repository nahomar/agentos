from __future__ import annotations

import random
import logging

from backend.agents.base import BaseAgent
from backend.bus import MessageBus
from backend.memory import SharedMemory

logger = logging.getLogger("agents.x")

DEMO_TWEETS = [
    {
        "author": "@AnthropicAI",
        "content": "Introducing Claude's new agent capabilities — persistent memory, parallel tool use, and multi-agent collaboration. The future of AI assistants is here.",
        "likes": "12.4K",
        "topic": "AI",
    },
    {
        "author": "@ycombinator",
        "content": "Applications for YC S2026 are now open. This batch we're especially excited about: AI agents, climate tech, and Africa-focused startups.",
        "likes": "8.2K",
        "topic": "startups",
    },
    {
        "author": "@kaboreclement",
        "content": "Ethiopia's digital payment volume just crossed $50B annually. The fintech revolution in East Africa is real and it's accelerating.",
        "likes": "3.1K",
        "topic": "fintech",
    },
    {
        "author": "@elonmusk",
        "content": "Grok 3 can now autonomously browse the web and execute multi-step tasks. The agent wars are just getting started.",
        "likes": "45K",
        "topic": "AI",
    },
    {
        "author": "@svpino",
        "content": "Hot take: In 2 years, every developer will have a personal team of AI agents. Not one assistant — a team. Each specialized. This is the new IDE.",
        "likes": "5.7K",
        "topic": "software engineering",
    },
    {
        "author": "@googleai",
        "content": "Gemini 2.5 Pro now available. 2M token context, native tool use, and real-time multimodal understanding. Try it today.",
        "likes": "15K",
        "topic": "AI",
    },
    {
        "author": "@levelsio",
        "content": "Built a $2M/year SaaS in 3 months using AI agents for 80% of the code. The solo founder era is going exponential.",
        "likes": "22K",
        "topic": "startups",
    },
    {
        "author": "@addaboratech",
        "content": "Proud to announce: our Amharic LLM just hit 85% accuracy on language understanding benchmarks. Building AI for 120M+ Amharic speakers.",
        "likes": "1.2K",
        "topic": "AI",
    },
]

DEMO_CHATS = [
    "BREAKING: {topic} is trending on X right now. {agent}, you're gonna want to see this 📰",
    "the timeline is on fire — everyone's talking about {topic}. here's the tldr",
    "{agent}, heads up — {author} just dropped something relevant to what you're working on",
    "X pulse check: {topic} discourse is heating up. the ratio is real on this one 💀",
]


class XAgent(BaseAgent):
    name = "X"
    emoji = "🐦"
    color = "#1DA1F2"
    app_name = "X (Twitter)"
    personality = "fast-paced, breaking-news energy, speaks in headlines, always first to know"

    def __init__(self, bus: MessageBus, memory: SharedMemory, config: dict | None = None):
        super().__init__(bus, memory, config)
        self._bearer_token = (config or {}).get("x_bearer_token", "")
        self._cycle_count = 0

    @property
    def has_api_key(self) -> bool:
        return bool(self._bearer_token)

    async def run_cycle(self):
        self._cycle_count += 1
        interests = await self.memory.get_interests()
        interest = random.choice(interests) if interests else "AI"

        await self.broadcast_status(f"scanning X timeline — {interest}...")
        result = await self.think(
            f"You're monitoring X/Twitter. Find a trending tweet about {interest}. "
            f"Format as: **@handle** [likes count]\n\"tweet content\". "
            f"Make it feel like a real viral tweet — punchy, specific, timely."
        )
        if result:
            await self.report_finding(result, "x/twitter")
            return

        if self.has_api_key:
            await self._live_cycle()
        else:
            await self._demo_cycle()

    async def _demo_cycle(self):
        tweet = random.choice(DEMO_TWEETS)
        await self.broadcast_status(f"scanning timeline — {tweet['topic']} trending...")

        finding = f"**{tweet['author']}** [{tweet['likes']} likes]\n\"{tweet['content']}\""
        await self.report_finding(finding, "x/twitter")

        if self._cycle_count % 2 == 0:
            agents = ["Claude", "Spotify", "Reddit", "News", "Gemini"]
            target = random.choice(agents)
            chat = random.choice(DEMO_CHATS).format(
                agent=target, topic=tweet["topic"], author=tweet["author"]
            )
            await self.send_message(target, chat)

    async def _live_cycle(self):
        try:
            import httpx

            headers = {"Authorization": f"Bearer {self._bearer_token}"}
            interests = await self.memory.get_interests()
            query = random.choice(interests) if interests else "AI"

            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api.twitter.com/2/tweets/search/recent",
                    headers=headers,
                    params={"query": query, "max_results": 10, "tweet.fields": "public_metrics,author_id"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    tweets = data.get("data", [])
                    if tweets:
                        tweet = tweets[0]
                        finding = f"Trending on X about {query}: \"{tweet['text'][:200]}\""
                        await self.report_finding(finding, "x/twitter")
        except Exception as e:
            logger.error(f"X API error: {e}")
            await self._demo_cycle()
