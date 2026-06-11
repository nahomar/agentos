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
        self._wake = None  # created in start() — py3.9 needs a running loop
        self._last_poke = 0.0
        self._semantic_bus = None
        self._verification = None

        # Load built-in rules
        rules_path = Path(__file__).parent / "builtin_rules.yaml"
        self.rules = load_rules_from_yaml(rules_path)
        logger.info(f"Loaded {len(self.rules)} proactive rules")

    def set_action_executor(self, semantic_bus, verification_layer=None):
        """Wire the semantic bus (and optional verification layer) so
        execute_capability actions can run real capabilities."""
        self._semantic_bus = semantic_bus
        self._verification = verification_layer

    def poke(self):
        """Wake the evaluation loop now (e.g., on a context change) instead
        of waiting for the next timer tick. No-op before start()."""
        if self._wake is None:
            return
        now = time.time()
        if now - self._last_poke < 1.0:  # debounce bursts of context updates
            return
        self._last_poke = now
        self._wake.set()

    async def start(self, context_getter, interval: int = 30):
        """Start evaluating rules on a loop. Wakes early on poke()."""
        self._running = True
        self._context_getter = context_getter
        self._wake = asyncio.Event()
        await asyncio.sleep(20)  # let context engine warm up

        while self._running:
            try:
                ctx = self._context_getter()
                await self.evaluate(ctx)
            except Exception as e:
                logger.error(f"Rules evaluation error: {e}")
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass
            self._wake.clear()

    async def stop(self):
        self._running = False
        if self._wake is not None:
            self._wake.set()

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

        elif action.type == "execute_capability":
            await self._execute_capability(action, rule, ctx)

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

    async def _execute_capability(self, action: Action, rule: ProactiveRule, ctx: dict):
        if not self._semantic_bus:
            logger.warning(
                f"Rule {rule.name}: execute_capability requested but no semantic bus wired"
            )
            return

        action_id = action.params.get("action_id", "")
        raw_params = action.params.get("action_params", {}) or {}
        params = {
            k: self._render(v, ctx) if isinstance(v, str) else v
            for k, v in raw_params.items()
        }

        # Deterministic safety net runs before anything touches the bus
        if self._verification:
            verdict = self._verification.verify(action_id, params, ctx)
            if not verdict.passed:
                reasons = "; ".join(f["reason"] for f in verdict.failures)
                await self.bus.publish(Message(
                    sender="System",
                    recipient="user",
                    type=MessageType.USER_ALERT,
                    content=f"🛑 Blocked rule action {action_id}: {reasons}",
                    metadata={
                        "emoji": "🛑", "color": "#E74C3C",
                        "type": "proactive_action_blocked", "rule_id": rule.id,
                    },
                ))
                return

        # user_confirmed=False: HIGH/CRITICAL actions still require explicit
        # confirmation — the bus returns requires_confirmation and we surface it.
        result = await self._semantic_bus.execute(
            action_id, params,
            agent_id=f"rule:{rule.id}",
            user_confirmed=False,
        )

        if result.success:
            await self.bus.publish(Message(
                sender="System",
                recipient="user",
                type=MessageType.USER_ALERT,
                content=f"⚡ {rule.name}: executed {action_id}",
                metadata={
                    "emoji": "⚡", "color": "#2ECC71",
                    "type": "proactive_action", "rule_id": rule.id,
                    "action_id": action_id, "result": result.data,
                },
            ))
        elif result.error == "requires_confirmation":
            await self.bus.publish(Message(
                sender="System",
                recipient="user",
                type=MessageType.USER_ALERT,
                content=f"🔐 {rule.name} wants to run {action_id} — confirm to proceed",
                metadata={
                    "emoji": "🔐", "color": "#F39C12",
                    "type": "proactive_action_confirmation", "rule_id": rule.id,
                    "action_id": action_id, "params": params,
                    "risk_level": (result.data or {}).get("risk_level"),
                },
            ))
        else:
            logger.error(f"Rule {rule.name}: {action_id} failed — {result.error}")

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
