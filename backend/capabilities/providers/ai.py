from __future__ import annotations

import logging
from backend.capabilities.registry import CapabilityProvider, CapabilityResult

logger = logging.getLogger("capabilities.ai")


class ClaudeAIProvider(CapabilityProvider):
    id = "ai.claude"
    name = "Claude AI"
    description = "Generate text using Claude API"
    category = "ai"

    @property
    def available(self) -> bool:
        return bool(self.config.get("anthropic"))

    async def execute(self, params: dict) -> CapabilityResult:
        prompt = params.get("prompt", "")
        system = params.get("system", "You are a helpful assistant.")
        model = params.get("model", "claude-sonnet-4-20250514")

        if not self.available:
            return CapabilityResult(success=True, data={
                "demo": True,
                "response": f"[Demo] Claude would respond to: {prompt[:100]}...",
            })

        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=self.config["anthropic"])
            response = await client.messages.create(
                model=model,
                max_tokens=500,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            return CapabilityResult(success=True, data={
                "response": response.content[0].text,
                "model": model,
            })
        except Exception as e:
            return CapabilityResult(success=False, error=str(e))


class GeminiAIProvider(CapabilityProvider):
    id = "ai.gemini"
    name = "Gemini AI"
    description = "Generate text using Google Gemini"
    category = "ai"

    @property
    def available(self) -> bool:
        return bool(self.config.get("gemini"))

    async def execute(self, params: dict) -> CapabilityResult:
        prompt = params.get("prompt", "")
        model = params.get("model", "gemini-2.0-flash")

        if not self.available:
            return CapabilityResult(success=True, data={
                "demo": True,
                "response": f"[Demo] Gemini would respond to: {prompt[:100]}...",
            })

        try:
            import google.generativeai as genai
            genai.configure(api_key=self.config["gemini"])
            m = genai.GenerativeModel(model)
            response = await m.generate_content_async(prompt)
            return CapabilityResult(success=True, data={
                "response": response.text,
                "model": model,
            })
        except Exception as e:
            return CapabilityResult(success=False, error=str(e))
