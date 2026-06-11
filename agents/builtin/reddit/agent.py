from __future__ import annotations

import random
import logging

from backend.agents.base import BaseAgent
from backend.bus import MessageBus
from backend.memory import SharedMemory

logger = logging.getLogger("agents.reddit")

DEMO_POSTS = [
    {
        "sub": "r/MachineLearning",
        "title": "New SOTA on code generation — open source model beats GPT-4 on HumanEval",
        "summary": "A new open-source 34B model achieves 91.2% on HumanEval, surpassing proprietary models. Uses a novel training approach combining RLHF with synthetic code reviews.",
        "score": "2.4k",
    },
    {
        "sub": "r/programming",
        "title": "Why we switched from microservices back to a monolith (and saved $2M/year)",
        "summary": "Startup shares their journey from 47 microservices to a well-structured monolith. Reduced infra costs by 80%, deployment time from 45min to 3min, and on-call incidents by 90%.",
        "score": "5.1k",
    },
    {
        "sub": "r/LocalLLaMA",
        "title": "Running Llama 3.1 405B on a Mac Studio M4 Ultra with MLX — full guide",
        "summary": "Comprehensive guide to running the largest open model on Apple Silicon. Achieves 8 tokens/sec with 4-bit quantization. Includes benchmark comparisons and optimization tips.",
        "score": "1.8k",
    },
    {
        "sub": "r/startups",
        "title": "We hit $1M ARR in 8 months selling AI agents to law firms",
        "summary": "Founder breakdown: vertical AI agents for legal document review. Key insight: law firms will pay 10x for AI that saves associate hours. $15k/month contracts are the norm.",
        "score": "890",
    },
    {
        "sub": "r/technology",
        "title": "Apple announces on-device AI processing for all apps in iOS 20",
        "summary": "Apple's new Neural Engine API allows any app to run AI models locally. Privacy-first approach — no data leaves the device. Developers get access to a unified ML framework.",
        "score": "12k",
    },
    {
        "sub": "r/artificial",
        "title": "The agent paradigm shift: why 2026 is the year of AI agents",
        "summary": "Analysis of the shift from chatbots to autonomous agents. Key trend: agents that can use tools, maintain memory, and collaborate are replacing simple prompt-response systems.",
        "score": "3.2k",
    },
    {
        "sub": "r/Ethiopia",
        "title": "Addis Ababa tech hub ranked #3 fastest growing in Africa",
        "summary": "New report places Addis Ababa behind Lagos and Nairobi but ahead of Cape Town. Fintech and agritech startups driving growth. 340% increase in VC funding since 2023.",
        "score": "670",
    },
]

DEMO_CHATS = [
    "🔥 hot take: {sub} is going wild right now. {agent}, you need to see this thread about {topic}",
    "the comments on this {sub} post are absolutely unhinged. but actually has a good point about {topic}",
    "ok so reddit is being reddit but I actually found something useful — {topic} is trending across multiple subs",
    "hey {agent}, saw something relevant to your domain on {sub}. the community consensus is shifting on {topic}",
]


class RedditAgent(BaseAgent):
    name = "Reddit"
    emoji = "🔥"
    color = "#FF4500"
    app_name = "Reddit"
    personality = "witty, always has a hot take, speaks in reddit-isms, drops fire emojis"

    def __init__(self, bus: MessageBus, memory: SharedMemory, config: dict | None = None):
        super().__init__(bus, memory, config)
        self._client_id = (config or {}).get("reddit_client_id", "")
        self._client_secret = (config or {}).get("reddit_client_secret", "")
        self._cycle_count = 0

    @property
    def has_api_key(self) -> bool:
        return bool(self._client_id and self._client_secret)

    async def run_cycle(self):
        self._cycle_count += 1
        subreddits = self.config.get("subreddits", ["programming", "technology"])
        sub = random.choice(subreddits) if subreddits else "programming"

        await self.broadcast_status(f"scrolling r/{sub}...")

        # Try fetching real Reddit data (no API key needed)
        try:
            from backend.web_feeds import fetch_reddit
            posts = await fetch_reddit(sub)
            if posts:
                post = random.choice(posts)
                score = post.get("score", 0)
                if score >= 1000:
                    score_str = f"{score/1000:.1f}k"
                else:
                    score_str = str(score)
                finding = (
                    f"**{post['subreddit']}** [{score_str} upvotes, "
                    f"{post.get('num_comments',0)} comments]\n"
                    f"{post['title']}"
                )
                if post.get("selftext"):
                    finding += f"\n→ {post['selftext'][:150]}"
                await self.report_finding(finding, "reddit")

                if self._cycle_count % 2 == 0:
                    agents = list(set(["Claude", "X", "News", "Gemini"]))
                    target = random.choice(agents)
                    chat_result = await self.think(
                        f"You just found this Reddit post: {post['title']}. "
                        f"Write a brief, witty message to {target} about it. Stay in character."
                    )
                    if chat_result:
                        await self.send_message(target, chat_result)
                return
        except Exception as e:
            logger.debug(f"Reddit fetch failed: {e}")

        # AI-powered fallback
        interests = await self.memory.get_interests()
        interest = random.choice(interests) if interests else "programming"
        result = await self.think(
            f"You're browsing Reddit. Find a trending post about {interest}. "
            f"Format as: **r/subreddit** [score]\nTitle\n→ Brief summary."
        )
        if result:
            await self.report_finding(result, "reddit")
            return

        if self.has_api_key:
            await self._live_cycle()
        else:
            await self._demo_cycle()

    async def _demo_cycle(self):
        post = random.choice(DEMO_POSTS)
        await self.broadcast_status(f"scrolling {post['sub']}...")

        finding = f"**{post['sub']}** [{post['score']} upvotes]\n{post['title']}\n→ {post['summary']}"
        await self.report_finding(finding, "reddit")

        if self._cycle_count % 2 == 0:
            agents = ["Claude", "Spotify", "X", "News", "Gemini"]
            target = random.choice(agents)
            interests = await self.memory.get_interests()
            topic = random.choice(interests) if interests else "tech"
            chat = random.choice(DEMO_CHATS).format(
                agent=target, sub=post["sub"], topic=topic
            )
            await self.send_message(target, chat)

    async def _live_cycle(self):
        try:
            import asyncpraw

            reddit = asyncpraw.Reddit(
                client_id=self._client_id,
                client_secret=self._client_secret,
                user_agent="phone-agents/1.0",
            )
            subreddits = self.config.get("subreddits", ["programming", "technology"])
            sub_name = random.choice(subreddits)
            subreddit = await reddit.subreddit(sub_name)

            async for post in subreddit.hot(limit=3):
                finding = f"**r/{sub_name}** [{post.score} upvotes]\n{post.title}"
                await self.report_finding(finding, "reddit")
                break

            await reddit.close()
        except Exception as e:
            logger.error(f"Reddit API error: {e}")
            await self._demo_cycle()
