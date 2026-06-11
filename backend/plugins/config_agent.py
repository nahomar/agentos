from __future__ import annotations

import random
import logging

from backend.agents.base import BaseAgent
from backend.bus import MessageBus
from backend.memory import SharedMemory
from backend.plugins.manifest import AgentManifest

logger = logging.getLogger("plugins.config_agent")


class ConfigAgent(BaseAgent):
    """Agent defined entirely by YAML manifest — no Python code needed."""

    def __init__(
        self,
        bus: MessageBus,
        memory: SharedMemory,
        config: dict,
        manifest: AgentManifest,
    ):
        self.name = manifest.name
        self.emoji = manifest.emoji
        self.color = manifest.color
        self.app_name = manifest.app_name or manifest.name
        self.personality = manifest.personality
        self._manifest = manifest

        super().__init__(bus, memory, config)

    async def run_cycle(self):
        context = await self.memory.get_user_context()

        for action in self._manifest.actions:
            condition = action.get("condition", "")
            if condition and not self._eval_condition(condition, context):
                continue

            action_type = action.get("type", "notify")
            template = action.get("template", action.get("message", ""))

            if action_type == "notify":
                message = self._render_template(template, context)
                await self.alert_user(message)
                await self.broadcast_status(message[:60])
            elif action_type == "discover":
                message = self._render_template(template, context)
                category = action.get("category", "general")
                await self.report_finding(message, category)
            elif action_type == "chat":
                target = action.get("target", "all")
                message = self._render_template(template, context)
                await self.send_message(target, message)

        # Evaluate rules
        for rule in self._manifest.rules:
            when = rule.get("when", "")
            if when and self._eval_condition(when, context):
                do_type = rule.get("do", "notify")
                message = self._render_template(rule.get("message", ""), context)
                if do_type == "notify":
                    await self.alert_user(message)

        if not self._manifest.actions and not self._manifest.rules:
            await self.broadcast_status("monitoring...")

    def _eval_condition(self, condition: str, context: dict) -> bool:
        """Safe condition evaluator — NO eval(). Parses simple comparisons only."""
        try:
            condition = condition.strip()
            ctx = _DotDict(context)

            # Parse: "context.field == value" or "context.field > value"
            import re
            m = re.match(r'^([\w.]+)\s*(==|!=|>|<|>=|<=)\s*(.+)$', condition)
            if not m:
                return False

            field_path, op, raw_value = m.group(1), m.group(2), m.group(3).strip()

            # Resolve field (e.g., "context.hour" → ctx.hour)
            obj = ctx
            for part in field_path.replace("context.", "").split("."):
                if isinstance(obj, dict):
                    obj = obj.get(part)
                elif hasattr(obj, part):
                    obj = getattr(obj, part)
                else:
                    return False
                if obj is None:
                    return False

            # Parse value
            if raw_value in ("True", "true"):
                value = True
            elif raw_value in ("False", "false"):
                value = False
            elif raw_value.isdigit():
                value = int(raw_value)
            elif raw_value.replace(".", "", 1).isdigit():
                value = float(raw_value)
            else:
                value = raw_value.strip("'\"")

            # Compare
            if op == "==": return obj == value
            if op == "!=": return obj != value
            if op == ">": return float(obj) > float(value)
            if op == "<": return float(obj) < float(value)
            if op == ">=": return float(obj) >= float(value)
            if op == "<=": return float(obj) <= float(value)
            return False
        except Exception:
            return False

    def _render_template(self, template: str, context: dict) -> str:
        """C5 fix: Safe template rendering — no attribute access, only key substitution."""
        import re
        def _replace(match):
            key = match.group(1)
            # Only allow simple dot-notation keys, no __class__ etc.
            if "__" in key:
                return match.group(0)
            parts = key.replace("context.", "").split(".")
            val = context
            for p in parts:
                if isinstance(val, dict):
                    val = val.get(p, "")
                else:
                    return ""
            return str(val) if val else ""

        try:
            return re.sub(r'\{([\w.]+)\}', _replace, template)
        except Exception:
            return template


class _DotDict(dict):
    """Dict that supports dot-notation access for template rendering."""

    def __getattr__(self, key):
        val = self.get(key, _MISSING)
        if val is _MISSING:
            return ""  # M10: Return empty string for missing keys, not empty dict
        if isinstance(val, dict):
            return _DotDict(val)
        if val is None:
            return ""
        return val

    def __str__(self):
        return str(dict(self)) if self else ""

    def __bool__(self):
        return bool(dict(self))


_MISSING = object()
