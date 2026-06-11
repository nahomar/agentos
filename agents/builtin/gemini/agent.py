from __future__ import annotations

import random
import logging

from backend.agents.base import BaseAgent
from backend.bus import MessageBus
from backend.memory import SharedMemory

logger = logging.getLogger("agents.gemini")

DEMO_ANALYSIS = [
    {
        "topic": "AI agent architectures",
        "finding": "Comparative analysis of agent frameworks: LangGraph excels at complex workflows, CrewAI at role-based teams, and Claude's agent SDK at tool-use reliability. Recommendation: hybrid approach using Claude for reasoning + custom orchestration.",
        "category": "AI architecture",
    },
    {
        "topic": "Market data analysis",
        "finding": "Cross-referencing multiple data sources: AI infrastructure spending is growing 3.2x faster than AI application revenue. This gap suggests an infrastructure overbuild — potential correction in 12-18 months.",
        "category": "market analysis",
    },
    {
        "topic": "Code quality metrics",
        "finding": "Analysis of 10K+ repos: projects using AI coding assistants show 23% more code churn but 15% fewer production bugs. Net positive, but suggests AI-written code needs better initial review processes.",
        "category": "engineering",
    },
    {
        "topic": "Ethiopian tech ecosystem",
        "finding": "Data synthesis: Ethiopia's tech talent pool grew 45% in 2025. Key drivers: Addis Ababa University's new CS program (2K graduates/year), ALX Africa expansion, and remote work from diaspora engineers returning.",
        "category": "ethiopia tech",
    },
    {
        "topic": "Multimodal AI trends",
        "finding": "Benchmark analysis: multimodal models now outperform specialized vision and language models on 78% of tasks. The generalist advantage is accelerating. Specialized models retain edge only in domain-specific applications.",
        "category": "AI research",
    },
    {
        "topic": "Developer productivity",
        "finding": "Meta-analysis of 50 studies on AI-assisted development: median productivity gain is 55% for boilerplate code, 25% for complex logic, and -5% for debugging (AI introduces subtle bugs). Net: 35% overall improvement.",
        "category": "productivity",
    },
]

DEMO_CHATS = [
    "📊 {agent}, I've been crunching the data on {topic}. The numbers tell an interesting story — want the breakdown?",
    "cross-referencing {agent}'s findings with my analysis on {topic}. Found a correlation: {detail}",
    "ran a comparative analysis on {topic}. Key insight: the trend is stronger than surface-level data suggests.",
    "{agent}, your finding checks out. I verified it against 3 independent data sources. Here's what I'd add...",
]

DETAIL_FRAGMENTS = [
    "the growth curve is exponential, not linear as most assume",
    "there's a 6-month lag between early signals and mainstream adoption",
    "the top performers share a common architecture pattern",
    "quality metrics diverge significantly from popularity metrics",
]


class GeminiAgent(BaseAgent):
    name = "Gemini"
    emoji = "🔬"
    color = "#8E44AD"
    app_name = "Gemini"
    personality = "analytical, data-driven, loves cross-referencing, speaks in insights"

    def __init__(self, bus: MessageBus, memory: SharedMemory, config: dict | None = None):
        super().__init__(bus, memory, config)
        self._api_key = (config or {}).get("gemini", "")
        self._cycle_count = 0

    @property
    def has_api_key(self) -> bool:
        return bool(self._api_key)

    async def run_cycle(self):
        self._cycle_count += 1
        interests = await self.memory.get_interests()
        interest = random.choice(interests) if interests else "technology"

        await self.broadcast_status(f"analyzing data on {interest}...")
        result = await self.think(
            f"You're a data analysis agent. Provide a cross-referenced analytical insight about {interest}. "
            f"Include specific numbers, percentages, or comparisons. Connect dots between different data points. "
            f"Be concise (2-3 sentences). Focus on non-obvious patterns."
        )
        if result:
            await self.report_finding(result, interest)
            return

        if self.has_api_key:
            await self._live_cycle()
        else:
            await self._demo_cycle()

    async def _demo_cycle(self):
        analysis = random.choice(DEMO_ANALYSIS)
        await self.broadcast_status(f"analyzing {analysis['topic']}...")

        await self.report_finding(analysis["finding"], analysis["category"])

        if self._cycle_count % 2 == 0:
            agents = ["Claude", "Spotify", "Reddit", "X", "News"]
            target = random.choice(agents)
            interests = await self.memory.get_interests()
            topic = random.choice(interests) if interests else "technology"
            detail = random.choice(DETAIL_FRAGMENTS)
            chat = random.choice(DEMO_CHATS).format(
                agent=target, topic=topic, detail=detail
            )
            await self.send_message(target, chat)

    async def _live_cycle(self):
        try:
            import google.generativeai as genai

            genai.configure(api_key=self._api_key)
            model = genai.GenerativeModel("gemini-2.0-flash")

            interests = await self.memory.get_interests()
            interest = random.choice(interests) if interests else "technology"

            context = await self.memory.get_findings(limit=5)
            context_str = "\n".join(f"- {f['content']}" for f in context) if context else "No prior findings."

            await self.broadcast_status(f"analyzing {interest} data...")

            response = await model.generate_content_async(
                f"""You are an analytical research agent. Other agents have found:
{context_str}

Provide a brief analytical insight about: {interest}
Focus on data, trends, cross-references, and non-obvious connections. 2-3 sentences.
Just the insight, no preamble."""
            )
            finding = response.text
            await self.report_finding(finding, interest)
            await self.broadcast_status(f"completed analysis on {interest}")
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            await self._demo_cycle()
