from __future__ import annotations

"""
IPC Broker — Inter-Process Communication for isolated agents.

Agents run in separate processes. The IPC broker routes messages
between them using async queues (in-process mode) or Unix sockets
(subprocess mode). This replaces the in-memory MessageBus for
cross-process communication.

Message format is the same as the existing bus protocol:
{sender, recipient, type, content, timestamp, metadata}
"""

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger("kernel.ipc")


class MessageType(str, Enum):
    AGENT_UPDATE = "agent_update"
    AGENT_CHAT = "agent_chat"
    USER_ALERT = "user_alert"
    TASK_STATUS = "task_status"
    DISCOVERY = "discovery"
    SYSTEM = "system"
    KERNEL = "kernel"          # Kernel-level messages
    CHECKPOINT = "checkpoint"  # State checkpoint events
    AUDIT = "audit"            # Audit log entries


@dataclass
class IPCMessage:
    sender: str
    recipient: str  # agent name, "all", "kernel", "user"
    type: MessageType
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    msg_id: str = ""  # Unique message ID for dedup

    def to_dict(self) -> dict:
        d = asdict(self)
        d["type"] = self.type.value
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, d: dict) -> IPCMessage:
        d["type"] = MessageType(d.get("type", "system"))
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class IPCBroker:
    """Central message broker for inter-agent communication.

    Supports both in-process (async queues) and cross-process
    (Unix socket) communication patterns.
    """

    def __init__(self, max_history: int = 500):
        self.history: deque[IPCMessage] = deque(maxlen=max_history)
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)  # agent_name -> callbacks
        self._type_subscribers: Dict[MessageType, List[Callable]] = defaultdict(list)
        self._global_subscribers: List[Callable] = []  # Receive ALL messages
        self._ws_clients: Set = set()
        self._lock = asyncio.Lock()
        self._msg_counter = 0
        self._stats = {
            "messages_total": 0,
            "messages_delivered": 0,
            "messages_dropped": 0,
        }

    def subscribe(self, agent_name: str, callback: Callable):
        """Subscribe an agent to messages addressed to it."""
        self._subscribers[agent_name].append(callback)

    def subscribe_type(self, msg_type: MessageType, callback: Callable):
        """Subscribe to all messages of a specific type."""
        self._type_subscribers[msg_type].append(callback)

    def subscribe_all(self, callback: Callable):
        """Subscribe to ALL messages (for monitoring/audit)."""
        self._global_subscribers.append(callback)

    def register_ws(self, ws):
        self._ws_clients.add(ws)

    def unregister_ws(self, ws):
        self._ws_clients.discard(ws)

    async def publish(self, message: IPCMessage):
        """Publish a message through the broker."""
        async with self._lock:
            self._msg_counter += 1
            if not message.msg_id:
                message.msg_id = f"{message.sender}:{self._msg_counter}"
            self.history.append(message)
            self._stats["messages_total"] += 1

        delivered = 0

        # Route to specific recipient
        if message.recipient != "all" and message.recipient != "user":
            for cb in self._subscribers.get(message.recipient, []):
                try:
                    await cb(message)
                    delivered += 1
                except Exception as e:
                    logger.error(f"IPC delivery error to {message.recipient}: {e}")

        # Route to type subscribers
        for cb in self._type_subscribers.get(message.type, []):
            try:
                await cb(message)
                delivered += 1
            except Exception:
                pass

        # Route to global subscribers
        for cb in self._global_subscribers:
            try:
                await cb(message)
                delivered += 1
            except Exception:
                pass

        # Broadcast to WebSocket clients
        await self._broadcast_ws(message)

        self._stats["messages_delivered"] += delivered

    async def _broadcast_ws(self, message: IPCMessage):
        if not self._ws_clients:
            return
        # Convert to legacy bus format for frontend compatibility
        data = json.dumps({
            "sender": message.sender,
            "recipient": message.recipient,
            "type": message.type.value,
            "content": message.content,
            "timestamp": message.timestamp,
            "metadata": message.metadata,
        })
        dead = set()
        for ws in self._ws_clients:
            try:
                await ws.send_text(data)
            except Exception:
                dead.add(ws)
        self._ws_clients -= dead

    def get_history(self, limit: int = 50, msg_type: str = None) -> List[dict]:
        msgs = list(self.history)
        if msg_type:
            msgs = [m for m in msgs if m.type.value == msg_type]
        return [m.to_dict() for m in msgs[-limit:]]

    def get_stats(self) -> dict:
        return {
            **self._stats,
            "subscribers": sum(len(v) for v in self._subscribers.values()),
            "type_subscribers": sum(len(v) for v in self._type_subscribers.values()),
            "global_subscribers": len(self._global_subscribers),
            "ws_clients": len(self._ws_clients),
            "history_size": len(self.history),
        }
