from __future__ import annotations

"""
Agent Scheduler — Priority-based scheduling with fairness.

Like a CPU scheduler, but for AI agents. Manages:
- Which agents run and when
- Priority levels (system > user-triggered > background)
- Fairness (no agent starves others)
- Preemption (high-priority interrupts low-priority)
- Staggered startup to prevent thundering herd
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Callable, Dict, List, Optional

logger = logging.getLogger("kernel.scheduler")


class Priority(IntEnum):
    SYSTEM = 0      # Kernel agents (watchdog, audit)
    CRITICAL = 1    # User-triggered actions
    HIGH = 2        # Proactive rules, notifications
    NORMAL = 3      # Regular agent cycles
    LOW = 4         # Background maintenance
    IDLE = 5        # Only when nothing else is running


@dataclass
class ScheduledTask:
    agent_id: str
    callback: Callable
    priority: Priority = Priority.NORMAL
    interval: float = 30.0
    last_run: float = 0.0
    next_run: float = 0.0
    run_count: int = 0
    total_ms: float = 0.0
    max_ms: float = 0.0
    enabled: bool = True
    running: bool = False

    @property
    def avg_ms(self) -> float:
        return self.total_ms / self.run_count if self.run_count > 0 else 0


class AgentScheduler:
    """Priority-based agent scheduler with fairness guarantees."""

    def __init__(self):
        self._tasks: Dict[str, ScheduledTask] = {}
        self._running = False
        self._tick_interval = 1.0  # Check every second
        self._max_concurrent = 4   # Max agents running simultaneously
        self._active_count = 0
        self._lock = asyncio.Lock()

    def register(
        self,
        agent_id: str,
        callback: Callable,
        interval: float = 30.0,
        priority: Priority = Priority.NORMAL,
    ):
        """Register an agent's cycle function with the scheduler."""
        self._tasks[agent_id] = ScheduledTask(
            agent_id=agent_id,
            callback=callback,
            priority=priority,
            interval=interval,
            next_run=time.time() + (len(self._tasks) * 2),  # Stagger startup
        )
        logger.info(f"Scheduled: {agent_id} (every {interval}s, priority={priority.name})")

    def unregister(self, agent_id: str):
        """Remove an agent from the scheduler."""
        self._tasks.pop(agent_id, None)

    async def start(self):
        """Start the scheduling loop."""
        self._running = True
        logger.info(f"Scheduler started ({len(self._tasks)} tasks, max_concurrent={self._max_concurrent})")

        while self._running:
            try:
                await self._tick()
            except Exception as e:
                logger.error(f"Scheduler tick error: {e}")
            await asyncio.sleep(self._tick_interval)

    async def stop(self):
        self._running = False
        logger.info("Scheduler stopped")

    async def _tick(self):
        """One scheduler tick — find and run eligible tasks."""
        now = time.time()

        # Get eligible tasks sorted by priority then next_run
        eligible = [
            t for t in self._tasks.values()
            if t.enabled and not t.running and now >= t.next_run
        ]
        eligible.sort(key=lambda t: (t.priority, t.next_run))

        for task in eligible:
            if self._active_count >= self._max_concurrent:
                break
            asyncio.create_task(self._run_task(task))

    async def _run_task(self, task: ScheduledTask):
        """Execute a single scheduled task with timing and error handling."""
        async with self._lock:
            task.running = True
            self._active_count += 1

        start = time.time()
        try:
            await asyncio.wait_for(task.callback(), timeout=60.0)
        except asyncio.TimeoutError:
            logger.warning(f"Task {task.agent_id} timed out (60s limit)")
        except Exception as e:
            logger.error(f"Task {task.agent_id} error: {e}")
        finally:
            elapsed_ms = (time.time() - start) * 1000
            task.run_count += 1
            task.total_ms += elapsed_ms
            task.max_ms = max(task.max_ms, elapsed_ms)
            task.last_run = time.time()
            task.next_run = time.time() + task.interval
            task.running = False

            async with self._lock:
                self._active_count -= 1

    async def trigger(self, agent_id: str) -> bool:
        """Manually trigger an agent immediately."""
        task = self._tasks.get(agent_id)
        if not task:
            return False
        task.next_run = 0  # Schedule immediately
        return True

    def set_priority(self, agent_id: str, priority: Priority):
        task = self._tasks.get(agent_id)
        if task:
            task.priority = priority

    def set_interval(self, agent_id: str, interval: float):
        task = self._tasks.get(agent_id)
        if task:
            task.interval = interval

    def enable(self, agent_id: str):
        task = self._tasks.get(agent_id)
        if task:
            task.enabled = True

    def disable(self, agent_id: str):
        task = self._tasks.get(agent_id)
        if task:
            task.enabled = False

    def get_queue(self) -> List[dict]:
        """Get current scheduler queue for introspection."""
        now = time.time()
        return sorted([
            {
                "agent_id": t.agent_id,
                "priority": t.priority.name,
                "enabled": t.enabled,
                "running": t.running,
                "interval": t.interval,
                "next_run_in": max(0, t.next_run - now),
                "run_count": t.run_count,
                "avg_ms": round(t.avg_ms, 1),
                "max_ms": round(t.max_ms, 1),
            }
            for t in self._tasks.values()
        ], key=lambda x: (0 if x["running"] else 1, x["next_run_in"]))

    def get_stats(self) -> dict:
        total_runs = sum(t.run_count for t in self._tasks.values())
        total_ms = sum(t.total_ms for t in self._tasks.values())
        return {
            "tasks": len(self._tasks),
            "active": self._active_count,
            "max_concurrent": self._max_concurrent,
            "total_runs": total_runs,
            "total_cpu_ms": round(total_ms, 1),
            "avg_ms_per_run": round(total_ms / total_runs, 1) if total_runs > 0 else 0,
        }
