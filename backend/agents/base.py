from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod

from backend.bus import MessageBus, Message, MessageType
from backend.memory import SharedMemory

logger = logging.getLogger("agents")


class BaseAgent(ABC):
    name: str = "Agent"
    emoji: str = "🤖"
    color: str = "#FFFFFF"
    app_name: str = "Unknown"
    personality: str = "helpful"

    def __init__(self, bus: MessageBus, memory: SharedMemory, config: dict | None = None):
        self.bus = bus
        self.memory = memory
        self.config = config or {}
        self.brain = None          # Set by orchestrator — shared AI reasoning
        self.semantic_bus = None   # Set by orchestrator — typed action execution
        self.audit_log = None      # Set by orchestrator — action logging
        self.checkpoint_mgr = None # Set by orchestrator — state persistence
        self.status = "idle"
        self.current_task = ""
        self._running = False
        self._cycle_interval = self.config.get("cycle_interval", 30)
        self._state: dict = {}     # Checkpointable state

    @property
    def has_api_key(self) -> bool:
        return False

    async def start(self, cycle_interval: int | None = None):
        if cycle_interval:
            self._cycle_interval = cycle_interval
        self._running = True
        logger.info(f"{self.emoji} {self.name} starting up")
        await self.broadcast_status("waking up...")

        while self._running:
            try:
                self.status = "working"
                await self.run_cycle()
                self.status = "idle"
            except Exception as e:
                logger.error(f"{self.name} cycle error: {e}")
                self.status = "error"
                await self.broadcast_status(f"hit a snag: {e}")

            await asyncio.sleep(self._cycle_interval)

    async def stop(self):
        self._running = False
        self.status = "offline"
        await self.broadcast_status("going to sleep 💤")
        logger.info(f"{self.emoji} {self.name} stopped")

    @abstractmethod
    async def run_cycle(self):
        """One cycle of the agent's work."""
        pass

    async def send_message(self, recipient: str, content: str, msg_type: MessageType = MessageType.AGENT_CHAT):
        msg = Message(
            sender=self.name,
            recipient=recipient,
            type=msg_type,
            content=content,
            metadata={"emoji": self.emoji, "color": self.color, "app": self.app_name},
        )
        await self.bus.publish(msg)

    async def broadcast_status(self, status_text: str):
        self.current_task = status_text
        await self.memory.update_agent_state(self.name, {
            "status": self.status,
            "current_task": status_text,
            "emoji": self.emoji,
            "color": self.color,
            "app": self.app_name,
        })
        msg = Message(
            sender=self.name,
            recipient="all",
            type=MessageType.AGENT_UPDATE,
            content=status_text,
            metadata={"emoji": self.emoji, "color": self.color, "app": self.app_name},
        )
        await self.bus.publish(msg)

    async def report_finding(self, finding: str, category: str = "general"):
        await self.memory.store_finding(self.name, finding, category)
        msg = Message(
            sender=self.name,
            recipient="all",
            type=MessageType.DISCOVERY,
            content=finding,
            metadata={"emoji": self.emoji, "color": self.color, "category": category, "app": self.app_name},
        )
        await self.bus.publish(msg)

    async def alert_user(self, alert: str):
        msg = Message(
            sender=self.name,
            recipient="user",
            type=MessageType.USER_ALERT,
            content=alert,
            metadata={"emoji": self.emoji, "color": self.color, "app": self.app_name},
        )
        await self.bus.publish(msg)

    async def execute_action(self, action_id: str, params: dict = None) -> dict | None:
        """Execute a typed action through the Semantic Bus.

        This is the OS way — agents call actions, not raw APIs.
        Example: self.execute_action("spotify.play_track", {"query": "lo-fi beats"})
        """
        if not self.semantic_bus:
            return None

        from backend.semantic_bus.schema import ActionResult
        result = await self.semantic_bus.execute(
            action_id=action_id,
            params=params or {},
            agent_id=self.name,
        )

        # Log to audit
        if self.audit_log:
            self.audit_log.log(
                agent_id=self.name,
                action=action_id,
                action_type="semantic_bus",
                params=params,
                result="success" if result.success else result.error,
                duration_ms=result.execution_ms,
            )

        if result.success:
            return result.data
        return None

    async def checkpoint(self):
        """Save agent state for crash recovery / cross-device migration."""
        if self.checkpoint_mgr:
            state = {
                "name": self.name,
                "status": self.status,
                "current_task": self.current_task,
                "custom_state": self._state,
                "cycle_interval": self._cycle_interval,
            }
            self.checkpoint_mgr.save(self.name, state)

    async def restore_state(self):
        """Restore agent state from last checkpoint."""
        if self.checkpoint_mgr:
            state = self.checkpoint_mgr.restore(self.name)
            if state:
                self._state = state.get("custom_state", {})
                return True
        return False

    async def think(self, task: str, context: str = "") -> str | None:
        """Use the shared AI brain to think. Returns None if no AI available."""
        if not self.brain:
            return None

        interests = await self.memory.get_interests()
        findings = await self.memory.get_findings(limit=5)
        findings_str = "\n".join(f"- [{f['agent']}] {f['content'][:100]}" for f in findings) if findings else ""

        return await self.brain.think(
            agent_name=self.name,
            agent_personality=self.personality,
            task=task,
            context=context,
            recent_findings=findings_str,
            user_interests=", ".join(interests),
        )

    def get_info(self) -> dict:
        return {
            "name": self.name,
            "emoji": self.emoji,
            "color": self.color,
            "app": self.app_name,
            "status": self.status,
            "current_task": self.current_task,
            "has_api_key": self.has_api_key,
            "personality": self.personality,
        }
