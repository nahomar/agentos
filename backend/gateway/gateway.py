from __future__ import annotations

"""
Agent Gateway — Multi-interface message router.

Routes messages between users and the AgentOS kernel through
multiple channels simultaneously. Like OpenClaw's gateway but
supporting our kernel architecture.

Channels: Web (WebSocket), Telegram, CLI, REST
"""

import asyncio
import logging
from typing import Callable, Dict, List, Optional

logger = logging.getLogger("gateway")


class GatewayMessage:
    """A message flowing through the gateway."""

    def __init__(
        self,
        text: str,
        channel: str,       # "web", "telegram", "cli"
        user_id: str = "",
        reply_to: str = "",
        metadata: dict = None,
    ):
        self.text = text
        self.channel = channel
        self.user_id = user_id
        self.reply_to = reply_to
        self.metadata = metadata or {}


class Gateway:
    """Central message router for multi-channel communication."""

    def __init__(self):
        self._channels: Dict[str, object] = {}
        self._message_handler: Optional[Callable] = None
        self._outbound_queues: Dict[str, asyncio.Queue] = {}

    def register_channel(self, name: str, channel):
        """Register a communication channel."""
        self._channels[name] = channel
        self._outbound_queues[name] = asyncio.Queue()
        logger.info(f"Gateway: registered channel '{name}'")

    def set_message_handler(self, handler: Callable):
        """Set the handler for incoming messages from any channel."""
        self._message_handler = handler

    async def handle_incoming(self, message: GatewayMessage):
        """Process an incoming message from any channel."""
        if self._message_handler:
            response = await self._message_handler(message)
            if response:
                await self.send_to_channel(message.channel, response, message.user_id)

    async def send_to_channel(self, channel: str, text: str, user_id: str = ""):
        """Send a message to a specific channel."""
        ch = self._channels.get(channel)
        if ch and hasattr(ch, 'send_message'):
            try:
                await ch.send_message(text, user_id)
            except Exception as e:
                logger.error(f"Gateway send error ({channel}): {e}")

    async def broadcast(self, text: str, exclude_channel: str = ""):
        """Broadcast a message to all channels."""
        for name, ch in self._channels.items():
            if name != exclude_channel and hasattr(ch, 'send_message'):
                try:
                    await ch.send_message(text)
                except Exception:
                    pass

    def get_channels(self) -> List[dict]:
        return [
            {
                "name": name,
                "type": type(ch).__name__,
                "active": getattr(ch, 'active', False),
            }
            for name, ch in self._channels.items()
        ]
