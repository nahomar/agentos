from __future__ import annotations

import logging
import random
from typing import Optional, List, Dict, Any

logger = logging.getLogger("intelligence")


class AgentBrain:
    """Shared AI reasoning layer that any agent can use for real thinking."""

    def __init__(self, config: dict):
        self.config = config
        self._anthropic_key = config.get("anthropic", "")
        self._gemini_key = config.get("gemini", "")

    @property
    def has_claude(self) -> bool:
        return bool(self._anthropic_key)

    @property
    def has_gemini(self) -> bool:
        return bool(self._gemini_key)

    @property
    def has_any_ai(self) -> bool:
        return self.has_claude or self.has_gemini

    async def think(
        self,
        agent_name: str,
        agent_personality: str,
        task: str,
        context: str = "",
        recent_findings: str = "",
        user_interests: str = "",
        max_tokens: int = 300,
    ) -> Optional[str]:
        """Have an AI model think on behalf of an agent. Returns None if no AI available."""

        system_prompt = f"""You are {agent_name}, an autonomous AI agent running on a user's phone.
Your personality: {agent_personality}

You are part of AgentOS — a team of AI agents that autonomously manage the user's digital life.
You communicate with other agents and proactively help the user.

User's interests: {user_interests or 'technology, AI, coding'}

Rules:
- Be concise (2-4 sentences max)
- Be specific with real facts and data points when possible
- Stay in character with your personality
- Speak naturally, not like a formal report
- If sharing a finding, make it genuinely interesting and actionable"""

        user_prompt = task
        if context:
            user_prompt = f"Current context:\n{context}\n\n{task}"
        if recent_findings:
            user_prompt += f"\n\nRecent findings from other agents:\n{recent_findings}"

        # Try Claude first, then Gemini
        if self.has_claude:
            result = await self._claude_think(system_prompt, user_prompt, max_tokens)
            if result:
                return result

        if self.has_gemini:
            result = await self._gemini_think(system_prompt, user_prompt, max_tokens)
            if result:
                return result

        return None

    async def chat(
        self,
        sender_name: str,
        sender_personality: str,
        recipient_name: str,
        recipient_personality: str,
        topic: str,
        context: str = "",
        user_name: str = "the user",
    ) -> Optional[List[str]]:
        """Generate a natural conversation between two agents. Returns list of messages or None."""

        prompt = f"""Generate a brief, natural conversation between two AI agents:

Agent 1: {sender_name} — {sender_personality}
Agent 2: {recipient_name} — {recipient_personality}

Topic: {topic}
User's name: {user_name}
{f'Context: {context}' if context else ''}

Write exactly 3 short messages alternating between the agents (sender, recipient, sender).
Each message should be 1-2 sentences, conversational, and in-character.
Format: one message per line, no labels or prefixes."""

        if self.has_claude:
            result = await self._claude_think(
                "You generate natural agent-to-agent conversations. Output only the messages, one per line.",
                prompt,
                250,
            )
            if result:
                lines = [l.strip() for l in result.strip().split("\n") if l.strip()]
                return lines[:3] if len(lines) >= 2 else None

        if self.has_gemini:
            result = await self._gemini_think(
                "You generate natural agent-to-agent conversations. Output only the messages, one per line.",
                prompt,
                250,
            )
            if result:
                lines = [l.strip() for l in result.strip().split("\n") if l.strip()]
                return lines[:3] if len(lines) >= 2 else None

        return None

    async def classify(
        self,
        text: str,
        categories: List[str],
        context: str = "",
    ) -> Optional[str]:
        """Classify text into one of the given categories. Returns category or None."""

        prompt = f"""Classify this text into exactly one category.

Text: "{text}"
Categories: {', '.join(categories)}
{f'Context: {context}' if context else ''}

Respond with just the category name, nothing else."""

        if self.has_claude:
            result = await self._claude_think("You classify text. Respond with just the category.", prompt, 20)
            if result:
                result = result.strip().lower()
                for cat in categories:
                    if cat.lower() in result:
                        return cat
                return categories[0]

        return None

    async def extract(self, system: str, prompt: str, max_tokens: int = 300) -> Optional[str]:
        """Raw completion without agent-personality framing — for structured
        extraction like command parsing. Returns None if no AI available."""
        if self.has_claude:
            result = await self._claude_think(system, prompt, max_tokens)
            if result:
                return result
        if self.has_gemini:
            return await self._gemini_think(system, prompt, max_tokens)
        return None

    async def summarize(self, items: List[str], style: str = "brief") -> Optional[str]:
        """Summarize a list of items. Returns summary or None."""

        items_text = "\n".join(f"- {item}" for item in items)
        prompt = f"""Summarize these findings into a {style} briefing (3-5 sentences):

{items_text}

Focus on the most important and actionable insights. Be concise."""

        if self.has_claude:
            return await self._claude_think("You create concise briefings.", prompt, 200)
        if self.has_gemini:
            return await self._gemini_think("You create concise briefings.", prompt, 200)
        return None

    async def _claude_think(self, system: str, prompt: str, max_tokens: int) -> Optional[str]:
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=self._anthropic_key)
            # claude-sonnet-4-20250514 is deprecated (retires 2026-06-15)
            response = await client.messages.create(
                model="claude-opus-4-8",
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return None

    async def _gemini_think(self, system: str, prompt: str, max_tokens: int) -> Optional[str]:
        try:
            import google.generativeai as genai
            genai.configure(api_key=self._gemini_key)
            model = genai.GenerativeModel("gemini-2.0-flash")
            response = await model.generate_content_async(f"{system}\n\n{prompt}")
            return response.text
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return None
