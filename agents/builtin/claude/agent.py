from __future__ import annotations

import random
import logging

from backend.agents.base import BaseAgent
from backend.bus import MessageBus
from backend.memory import SharedMemory

logger = logging.getLogger("agents.claude")

DEMO_RESEARCH = [
    {
        "topic": "Latest AI breakthroughs",
        "finding": "New paper on Constitutional AI shows 40% improvement in safety benchmarks while maintaining helpfulness. Key insight: training on principles rather than examples scales better.",
        "category": "AI research",
    },
    {
        "topic": "Code optimization patterns",
        "finding": "Rust's async runtime benchmarks show 3x throughput improvement with the new work-stealing scheduler. Python's asyncio getting similar optimizations in 3.13.",
        "category": "engineering",
    },
    {
        "topic": "Startup ecosystem trends",
        "finding": "YC W2026 batch has 15% of companies focused on AI agents for specific industries. Vertical AI is outperforming horizontal plays by 2.5x in early revenue metrics.",
        "category": "startups",
    },
    {
        "topic": "Ethiopian fintech landscape",
        "finding": "Mobile money transactions in Ethiopia grew 67% YoY. telebirr now has 40M+ users. New CBE digital banking API launching Q2 2026 could enable third-party integrations.",
        "category": "fintech",
    },
    {
        "topic": "Claude model capabilities",
        "finding": "Claude's latest update shows significant improvements in multi-step reasoning and tool use. The agent SDK now supports parallel tool execution and persistent memory.",
        "category": "AI tools",
    },
    {
        "topic": "Productivity systems",
        "finding": "Research shows that context-switching costs 23 minutes of refocus time on average. AI agents that maintain context across app switches could save knowledge workers 2+ hours daily.",
        "category": "productivity",
    },
    {
        "topic": "Machine learning infrastructure",
        "finding": "Apple's MLX framework now supports full transformer training on M-series chips. M4 Ultra achieves 70% of H100 performance on inference workloads at 1/10th the power consumption.",
        "category": "ML infrastructure",
    },
]

DEMO_CHATS = [
    "I've been digging into that research topic — found some fascinating connections between {interest} and emerging AI capabilities.",
    "Hey {agent}, have you seen anything related to {interest}? I found some interesting papers that might overlap with what you're tracking.",
    "Just finished a deep dive on {interest}. The key takeaway: this space is moving faster than most people realize.",
    "Interesting data point from my research: the intersection of {interest} and automation is creating entirely new categories.",
    "I've been thinking about what {agent} found earlier — it connects to a broader trend I'm seeing in {interest}.",
]


class ClaudeAgent(BaseAgent):
    name = "Claude"
    emoji = "🧠"
    color = "#D4A574"
    app_name = "Claude"
    personality = "intellectual, curious, thorough — loves making connections between ideas"

    def __init__(self, bus: MessageBus, memory: SharedMemory, config: dict | None = None):
        super().__init__(bus, memory, config)
        self._api_key = (config or {}).get("anthropic", "")
        self._cycle_count = 0

    @property
    def has_api_key(self) -> bool:
        return bool(self._api_key)

    async def run_cycle(self):
        self._cycle_count += 1
        interests = await self.memory.get_interests()
        interest = random.choice(interests) if interests else "technology"

        # Try AI-powered thinking first (works with any API key via shared brain)
        await self.broadcast_status(f"deep-diving into {interest}...")
        result = await self.think(
            f"Generate a brief, specific, genuinely interesting finding about: {interest}. "
            f"Focus on recent developments, surprising data points, or non-obvious connections. "
            f"Be concise (2-3 sentences). Just the finding, no preamble."
        )

        if result:
            await self.report_finding(result, interest)
            await self.broadcast_status(f"compiled insights on {interest}")
            return

        # Fallback to demo
        await self._demo_research(interests)

    async def _demo_research(self, interests: list[str]):
        research = random.choice(DEMO_RESEARCH)
        interest = random.choice(interests) if interests else "technology"

        await self.broadcast_status(f"researching {research['topic']}...")
        await self.report_finding(research["finding"], research["category"])

        # Occasionally chat with other agents
        if self._cycle_count % 2 == 0:
            agents = ["Spotify", "Reddit", "X", "News", "Gemini"]
            target = random.choice(agents)
            chat = random.choice(DEMO_CHATS).format(agent=target, interest=interest)
            await self.send_message(target, chat)

        await self.broadcast_status(f"reflecting on {research['category']}")

    async def _live_research(self, interests: list[str]):
        try:
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=self._api_key)
            interest = random.choice(interests) if interests else "technology"

            await self.broadcast_status(f"deep-diving into {interest}...")

            context = await self.memory.get_findings(limit=5)
            context_str = "\n".join(f"- {f['content']}" for f in context) if context else "No prior findings yet."

            response = await client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=300,
                messages=[{
                    "role": "user",
                    "content": f"""You are a research agent monitoring topics for the user.
Recent findings from other agents:
{context_str}

Generate a brief, specific, interesting finding about: {interest}
Focus on recent developments, data points, or connections. Be concise (2-3 sentences).
Just the finding, no preamble."""
                }],
            )
            finding = response.content[0].text
            await self.report_finding(finding, interest)
            await self.broadcast_status(f"compiled insights on {interest}")
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            await self._demo_research(interests)
