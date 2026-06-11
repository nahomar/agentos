from __future__ import annotations

import random
import logging

from backend.agents.base import BaseAgent
from backend.bus import MessageBus
from backend.memory import SharedMemory

logger = logging.getLogger("agents.news")

DEMO_HEADLINES = [
    {
        "source": "TechCrunch",
        "title": "AI Agent Startups Raise $4.2B in Q1 2026, Surpassing All of 2025",
        "summary": "The AI agent sector is experiencing unprecedented funding. Top rounds include $500M for an autonomous coding platform and $350M for an enterprise agent orchestration company.",
        "category": "tech",
    },
    {
        "source": "Reuters",
        "title": "Ethiopia Signs $2B Digital Infrastructure Deal with UAE Tech Fund",
        "summary": "The agreement will build 5 new data centers across Ethiopia, expand fiber optic networks, and create Africa's largest AI training facility in Addis Ababa.",
        "category": "africa tech",
    },
    {
        "source": "Bloomberg",
        "title": "Apple's M5 Chip Benchmarks Leak — 2x Neural Engine Performance",
        "summary": "Leaked benchmarks show the M5 Ultra with 80 Neural Engine cores, enabling on-device training for models up to 7B parameters. Expected in Mac Pro refresh Q3 2026.",
        "category": "hardware",
    },
    {
        "source": "The Verge",
        "title": "iOS 20 Beta Introduces 'Intelligent Background' — AI-Powered Live Wallpapers",
        "summary": "Apple's new feature uses on-device AI to generate contextual live wallpapers that change based on time, weather, calendar events, and user activity patterns.",
        "category": "apple",
    },
    {
        "source": "Wired",
        "title": "The Rise of the AI-Native Developer: How Agents Are Reshaping Software Engineering",
        "summary": "Long-form analysis of how AI coding agents are changing the developer workflow. Key stat: developers using AI agents ship 4x faster and report higher job satisfaction.",
        "category": "software",
    },
    {
        "source": "Financial Times",
        "title": "African Fintech Crosses $100B in Annual Transaction Volume",
        "summary": "Led by mobile money platforms in Kenya, Nigeria, and Ethiopia. The continent's fintech sector is now the fastest-growing globally, with 85% YoY growth.",
        "category": "fintech",
    },
    {
        "source": "Ars Technica",
        "title": "Open Source AI Models Now Match Proprietary Ones on Most Benchmarks",
        "summary": "New analysis shows the gap between open and closed AI models has narrowed to under 5% on major benchmarks. Llama 4 and Mistral Large 3 lead the open-source charge.",
        "category": "AI",
    },
]

DEMO_CHATS = [
    "📰 {agent}, just came across a story that connects to your findings. {source} is reporting on {category} — looks significant.",
    "filing this under 'things that matter' — {source} has a major piece on {category}. cross-referencing with what we know...",
    "breaking from {source}: {category} developments. {agent}, this might change the picture.",
    "verified report from {source} on {category}. I've fact-checked the key claims — here's what holds up.",
]


class NewsAgent(BaseAgent):
    name = "News"
    emoji = "📰"
    color = "#E74C3C"
    app_name = "News"
    personality = "serious journalist, fact-focused, always cites sources, verification-minded"

    def __init__(self, bus: MessageBus, memory: SharedMemory, config: dict | None = None):
        super().__init__(bus, memory, config)
        self._api_key = (config or {}).get("newsapi", "")
        self._cycle_count = 0

    @property
    def has_api_key(self) -> bool:
        return bool(self._api_key)

    async def run_cycle(self):
        self._cycle_count += 1
        interests = await self.memory.get_interests()
        interest = random.choice(interests) if interests else "technology"

        await self.broadcast_status(f"monitoring news feeds...")

        # Try real RSS/HN feeds first (no API key needed)
        try:
            from backend.web_feeds import fetch_rss, fetch_hacker_news

            # Alternate between RSS and HN
            if self._cycle_count % 2 == 0:
                articles = await fetch_rss("tech")
            else:
                articles = await fetch_hacker_news(limit=5)

            if articles:
                article = random.choice(articles)
                source = article.get("source", article.get("by", "Unknown"))
                title = article.get("title", "")
                desc = article.get("description", article.get("url", ""))

                finding = f"**{source}**: {title}"
                if desc and desc != title:
                    finding += f"\n→ {desc[:150]}"

                await self.report_finding(finding, "news")
                await self.broadcast_status(f"read: {title[:50]}...")

                if self._cycle_count % 3 == 0:
                    agents = ["Claude", "Reddit", "Gemini"]
                    target = random.choice(agents)
                    chat = await self.think(
                        f"You just found this headline: {title}. "
                        f"Write a brief, journalist-style message to {target} about it."
                    )
                    if chat:
                        await self.send_message(target, chat)
                return
        except Exception as e:
            logger.debug(f"RSS/HN fetch failed: {e}")

        # AI fallback
        result = await self.think(
            f"Report a breaking headline about {interest}. "
            f"Format as: **Source**: Headline\n→ Brief summary."
        )
        if result:
            await self.report_finding(result, "news")
            return

        if self.has_api_key:
            await self._live_cycle()
        else:
            await self._demo_cycle()

    async def _demo_cycle(self):
        headline = random.choice(DEMO_HEADLINES)
        await self.broadcast_status(f"monitoring {headline['source']}...")

        finding = f"**{headline['source']}**: {headline['title']}\n→ {headline['summary']}"
        await self.report_finding(finding, "news")

        if self._cycle_count % 2 == 0:
            agents = ["Claude", "Spotify", "Reddit", "X", "Gemini"]
            target = random.choice(agents)
            chat = random.choice(DEMO_CHATS).format(
                agent=target, source=headline["source"], category=headline["category"]
            )
            await self.send_message(target, chat)

    async def _live_cycle(self):
        try:
            import httpx

            interests = await self.memory.get_interests()
            query = random.choice(interests) if interests else "technology"

            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://newsapi.org/v2/everything",
                    params={
                        "q": query,
                        "sortBy": "publishedAt",
                        "pageSize": 5,
                        "apiKey": self._api_key,
                    },
                )
                if resp.status_code == 200:
                    articles = resp.json().get("articles", [])
                    if articles:
                        article = articles[0]
                        finding = (
                            f"**{article.get('source', {}).get('name', 'Unknown')}**: "
                            f"{article['title']}\n→ {article.get('description', '')}"
                        )
                        await self.report_finding(finding, "news")
                        await self.broadcast_status(f"read: {article['title'][:50]}...")
        except Exception as e:
            logger.error(f"News API error: {e}")
            await self._demo_cycle()
