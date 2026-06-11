from __future__ import annotations

"""
Resource Governor — Enforces CPU, memory, and network quotas per agent.

Prevents a single runaway agent from consuming all system resources.
Like Linux cgroups, but for agent processes.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger("kernel.governor")


@dataclass
class ResourceQuota:
    """Resource limits for an agent."""
    max_cpu_ms_per_cycle: float = 5000    # Max CPU time per cycle (5s default)
    max_memory_mb: float = 100            # Max memory usage (MB)
    max_api_calls_per_minute: int = 30    # Max external API calls
    max_messages_per_minute: int = 20     # Max IPC messages
    max_findings_per_hour: int = 100      # Max discoveries/findings
    throttle_on_exceed: bool = True       # Throttle or kill on exceed


@dataclass
class ResourceUsage:
    """Current resource usage for an agent."""
    cpu_ms_total: float = 0.0
    cpu_ms_last_cycle: float = 0.0
    api_calls_this_minute: int = 0
    messages_this_minute: int = 0
    findings_this_hour: int = 0
    throttled: bool = False
    last_reset: float = field(default_factory=time.time)
    violations: int = 0


class ResourceGovernor:
    """Enforces resource quotas per agent."""

    def __init__(self):
        self._quotas: Dict[str, ResourceQuota] = {}
        self._usage: Dict[str, ResourceUsage] = {}
        self._default_quota = ResourceQuota()

    def set_quota(self, agent_id: str, quota: ResourceQuota):
        """Set resource limits for an agent."""
        self._quotas[agent_id] = quota

    def get_quota(self, agent_id: str) -> ResourceQuota:
        return self._quotas.get(agent_id, self._default_quota)

    def get_usage(self, agent_id: str) -> ResourceUsage:
        if agent_id not in self._usage:
            self._usage[agent_id] = ResourceUsage()
        return self._usage[agent_id]

    def record_cpu(self, agent_id: str, ms: float):
        """Record CPU time used by an agent cycle."""
        usage = self.get_usage(agent_id)
        usage.cpu_ms_total += ms
        usage.cpu_ms_last_cycle = ms

        quota = self.get_quota(agent_id)
        if ms > quota.max_cpu_ms_per_cycle:
            usage.violations += 1
            logger.warning(f"Governor: {agent_id} exceeded CPU limit ({ms:.0f}ms > {quota.max_cpu_ms_per_cycle}ms)")
            if quota.throttle_on_exceed:
                usage.throttled = True

    def record_api_call(self, agent_id: str) -> bool:
        """Record an API call. Returns False if rate limit exceeded."""
        usage = self.get_usage(agent_id)
        self._maybe_reset_minute(usage)

        quota = self.get_quota(agent_id)
        usage.api_calls_this_minute += 1

        if usage.api_calls_this_minute > quota.max_api_calls_per_minute:
            usage.violations += 1
            logger.warning(f"Governor: {agent_id} exceeded API rate limit")
            return False
        return True

    def record_message(self, agent_id: str) -> bool:
        """Record an IPC message. Returns False if rate limit exceeded."""
        usage = self.get_usage(agent_id)
        self._maybe_reset_minute(usage)

        quota = self.get_quota(agent_id)
        usage.messages_this_minute += 1

        if usage.messages_this_minute > quota.max_messages_per_minute:
            usage.violations += 1
            return False
        return True

    def record_finding(self, agent_id: str) -> bool:
        """Record a finding/discovery. Returns False if rate limit exceeded."""
        usage = self.get_usage(agent_id)
        quota = self.get_quota(agent_id)
        usage.findings_this_hour += 1

        if usage.findings_this_hour > quota.max_findings_per_hour:
            usage.violations += 1
            return False
        return True

    def is_throttled(self, agent_id: str) -> bool:
        """Check if an agent is currently throttled."""
        usage = self.get_usage(agent_id)
        if usage.throttled:
            # Auto-unthrottle after 30 seconds
            if time.time() - usage.last_reset > 30:
                usage.throttled = False
                return False
            return True
        return False

    def _maybe_reset_minute(self, usage: ResourceUsage):
        """Reset per-minute counters if a minute has passed."""
        if time.time() - usage.last_reset > 60:
            usage.api_calls_this_minute = 0
            usage.messages_this_minute = 0
            usage.last_reset = time.time()

    def get_all_usage(self) -> Dict[str, dict]:
        """Get resource usage for all agents."""
        return {
            agent_id: {
                "cpu_ms_total": round(u.cpu_ms_total, 1),
                "cpu_ms_last_cycle": round(u.cpu_ms_last_cycle, 1),
                "api_calls_this_minute": u.api_calls_this_minute,
                "messages_this_minute": u.messages_this_minute,
                "findings_this_hour": u.findings_this_hour,
                "throttled": u.throttled,
                "violations": u.violations,
            }
            for agent_id, u in self._usage.items()
        }

    def get_limits(self) -> Dict[str, dict]:
        """Get configured limits for all agents."""
        all_agents = set(list(self._quotas.keys()) + list(self._usage.keys()))
        return {
            agent_id: {
                "max_cpu_ms": q.max_cpu_ms_per_cycle,
                "max_api_calls_per_min": q.max_api_calls_per_minute,
                "max_messages_per_min": q.max_messages_per_minute,
                "max_findings_per_hour": q.max_findings_per_hour,
            }
            for agent_id in all_agents
            for q in [self.get_quota(agent_id)]
        }
