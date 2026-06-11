from __future__ import annotations

"""
Command Pipeline — natural language in, verified action out.

The Jarvis path: "play some jazz" → intent → verification → semantic bus →
result, in one round trip. Parsing is deterministic-first (fast, free,
predictable for common phrasings), with the AI brain as fallback for
anything the rules don't catch. HIGH/CRITICAL actions are never executed
directly: they become pending actions the user must confirm.
"""

import json
import logging
import re
import time
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger("command")

PENDING_TTL_SECONDS = 300


class CommandPipeline:
    def __init__(
        self,
        semantic_bus,
        verification_layer=None,
        brain=None,
        context_getter=None,
        speculative_engine=None,
    ):
        self.bus = semantic_bus
        self.verification = verification_layer
        self.brain = brain
        self.context_getter = context_getter
        self.speculative = speculative_engine
        self._pending: Dict[str, dict] = {}  # pending_id -> {action_id, params, created}

    # === Entry points ===

    async def handle(self, text: str, source: str = "api") -> dict:
        """Parse a natural-language command and act on it."""
        text = (text or "").strip()
        if not text:
            return self._reply("Say something like \"play some jazz\" or \"what's on my calendar?\"")
        if len(text) > 2000:
            return self._reply("That command is too long — keep it under 2000 characters.")

        # Confirmation replies ("confirm a1b2c3d4e5f6" / "deny a1b2c3d4e5f6")
        m = re.match(r"(confirm|approve|deny|cancel)\s+([a-f0-9]{12})$", text, re.IGNORECASE)
        if m:
            return await self.confirm(m.group(2).lower(), m.group(1).lower() in ("confirm", "approve"))

        intent = self._parse_deterministic(text)
        if intent is None and self.brain is not None and self.brain.has_any_ai:
            intent = await self._parse_with_ai(text)

        if intent is None:
            return await self._chat_fallback(text)

        return await self._execute(intent["action_id"], intent["params"], source)

    async def confirm(self, pending_id: str, approved: bool) -> dict:
        """Resolve a pending high-risk action."""
        self._expire_pending()
        pending = self._pending.pop(pending_id, None)
        if pending is None:
            return self._reply("That confirmation expired or was already handled.")
        if not approved:
            return self._reply(f"Cancelled {pending['action_id']}.")

        result = await self.bus.execute(
            pending["action_id"], pending["params"],
            agent_id=f"command:{pending['source']}",
            user_confirmed=True,
        )
        if result.success:
            return self._reply(
                f"Done — {pending['action_id']} executed.",
                action_id=pending["action_id"], success=True, data=result.data,
            )
        return self._reply(
            f"{pending['action_id']} failed: {result.error}",
            action_id=pending["action_id"], success=False,
        )

    def get_pending(self) -> list:
        self._expire_pending()
        return [
            {"pending_id": pid, "action_id": p["action_id"], "params": p["params"]}
            for pid, p in self._pending.items()
        ]

    # === Execution ===

    async def _execute(self, action_id: str, params: dict, source: str) -> dict:
        ctx = {}
        if self.context_getter:
            try:
                c = self.context_getter()
                ctx = c.to_dict() if hasattr(c, "to_dict") else dict(c)
            except Exception:
                pass

        # Deterministic safety net first
        if self.verification:
            verdict = self.verification.verify(action_id, params, ctx)
            if not verdict.passed:
                reasons = "; ".join(f["reason"] for f in verdict.failures)
                return self._reply(
                    f"Blocked {action_id}: {reasons}",
                    action_id=action_id, success=False, blocked=True,
                )

        # Serve from the speculative cache when pre-warmed
        if self.speculative:
            cached = self.speculative.get_cached_result(action_id, params)
            if cached is not None:
                return self._reply(
                    self._describe_result(action_id, cached),
                    action_id=action_id, success=True, data=cached, cached=True,
                )

        result = await self.bus.execute(
            action_id, params, agent_id=f"command:{source}", user_confirmed=False,
        )

        if result.success:
            return self._reply(
                self._describe_result(action_id, result.data),
                action_id=action_id, success=True, data=result.data,
            )

        if result.error == "requires_confirmation":
            pending_id = uuid.uuid4().hex[:12]
            self._pending[pending_id] = {
                "action_id": action_id, "params": params,
                "source": source, "created": time.time(),
            }
            self._expire_pending()
            risk = (result.data or {}).get("risk_level", "high")
            return self._reply(
                f"{action_id} is a {risk}-risk action — confirm to proceed.",
                action_id=action_id, success=False,
                pending_id=pending_id, requires_confirmation=True, params=params,
            )

        return self._reply(
            f"{action_id} failed: {result.error}",
            action_id=action_id, success=False,
        )

    def _expire_pending(self):
        cutoff = time.time() - PENDING_TTL_SECONDS
        self._pending = {
            pid: p for pid, p in self._pending.items() if p["created"] > cutoff
        }

    # === Deterministic parser ===

    # Ordered (pattern, builder) pairs — first match wins
    def _parse_deterministic(self, text: str) -> Optional[dict]:
        t = text.strip()
        low = t.lower().rstrip("?!.")

        m = re.match(r"(?:please\s+)?(?:play|put on)\s+(?:some\s+)?(.+)", low)
        if m and "playlist" in m.group(1):
            name = m.group(1).replace("playlist", "").strip()
            return {"action_id": "spotify.play_playlist", "params": {"name": name or "favorites"}}
        if m:
            return {"action_id": "spotify.play_track", "params": {"query": m.group(1)}}
        if low in ("pause", "pause music", "stop music", "stop the music"):
            return {"action_id": "spotify.pause", "params": {}}
        if re.match(r"what(?:'s| is)\s+playing", low) or low == "now playing":
            return {"action_id": "spotify.get_now_playing", "params": {}}

        m = re.match(r"(?:text|message|send a message to|tell)\s+([\w .'-]+?)(?:\s+(?:saying|that)\s+|\s*[:,]\s*)(.+)", t, re.IGNORECASE)
        if m:
            return {"action_id": "messages.send",
                    "params": {"recipient": m.group(1).strip(), "body": m.group(2).strip()}}
        if re.match(r"(?:any |do i have )?unread messages", low) or low == "check messages":
            return {"action_id": "messages.get_unread", "params": {}}

        m = re.match(r"call\s+([\w .'-]+)", t, re.IGNORECASE)
        if m:
            return {"action_id": "phone.call", "params": {"recipient": m.group(1).strip()}}

        m = re.match(r"(?:navigate|directions|take me|drive)\s+(?:to\s+)?(.+)", low)
        if m:
            return {"action_id": "maps.navigate", "params": {"destination": m.group(1)}}
        m = re.match(r"find\s+(?:a\s+|the nearest\s+)?(.+?)\s+(?:near me|nearby)", low) or \
            re.match(r"(?:any|where(?:'s| is) the nearest)\s+(.+?)\s*(?:near me|nearby)?$", low)
        if m and any(w in low for w in ("near", "nearest", "nearby")):
            return {"action_id": "maps.find_nearby", "params": {"query": m.group(1)}}

        if re.search(r"(?:what'?s? )?on my (?:calendar|schedule)|upcoming events|my agenda", low):
            return {"action_id": "calendar.get_upcoming", "params": {}}

        m = re.match(r"(?:note|remember)(?:\s+that)?\s*[:,]?\s+(.+)", t, re.IGNORECASE)
        if m:
            content = m.group(1).strip()
            return {"action_id": "notes.create",
                    "params": {"title": content[:40], "content": content}}
        m = re.match(r"search (?:my )?notes (?:for\s+)?(.+)", low)
        if m:
            return {"action_id": "notes.search", "params": {"query": m.group(1)}}

        m = re.match(r"(?:search|google|look up)(?:\s+for)?\s+(.+)", low)
        if m:
            return {"action_id": "browser.search", "params": {"query": m.group(1)}}

        m = re.match(r"(?:pay|send)\s+\$?(\d+(?:\.\d+)?)\s+(?:dollars\s+)?to\s+([\w .'-]+)", t, re.IGNORECASE)
        if m:
            return {"action_id": "payments.send",
                    "params": {"recipient": m.group(2).strip(), "amount": float(m.group(1))}}
        if re.search(r"\b(?:my )?balance\b", low):
            return {"action_id": "payments.get_balance", "params": {}}

        m = re.match(r"(?:set\s+)?volume\s+(?:to\s+)?(\d+)", low)
        if m:
            return {"action_id": "settings.set_volume", "params": {"level": int(m.group(1))}}
        m = re.match(r"(?:turn\s+)?(?:dnd|do not disturb)\s+(on|off)", low) or \
            re.match(r"(enable|disable)\s+(?:dnd|do not disturb)", low)
        if m:
            on = m.group(1) in ("on", "enable")
            return {"action_id": "settings.toggle_dnd", "params": {"enabled": on}}

        if re.match(r"take a (?:photo|picture|pic)", low):
            return {"action_id": "camera.take_photo", "params": {}}

        return None

    # === AI parser (fallback for free-form phrasings) ===

    async def _parse_with_ai(self, text: str) -> Optional[dict]:
        actions_context = self.bus.get_actions_context()
        prompt = (
            f"{actions_context}\n\n"
            f'User command: "{text}"\n\n'
            "If the command maps to one of the actions above, respond with ONLY a "
            'JSON object: {"action_id": "<id>", "params": {<params>}}. '
            'If it does not map to any action, respond with ONLY: {"action_id": null}.'
        )
        try:
            raw = await self.brain.extract(
                "You translate user commands into structured action calls. "
                "Respond with only valid JSON, no other text.",
                prompt,
            )
            if not raw:
                return None
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if not m:
                return None
            data = json.loads(m.group(0))
            action_id = data.get("action_id")
            if not action_id or action_id not in self.bus._actions:
                return None
            params = data.get("params") or {}
            if not isinstance(params, dict):
                return None
            return {"action_id": action_id, "params": params}
        except Exception as e:
            logger.debug(f"AI parse failed: {e}")
            return None

    async def _chat_fallback(self, text: str) -> dict:
        if self.brain is not None and self.brain.has_any_ai:
            ctx = ""
            if self.context_getter:
                try:
                    c = self.context_getter()
                    ctx = str(c.to_dict() if hasattr(c, "to_dict") else c)
                except Exception:
                    pass
            answer = await self.brain.think(
                agent_name="AgentOS",
                agent_personality="A capable, concise personal assistant running on the user's device.",
                task=text,
                context=ctx,
            )
            if answer:
                return self._reply(answer)
        return self._reply(
            "I didn't catch an action there. Try things like: \"play some jazz\", "
            "\"text Sam: running late\", \"what's on my calendar\", or \"volume 40\"."
        )

    # === Reply formatting ===

    def _describe_result(self, action_id: str, data: Any) -> str:
        sim = " (simulated)" if isinstance(data, dict) and data.get("simulated") else ""
        if action_id == "calendar.get_upcoming" and isinstance(data, dict):
            n = data.get("count", 0)
            return f"You have {n} upcoming event{'s' if n != 1 else ''}.{sim}"
        if action_id == "spotify.get_now_playing" and isinstance(data, dict):
            playback = data.get("playback")
            return f"Now playing: {playback}" if playback else f"Nothing is playing right now.{sim}"
        if action_id.startswith("notes.search") and isinstance(data, dict):
            return f"Found {data.get('count', 0)} matching note(s).{sim}"
        if action_id == "payments.get_balance" and isinstance(data, dict):
            return f"Balance: {data.get('balance')} {data.get('currency', '')}{sim}"
        return f"Done — {action_id} executed.{sim}"

    @staticmethod
    def _reply(reply: str, **extra) -> dict:
        out = {"reply": reply, "success": extra.pop("success", None)}
        out.update(extra)
        return out
