from __future__ import annotations

"""
Watchdog — Crash detection and auto-restart for agents.

Monitors agent health and restarts crashed agents automatically.
Like a kernel watchdog timer that prevents system hangs.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

logger = logging.getLogger("kernel.watchdog")


@dataclass
class AgentHealth:
    agent_id: str
    last_heartbeat: float = field(default_factory=time.time)
    consecutive_failures: int = 0
    total_restarts: int = 0
    status: str = "healthy"  # healthy, warning, critical, dead
    max_failures_before_kill: int = 5


class Watchdog:
    """Monitors agent health and auto-restarts failed agents."""

    def __init__(self, heartbeat_timeout: float = 120.0):
        self._agents: Dict[str, AgentHealth] = {}
        self._restart_callbacks: Dict[str, Callable] = {}
        self._heartbeat_timeout = heartbeat_timeout
        self._running = False
        self._check_interval = 10.0

    def register(self, agent_id: str, restart_callback: Callable = None):
        """Register an agent for monitoring."""
        self._agents[agent_id] = AgentHealth(agent_id=agent_id)
        if restart_callback:
            self._restart_callbacks[agent_id] = restart_callback
        logger.debug(f"Watchdog monitoring: {agent_id}")

    def heartbeat(self, agent_id: str):
        """Record a heartbeat from an agent (called each successful cycle)."""
        health = self._agents.get(agent_id)
        if health:
            health.last_heartbeat = time.time()
            health.consecutive_failures = 0
            if health.status != "healthy":
                logger.info(f"Watchdog: {agent_id} recovered → healthy")
                health.status = "healthy"

    def report_failure(self, agent_id: str, error: str = ""):
        """Report an agent failure."""
        health = self._agents.get(agent_id)
        if health:
            health.consecutive_failures += 1
            if health.consecutive_failures >= 3:
                health.status = "critical"
            else:
                health.status = "warning"
            logger.warning(f"Watchdog: {agent_id} failure #{health.consecutive_failures}: {error}")

    async def start(self):
        """Start the watchdog monitoring loop."""
        self._running = True
        logger.info(f"Watchdog started (timeout={self._heartbeat_timeout}s, monitoring {len(self._agents)} agents)")

        while self._running:
            try:
                await self._check_health()
            except Exception as e:
                logger.error(f"Watchdog check error: {e}")
            await asyncio.sleep(self._check_interval)

    async def stop(self):
        self._running = False

    async def _check_health(self):
        now = time.time()

        for agent_id, health in self._agents.items():
            elapsed = now - health.last_heartbeat

            if elapsed > self._heartbeat_timeout:
                if health.status != "dead":
                    health.status = "critical"
                    logger.warning(f"Watchdog: {agent_id} missed heartbeat ({elapsed:.0f}s)")

                    if health.consecutive_failures >= health.max_failures_before_kill:
                        health.status = "dead"
                        logger.error(f"Watchdog: {agent_id} declared DEAD after {health.consecutive_failures} failures")
                    else:
                        await self._attempt_restart(agent_id, health)

    async def _attempt_restart(self, agent_id: str, health: AgentHealth):
        """Attempt to restart a failed agent."""
        callback = self._restart_callbacks.get(agent_id)
        if not callback:
            return

        health.total_restarts += 1
        logger.info(f"Watchdog: restarting {agent_id} (restart #{health.total_restarts})")

        try:
            await callback()
            health.last_heartbeat = time.time()
            health.status = "healthy"
            health.consecutive_failures = 0
            logger.info(f"Watchdog: {agent_id} restarted successfully")
        except Exception as e:
            health.consecutive_failures += 1
            logger.error(f"Watchdog: {agent_id} restart failed: {e}")

    def get_health(self) -> List[dict]:
        now = time.time()
        return [
            {
                "agent_id": h.agent_id,
                "status": h.status,
                "last_heartbeat_ago": round(now - h.last_heartbeat, 1),
                "consecutive_failures": h.consecutive_failures,
                "total_restarts": h.total_restarts,
            }
            for h in self._agents.values()
        ]

    def get_stats(self) -> dict:
        statuses = [h.status for h in self._agents.values()]
        return {
            "agents_monitored": len(self._agents),
            "healthy": statuses.count("healthy"),
            "warning": statuses.count("warning"),
            "critical": statuses.count("critical"),
            "dead": statuses.count("dead"),
            "total_restarts": sum(h.total_restarts for h in self._agents.values()),
        }
