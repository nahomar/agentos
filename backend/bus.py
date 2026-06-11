from __future__ import annotations

"""
Message Bus — Unified interface for agent communication.

This module provides the public API that agents import from.
Internally delegates to the kernel IPCBroker for actual routing.
"""

import asyncio
import json
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Callable, Any, Optional, Dict, List, Tuple, Set


class MessageType(str, Enum):
    AGENT_UPDATE = "agent_update"
    AGENT_CHAT = "agent_chat"
    USER_ALERT = "user_alert"
    TASK_STATUS = "task_status"
    DISCOVERY = "discovery"
    SYSTEM = "system"


@dataclass
class Message:
    sender: str
    recipient: str  # agent name or "all"
    type: MessageType
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["type"] = self.type.value
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class MessageBus:
    """Unified message bus that delegates to kernel IPCBroker.

    Maintains backward compatibility with agent code while
    routing all messages through the kernel IPC system.
    """

    def __init__(self, max_history: int = 200):
        self.history: deque[Message] = deque(maxlen=max_history)
        self._ws_clients: set = set()
        self._lock = asyncio.Lock()
        self._ipc_broker = None  # Set by main.py after kernel init

    def set_ipc_broker(self, broker):
        """Wire the kernel IPCBroker as the backend for this bus."""
        self._ipc_broker = broker

    def register_ws(self, ws):
        self._ws_clients.add(ws)
        # Also register with IPCBroker if available
        if self._ipc_broker:
            self._ipc_broker.register_ws(ws)

    def unregister_ws(self, ws):
        self._ws_clients.discard(ws)
        if self._ipc_broker:
            self._ipc_broker.unregister_ws(ws)

    async def publish(self, message: Message):
        async with self._lock:
            self.history.append(message)

        # Route through IPCBroker if available
        if self._ipc_broker:
            from backend.kernel.ipc import IPCMessage, MessageType as KernelMsgType
            try:
                kernel_type = KernelMsgType(message.type.value)
            except ValueError:
                kernel_type = KernelMsgType.SYSTEM

            ipc_msg = IPCMessage(
                sender=message.sender,
                recipient=message.recipient,
                type=kernel_type,
                content=message.content,
                timestamp=message.timestamp,
                metadata=message.metadata,
            )
            await self._ipc_broker.publish(ipc_msg)
        else:
            # Fallback: direct WebSocket broadcast
            await self._broadcast_ws(message)

    async def _broadcast_ws(self, message: Message):
        if not self._ws_clients:
            return
        data = message.to_json()
        dead = set()
        for ws in self._ws_clients:
            try:
                await ws.send_text(data)
            except Exception:
                dead.add(ws)
        self._ws_clients -= dead

    def get_history(self, limit: int = 50, msg_type: Optional[MessageType] = None) -> List[dict]:
        msgs = list(self.history)
        if msg_type:
            msgs = [m for m in msgs if m.type == msg_type]
        return [m.to_dict() for m in msgs[-limit:]]
