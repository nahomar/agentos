from __future__ import annotations

"""
Agent Process Manager — Real subprocess isolation.

Each agent runs in its own asyncio task with exception boundaries.
If one agent crashes, others keep running. The process manager
handles lifecycle, restart, and resource tracking.

Future: migrate to actual OS subprocesses with socket IPC.
Currently uses task-level isolation with error boundaries.
"""

import asyncio
import logging
import time
import traceback
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

logger = logging.getLogger("kernel.process")


@dataclass
class AgentProcess:
    """Represents an isolated agent process."""
    agent_id: str
    agent_ref: object  # The BaseAgent instance
    task: Optional[asyncio.Task] = None
    pid: int = 0  # Internal process ID
    status: str = "created"  # created, running, stopped, crashed, restarting
    started_at: float = 0.0
    crash_count: int = 0
    last_crash: float = 0.0
    last_error: str = ""
    max_restarts: int = 10
    restart_delay: float = 5.0

    @property
    def uptime(self) -> float:
        if self.started_at > 0:
            return time.time() - self.started_at
        return 0


class ProcessManager:
    """Manages agent processes with isolation and auto-restart."""

    def __init__(self):
        self._processes: Dict[str, AgentProcess] = {}
        self._pid_counter = 1000
        self._running = False
        self._on_crash_callbacks: List[Callable] = []
        self._heartbeat_callback: Optional[Callable] = None
        self._governor = None  # N3: ResourceGovernor

    def set_heartbeat_callback(self, callback: Callable):
        """Set callback called on every successful agent cycle (for watchdog)."""
        self._heartbeat_callback = callback

    def set_governor(self, governor):
        """N3: Wire resource governor for CPU/memory tracking."""
        self._governor = governor

    def register(self, agent_id: str, agent_ref) -> AgentProcess:
        """Register an agent for process management."""
        self._pid_counter += 1
        proc = AgentProcess(
            agent_id=agent_id,
            agent_ref=agent_ref,
            pid=self._pid_counter,
        )
        self._processes[agent_id] = proc
        return proc

    def on_crash(self, callback: Callable):
        """Register a callback for agent crashes."""
        self._on_crash_callbacks.append(callback)

    async def start_all(self, cycle_interval: int = 30):
        """Start all registered agent processes with staggered startup."""
        self._running = True
        for i, (agent_id, proc) in enumerate(self._processes.items()):
            await self._start_process(proc, cycle_interval)
            await asyncio.sleep(2)  # Stagger

        logger.info(f"Process manager: {len(self._processes)} agents started")

    async def _start_process(self, proc: AgentProcess, cycle_interval: int = 30):
        """Start a single agent process with error boundary."""
        async def _isolated_run():
            proc.status = "running"
            proc.started_at = time.time()
            agent = proc.agent_ref
            logger.info(f"[PID {proc.pid}] {proc.agent_id} started")

            while self._running and proc.status == "running":
                # N3: Check governor throttle before running
                if self._governor and self._governor.is_throttled(proc.agent_id):
                    await asyncio.sleep(5)
                    continue

                try:
                    start_time = time.time()
                    agent.status = "working"
                    await asyncio.wait_for(agent.run_cycle(), timeout=60.0)
                    agent.status = "idle"
                    elapsed_ms = (time.time() - start_time) * 1000

                    # N3: Record CPU usage with governor
                    if self._governor:
                        self._governor.record_cpu(proc.agent_id, elapsed_ms)

                    # M3: Report heartbeat to watchdog on success
                    if self._heartbeat_callback:
                        self._heartbeat_callback(proc.agent_id)

                except asyncio.TimeoutError:
                    logger.warning(f"[PID {proc.pid}] {proc.agent_id} cycle timeout (60s)")
                    agent.status = "idle"

                except asyncio.CancelledError:
                    break

                except Exception as e:
                    proc.crash_count += 1
                    proc.last_crash = time.time()
                    proc.last_error = str(e)
                    logger.error(f"[PID {proc.pid}] {proc.agent_id} CRASHED: {e}")

                    # Notify crash callbacks
                    for cb in self._on_crash_callbacks:
                        try:
                            await cb(proc.agent_id, str(e))
                        except Exception:
                            pass

                    # Error boundary — don't let the crash propagate
                    agent.status = "error"
                    if proc.crash_count >= proc.max_restarts:
                        proc.status = "dead"
                        logger.error(f"[PID {proc.pid}] {proc.agent_id} exceeded max restarts, marking DEAD")
                        return

                    # Brief cooldown before retrying
                    await asyncio.sleep(min(proc.restart_delay * proc.crash_count, 30))
                    agent.status = "idle"
                    continue

                await asyncio.sleep(cycle_interval)

            proc.status = "stopped"
            logger.info(f"[PID {proc.pid}] {proc.agent_id} stopped")

        # Broadcast initial status
        try:
            await proc.agent_ref.broadcast_status("waking up...")
        except Exception:
            pass

        proc.task = asyncio.create_task(_isolated_run())

    async def stop_all(self):
        """Stop all agent processes."""
        self._running = False
        for proc in self._processes.values():
            await self.stop_process(proc.agent_id)
        logger.info("All agent processes stopped")

    async def stop_process(self, agent_id: str):
        """Stop a single agent process."""
        proc = self._processes.get(agent_id)
        if not proc:
            return
        proc.status = "stopped"
        if proc.task and not proc.task.done():
            proc.task.cancel()
            try:
                await asyncio.wait_for(proc.task, timeout=5)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        try:
            await proc.agent_ref.broadcast_status("going to sleep 💤")
        except Exception:
            pass

    async def restart_process(self, agent_id: str, cycle_interval: int = 30):
        """Restart a crashed or stopped agent."""
        proc = self._processes.get(agent_id)
        if not proc:
            return False
        await self.stop_process(agent_id)
        proc.status = "restarting"
        proc.crash_count = 0
        await self._start_process(proc, cycle_interval)
        return True

    def get_process_table(self) -> List[dict]:
        """Get process table — like `ps aux` for agents."""
        return [
            {
                "pid": p.pid,
                "agent_id": p.agent_id,
                "status": p.status,
                "uptime": round(p.uptime, 1),
                "crash_count": p.crash_count,
                "last_error": p.last_error[:100] if p.last_error else "",
            }
            for p in self._processes.values()
        ]

    def get_stats(self) -> dict:
        statuses = [p.status for p in self._processes.values()]
        return {
            "total_processes": len(self._processes),
            "running": statuses.count("running"),
            "stopped": statuses.count("stopped"),
            "crashed": statuses.count("crashed"),
            "dead": statuses.count("dead"),
            "total_crashes": sum(p.crash_count for p in self._processes.values()),
        }
