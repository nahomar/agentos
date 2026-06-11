from __future__ import annotations

"""
Agent Namespace — Virtual filesystem for agent introspection.

Inspired by Plan 9's "everything is a file" philosophy, but for agents:
"everything is an endpoint."

/agents/{id}/status     → agent status
/agents/{id}/findings   → agent discoveries
/kernel/scheduler/queue → scheduling queue
/kernel/audit/log       → audit trail
/context/current        → user context
"""

import logging
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger("kernel.namespace")


class AgentNamespace:
    """Maps path-like routes to data handlers for agent introspection."""

    def __init__(self):
        self._handlers: Dict[str, Callable] = {}

    def mount(self, path: str, handler: Callable):
        """Mount a handler at a namespace path.

        Handler signature: async (params: dict) -> Any
        """
        self._handlers[path] = handler
        logger.debug(f"Mounted: {path}")

    async def resolve(self, path: str, params: dict = None) -> Any:
        """Resolve a namespace path and return the data."""
        # Try exact match first
        handler = self._handlers.get(path)
        if handler:
            return await handler(params or {})

        # Try pattern match (e.g., /agents/{id}/status)
        for pattern, handler in self._handlers.items():
            if self._matches(pattern, path):
                extracted = self._extract_params(pattern, path)
                merged = {**(params or {}), **extracted}
                return await handler(merged)

        return {"error": f"Not found: {path}"}

    def _matches(self, pattern: str, path: str) -> bool:
        """Check if a path matches a pattern with {param} placeholders."""
        p_parts = pattern.strip("/").split("/")
        path_parts = path.strip("/").split("/")

        if len(p_parts) != len(path_parts):
            return False

        for pp, pathp in zip(p_parts, path_parts):
            if pp.startswith("{") and pp.endswith("}"):
                continue
            if pp != pathp:
                return False

        return True

    def _extract_params(self, pattern: str, path: str) -> dict:
        """Extract parameters from a path matching a pattern."""
        p_parts = pattern.strip("/").split("/")
        path_parts = path.strip("/").split("/")
        params = {}

        for pp, pathp in zip(p_parts, path_parts):
            if pp.startswith("{") and pp.endswith("}"):
                key = pp[1:-1]
                params[key] = pathp

        return params

    def list_paths(self) -> list:
        """List all mounted namespace paths."""
        return sorted(self._handlers.keys())


def register_default_namespace(
    ns: AgentNamespace,
    orchestrator,
    scheduler,
    governor,
    watchdog,
    audit_log,
    checkpoint_mgr,
    context_engine,
    semantic_bus,
    verification_layer,
    identity_vault,
    ipc_broker,
):
    """Register all default namespace handlers."""

    # === Agent namespace ===
    async def agent_status(p):
        agent = orchestrator.agents.get(p.get("id", ""))
        if not agent:
            return {"error": "Agent not found"}
        return agent.get_info()

    async def agent_list(p):
        return orchestrator.get_agents_info()

    async def agent_findings(p):
        from backend.database import get_findings
        return get_findings(limit=20, agent=p.get("id"))

    ns.mount("/agents", agent_list)
    ns.mount("/agents/{id}/status", agent_status)
    ns.mount("/agents/{id}/findings", agent_findings)

    # === Kernel namespace ===
    async def kernel_scheduler_queue(p):
        return scheduler.get_queue()

    async def kernel_scheduler_stats(p):
        return scheduler.get_stats()

    async def kernel_governor_usage(p):
        return governor.get_all_usage()

    async def kernel_governor_limits(p):
        return governor.get_limits()

    async def kernel_watchdog_health(p):
        return watchdog.get_health()

    async def kernel_watchdog_stats(p):
        return watchdog.get_stats()

    async def kernel_audit_log(p):
        return audit_log.query(limit=int(p.get("limit", 50)))

    async def kernel_audit_stats(p):
        return audit_log.get_stats()

    async def kernel_checkpoint_list(p):
        return checkpoint_mgr.list_checkpoints()

    async def kernel_ipc_stats(p):
        return ipc_broker.get_stats()

    async def kernel_ipc_history(p):
        return ipc_broker.get_history(limit=int(p.get("limit", 20)))

    ns.mount("/kernel/scheduler/queue", kernel_scheduler_queue)
    ns.mount("/kernel/scheduler/stats", kernel_scheduler_stats)
    ns.mount("/kernel/governor/usage", kernel_governor_usage)
    ns.mount("/kernel/governor/limits", kernel_governor_limits)
    ns.mount("/kernel/watchdog/health", kernel_watchdog_health)
    ns.mount("/kernel/watchdog/stats", kernel_watchdog_stats)
    ns.mount("/kernel/audit/log", kernel_audit_log)
    ns.mount("/kernel/audit/stats", kernel_audit_stats)
    ns.mount("/kernel/checkpoints", kernel_checkpoint_list)
    ns.mount("/kernel/ipc/stats", kernel_ipc_stats)
    ns.mount("/kernel/ipc/history", kernel_ipc_history)

    # === Context namespace ===
    async def context_current(p):
        return context_engine.get_context_dict()

    async def context_patterns(p):
        return {
            "habits": context_engine.patterns.get_habits(),
            "predictions": context_engine.patterns.predict(context_engine.get_context_dict()),
            "stats": context_engine.patterns.get_stats(),
        }

    ns.mount("/context/current", context_current)
    ns.mount("/context/patterns", context_patterns)

    # === Services namespace ===
    async def bus_actions(p):
        return [a.to_dict() for a in semantic_bus.get_available_actions()]

    async def bus_apps(p):
        return semantic_bus.get_app_info()

    async def bus_stats(p):
        return semantic_bus.get_execution_stats()

    async def verify_stats(p):
        return verification_layer.get_stats()

    async def vault_services(p):
        return identity_vault.list_services()

    async def vault_stats(p):
        return identity_vault.get_stats()

    ns.mount("/services/bus/actions", bus_actions)
    ns.mount("/services/bus/apps", bus_apps)
    ns.mount("/services/bus/stats", bus_stats)
    ns.mount("/services/verification/stats", verify_stats)
    ns.mount("/services/vault/services", vault_services)
    ns.mount("/services/vault/stats", vault_stats)

    logger.info(f"Namespace initialized: {len(ns.list_paths())} paths mounted")
