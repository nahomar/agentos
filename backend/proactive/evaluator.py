from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Dict, List

from backend.bus import MessageBus, Message, MessageType
from backend.context.models import UserContext
from backend.proactive.rules import ProactiveRule, Condition, Action, load_rules_from_yaml

logger = logging.getLogger("proactive")


class RulesEvaluator:
    """Evaluates proactive rules against user context and triggers actions."""

    def __init__(self, bus: MessageBus, config: dict):
        self.bus = bus
        self.config = config
        self.rules: List[ProactiveRule] = []
        self._cooldowns: Dict[str, float] = {}  # rule_id -> last_triggered_time
        self._running = False

        # Load built-in rules
        rules_path = Path(__file__).parent / "builtin_rules.yaml"
        self.rules = load_rules_from_yaml(rules_path)
        logger.info(f"Loaded {len(self.rules)} proactive rules")

    async def start(self, context_getter, interval: int = 30):
        """Start evaluating rules on a loop."""
        self._running = True
        self._context_getter = context_getter
        await asyncio.sleep(20)  # let context engine warm up

        while self._running:
            try:
                ctx = self._context_getter()
                await self.evaluate(ctx)
            except Exception as e:
                logger.error(f"Rules evaluation error: {e}")
            await asyncio.sleep(interval)

    async def stop(self):
        self._running = False

    async def evaluate(self, ctx: UserContext):
        ctx_dict = ctx.to_dict()

        for rule in self.rules:
            if not rule.enabled:
                continue

            # Check cooldown
            last_trigger = self._cooldowns.get(rule.id, 0)
            if (time.time() - last_trigger) < (rule.cooldown_minutes * 60):
                continue

            # Evaluate all conditions
            if all(self._eval_condition(c, ctx_dict) for c in rule.conditions):
                await self._execute_actions(rule, ctx_dict)
                self._cooldowns[rule.id] = time.time()

    def _eval_condition(self, condition: Condition, ctx: dict) -> bool:
        value = self._resolve_field(condition.field, ctx)

        try:
            op = condition.operator
            target = condition.value

            if op == "eq":
                return value == target
            elif op == "neq":
                return value != target
            elif op == "gt":
                return float(value) > float(target)
            elif op == "lt":
                return float(value) < float(target)
            elif op == "gte":
                return float(value) >= float(target)
            elif op == "lte":
                return float(value) <= float(target)
            elif op == "in":
                return value in target
            elif op == "not_in":
                return value not in target
            elif op == "contains":
                return target in str(value)
            elif op == "between":
                if isinstance(target, list) and len(target) == 2:
                    return float(target[0]) <= float(value) <= float(target[1])
            elif op == "is_true":
                return bool(value)
            elif op == "is_false":
                return not bool(value)
        except (TypeError, ValueError):
            return False

        return False

    def _resolve_field(self, field_path: str, ctx: dict):
        """Resolve dot-notation field path against context dict."""
        parts = field_path.split(".")
        current = ctx

        for part in parts:
            # H10: Block dunder attribute traversal
            if part.startswith("_"):
                return None
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None  # Only traverse dicts, never getattr

            if current is None:
                return None

        return current

    async def _execute_actions(self, rule: ProactiveRule, ctx: dict):
        logger.info(f"Rule triggered: {rule.name}")

        for action in rule.actions:
            try:
                await self._execute_action(action, rule, ctx)
            except Exception as e:
                logger.error(f"Action error in rule {rule.name}: {e}")

    async def _execute_action(self, action: Action, rule: ProactiveRule, ctx: dict):
        if action.type == "notify":
            title = self._render(action.params.get("title", "AgentOS"), ctx)
            body = self._render(action.params.get("body", ""), ctx)

            await self.bus.publish(Message(
                sender="System",
                recipient="user",
                type=MessageType.USER_ALERT,
                content=f"**{title}**\n{body}",
                metadata={
                    "emoji": "💡",
                    "color": "#FFD700",
                    "type": "proactive_suggestion",
                    "rule_id": rule.id,
                    "priority": rule.priority,
                },
            ))

        elif action.type == "suggest":
            message = self._render(action.params.get("message", ""), ctx)

            await self.bus.publish(Message(
                sender="System",
                recipient="user",
                type=MessageType.USER_ALERT,
                content=message,
                metadata={
                    "emoji": "🤔",
                    "color": "#3498DB",
                    "type": "proactive_suggestion",
                    "rule_id": rule.id,
                },
            ))

        elif action.type == "agent_task":
            agent = action.params.get("agent", "Claude")
            task = self._render(action.params.get("task", ""), ctx)

            await self.bus.publish(Message(
                sender="System",
                recipient=agent,
                type=MessageType.TASK_STATUS,
                content=task,
                metadata={"emoji": "📋", "color": "#FFD700", "type": "agent_task"},
            ))

    def _render(self, template: str, ctx: dict) -> str:
        try:
            # Simple variable substitution
            result = template
            for key, val in self._flatten(ctx).items():
                result = result.replace(f"{{{key}}}", str(val))
            return result
        except Exception:
            return template

    def _flatten(self, d: dict, prefix: str = "") -> dict:
        items = {}
        for k, v in d.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                items.update(self._flatten(v, key))
            else:
                items[key] = v
        return items

    def add_rule(self, rule: ProactiveRule):
        self.rules.append(rule)

    def remove_rule(self, rule_id: str):
        self.rules = [r for r in self.rules if r.id != rule_id]

    def get_rules_info(self) -> list:
        return [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "priority": r.priority,
                "enabled": r.enabled,
                "cooldown_minutes": r.cooldown_minutes,
                "conditions_count": len(r.conditions),
                "source": r.source,
            }
            for r in self.rules
        ]
