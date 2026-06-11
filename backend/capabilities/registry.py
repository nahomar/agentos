from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from backend.capabilities.permissions import PermissionStore, PermissionLevel
from backend.bus import MessageBus, Message, MessageType

logger = logging.getLogger("capabilities")


@dataclass
class CapabilityResult:
    success: bool
    data: Any = None
    error: str = ""


@dataclass
class CapabilityInfo:
    id: str
    name: str
    description: str
    category: str
    available: bool  # True if provider is configured


class CapabilityProvider:
    """Base class for capability providers."""

    id: str = ""
    name: str = ""
    description: str = ""
    category: str = ""

    def __init__(self, config: dict):
        self.config = config

    @property
    def available(self) -> bool:
        return True

    async def execute(self, params: dict) -> CapabilityResult:
        return CapabilityResult(success=False, error="Not implemented")

    def info(self) -> CapabilityInfo:
        return CapabilityInfo(
            id=self.id,
            name=self.name,
            description=self.description,
            category=self.category,
            available=self.available,
        )


class CapabilityRegistry:
    """Central registry of all capabilities agents can use."""

    def __init__(self, bus: MessageBus, config: dict):
        self.bus = bus
        self.config = config
        self.permissions = PermissionStore()
        self._providers: Dict[str, CapabilityProvider] = {}
        self._pending_permissions: Dict[str, asyncio.Future] = {}

    def register(self, provider: CapabilityProvider):
        self._providers[provider.id] = provider
        logger.info(f"Registered capability: {provider.id} ({'available' if provider.available else 'unavailable'})")

    async def execute(
        self,
        capability_id: str,
        params: dict,
        requesting_agent: str,
    ) -> CapabilityResult:
        provider = self._providers.get(capability_id)
        if not provider:
            return CapabilityResult(success=False, error=f"Unknown capability: {capability_id}")

        if not provider.available:
            return CapabilityResult(success=False, error=f"Capability {capability_id} not configured")

        # Check permissions
        granted = self.permissions.check(requesting_agent, capability_id)
        if granted is False:
            return CapabilityResult(success=False, error="Permission denied")

        if granted is None:
            # Need to ask user
            granted = await self._request_permission(requesting_agent, capability_id, params)
            if not granted:
                return CapabilityResult(success=False, error="Permission denied by user")

        try:
            result = await provider.execute(params)
            logger.info(f"Capability {capability_id} executed by {requesting_agent}: {'success' if result.success else result.error}")
            return result
        except Exception as e:
            logger.error(f"Capability {capability_id} error: {e}")
            return CapabilityResult(success=False, error=str(e))

    async def _request_permission(self, agent_id: str, capability_id: str, params: dict) -> bool:
        request_id = str(uuid.uuid4())[:8]

        # Send permission request to frontend via WebSocket
        await self.bus.publish(Message(
            sender="System",
            recipient="user",
            type=MessageType.SYSTEM,
            content=f"Permission request: {agent_id} wants to use {capability_id}",
            metadata={
                "type": "permission_request",
                "request_id": request_id,
                "agent": agent_id,
                "capability": capability_id,
                "params": params,
                "emoji": "🔐",
                "color": "#FFD700",
            },
        ))

        # Wait for response (with timeout)
        future = asyncio.get_event_loop().create_future()
        self._pending_permissions[request_id] = future

        try:
            granted = await asyncio.wait_for(future, timeout=30.0)
            level = self.permissions.get_level(capability_id)
            if level == PermissionLevel.ASK_ONCE:
                self.permissions.grant(agent_id, capability_id, granted)
            return granted
        except asyncio.TimeoutError:
            logger.info(f"Permission request {request_id} timed out")
            return False
        finally:
            self._pending_permissions.pop(request_id, None)

    def resolve_permission(self, request_id: str, granted: bool):
        future = self._pending_permissions.get(request_id)
        if future and not future.done():
            future.set_result(granted)

    def list_capabilities(self) -> List[dict]:
        return [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "category": p.category,
                "available": p.available,
            }
            for p in self._providers.values()
        ]
