from __future__ import annotations

"""
Semantic Bus — The core routing layer between agents and app actions.

Instead of agents scraping UIs, the Semantic Bus:
1. Receives action schemas from registered apps
2. Routes agent intents to the correct action
3. Validates params, checks permissions, verifies risk level
4. Executes the action and returns results
5. Emits events that other agents can subscribe to

The bus makes agents INSTANT because they skip the entire
see → understand → plan → click pipeline.
"""

import asyncio
import logging
import time
from typing import Callable, Dict, List, Optional, Any

from backend.semantic_bus.schema import (
    ActionSchema, ActionResult, AppManifest, RiskLevel,
)

logger = logging.getLogger("semantic_bus")


class SemanticBus:
    """Routes agent intents to app actions at protocol speed."""

    def __init__(self):
        self._apps: Dict[str, AppManifest] = {}
        self._actions: Dict[str, ActionSchema] = {}
        self._handlers: Dict[str, Callable] = {}  # action_id -> async handler
        self._event_listeners: Dict[str, List[Callable]] = {}
        self._execution_log: List[dict] = []
        self._cooldowns: Dict[str, float] = {}
        self._biometric_callback: Optional[Callable] = None

    def register_app(self, manifest: AppManifest, handlers: Dict[str, Callable] = None):
        """Register an app and its available actions."""
        self._apps[manifest.app_id] = manifest

        for action in manifest.actions:
            self._actions[action.id] = action
            if handlers and action.id in handlers:
                self._handlers[action.id] = handlers[action.id]

        logger.info(
            f"Registered app: {manifest.name} "
            f"({len(manifest.actions)} actions, {len(manifest.events)} events)"
        )

    def set_biometric_callback(self, callback: Callable):
        """Set the callback for biometric verification (FaceID/fingerprint)."""
        self._biometric_callback = callback

    def get_available_actions(self, tags: List[str] = None) -> List[ActionSchema]:
        """Get all available actions, optionally filtered by tags."""
        actions = list(self._actions.values())
        if tags:
            actions = [
                a for a in actions
                if any(t in a.tags for t in tags)
            ]
        return actions

    def get_actions_context(self, tags: List[str] = None, limit: int = 20) -> str:
        """Get a formatted context string of available actions for an agent."""
        actions = self.get_available_actions(tags)[:limit]
        if not actions:
            return "No actions available."

        lines = ["Available actions:"]
        for a in actions:
            params = ", ".join(f"{p.name}:{p.type.value}" for p in a.params)
            lines.append(f"  - {a.id}({params}) [{a.risk_level.value}]")
            lines.append(f"    {a.description}")

        return "\n".join(lines)

    async def execute(
        self,
        action_id: str,
        params: Dict[str, Any],
        agent_id: str,
        user_confirmed: bool = False,
    ) -> ActionResult:
        """Execute an action through the semantic bus.

        Flow:
        1. Find action schema
        2. Validate params against schema
        3. Check risk level → request confirmation if needed
        4. Check cooldown
        5. Execute handler
        6. Log execution
        7. Emit events
        """
        start = time.time()

        # 1. Find action
        action = self._actions.get(action_id)
        if not action:
            return ActionResult(
                success=False, action_id=action_id,
                error=f"Unknown action: {action_id}",
            )

        # 2. Validate params
        valid, errors = action.validate_params(params)
        if not valid:
            return ActionResult(
                success=False, action_id=action_id,
                error=f"Invalid params: {'; '.join(errors)}",
            )

        # 3. Check risk level
        if action.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL) and not user_confirmed:
            return ActionResult(
                success=False, action_id=action_id,
                error="requires_confirmation",
                data={
                    "risk_level": action.risk_level.value,
                    "action": action.to_dict(),
                    "params": params,
                    "message": f"{action.name} requires {'biometric' if action.risk_level == RiskLevel.CRITICAL else ''} confirmation",
                },
            )

        if action.risk_level == RiskLevel.MEDIUM and not user_confirmed:
            return ActionResult(
                success=False, action_id=action_id,
                error="requires_confirmation",
                data={
                    "risk_level": action.risk_level.value,
                    "action": action.to_dict(),
                    "params": params,
                },
            )

        # 4. Check cooldown
        last_exec = self._cooldowns.get(action_id, 0)
        if action.cooldown_seconds > 0 and (time.time() - last_exec) < action.cooldown_seconds:
            remaining = action.cooldown_seconds - (time.time() - last_exec)
            return ActionResult(
                success=False, action_id=action_id,
                error=f"Cooldown: {remaining:.0f}s remaining",
            )

        # 5. Execute
        handler = self._handlers.get(action_id)
        if not handler:
            return ActionResult(
                success=False, action_id=action_id,
                error=f"No handler registered for {action_id}",
            )

        try:
            result_data = await handler(params)
            elapsed = (time.time() - start) * 1000

            self._cooldowns[action_id] = time.time()

            result = ActionResult(
                success=True, action_id=action_id,
                data=result_data, execution_ms=elapsed,
            )

            # 6. Log
            self._execution_log.append({
                "action_id": action_id,
                "agent_id": agent_id,
                "params": params,
                "success": True,
                "execution_ms": elapsed,
                "timestamp": time.time(),
            })
            if len(self._execution_log) > 1000:
                self._execution_log = self._execution_log[-500:]

            # 7. Emit events
            await self._emit_event(f"{action.app_id}.action_executed", {
                "action_id": action_id,
                "agent_id": agent_id,
                "result": result_data,
            })

            logger.info(f"Action {action_id} executed by {agent_id} in {elapsed:.0f}ms")
            return result

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            logger.error(f"Action {action_id} failed: {e}")
            return ActionResult(
                success=False, action_id=action_id,
                error=str(e), execution_ms=elapsed,
            )

    def on_event(self, event_name: str, callback: Callable):
        """Subscribe to events from apps."""
        if event_name not in self._event_listeners:
            self._event_listeners[event_name] = []
        self._event_listeners[event_name].append(callback)

    async def _emit_event(self, event_name: str, data: dict):
        for cb in self._event_listeners.get(event_name, []):
            try:
                await cb(data)
            except Exception as e:
                logger.error(f"Event listener error ({event_name}): {e}")

    def get_execution_stats(self) -> dict:
        """Get stats about action executions."""
        if not self._execution_log:
            return {"total": 0, "avg_ms": 0, "apps": 0, "actions": 0}

        total = len(self._execution_log)
        avg_ms = sum(e["execution_ms"] for e in self._execution_log) / total
        unique_actions = len(set(e["action_id"] for e in self._execution_log))
        unique_apps = len(self._apps)

        return {
            "total_executions": total,
            "avg_execution_ms": round(avg_ms, 1),
            "registered_apps": unique_apps,
            "registered_actions": len(self._actions),
            "unique_actions_used": unique_actions,
        }

    def get_app_info(self) -> List[dict]:
        return [
            {
                "app_id": m.app_id,
                "name": m.name,
                "version": m.version,
                "actions": len(m.actions),
                "events": len(m.events),
            }
            for m in self._apps.values()
        ]
