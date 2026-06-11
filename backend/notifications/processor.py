from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import IntEnum
from typing import List, Optional

from backend.bus import MessageBus, Message, MessageType
from backend.database import store_notification

logger = logging.getLogger("notifications")


class Priority(IntEnum):
    IGNORABLE = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    CRITICAL = 5


@dataclass
class ProcessedNotification:
    source: str
    title: str
    body: str
    priority: Priority
    auto_response: str = ""
    summary: str = ""


# Keywords for priority classification
CRITICAL_KEYWORDS = ["emergency", "urgent", "security", "alert", "911"]
HIGH_KEYWORDS = ["meeting", "deadline", "boss", "important", "asap"]
LOW_KEYWORDS = ["sale", "discount", "promo", "newsletter", "subscribe"]
IGNORABLE_KEYWORDS = ["game", "streak", "daily reward", "play now"]


class NotificationProcessor:
    """Processes, classifies, and routes notifications."""

    def __init__(self, bus: MessageBus, config: dict):
        self.bus = bus
        self.config = config

    async def process(self, source: str, title: str, body: str) -> ProcessedNotification:
        """Process an incoming notification."""
        priority = self._classify(title, body, source)
        summary = self._summarize(title, body)

        notif = ProcessedNotification(
            source=source,
            title=title,
            body=body,
            priority=priority,
            summary=summary,
        )

        # Store in database
        store_notification(source, title, body, priority.value)

        # Route based on priority
        await self._route(notif)

        return notif

    def _classify(self, title: str, body: str, source: str) -> Priority:
        text = f"{title} {body}".lower()

        if any(kw in text for kw in CRITICAL_KEYWORDS):
            return Priority.CRITICAL

        if any(kw in text for kw in HIGH_KEYWORDS):
            return Priority.HIGH

        if any(kw in text for kw in IGNORABLE_KEYWORDS):
            return Priority.IGNORABLE

        if any(kw in text for kw in LOW_KEYWORDS):
            return Priority.LOW

        # Contact-based boost (if from messaging apps)
        if source in ("iMessage", "WhatsApp", "Telegram"):
            return Priority.HIGH

        return Priority.MEDIUM

    def _summarize(self, title: str, body: str) -> str:
        text = f"{title}: {body}" if title else body
        if len(text) > 100:
            return text[:97] + "..."
        return text

    async def _route(self, notif: ProcessedNotification):
        if notif.priority >= Priority.HIGH:
            # Immediate notification
            await self.bus.publish(Message(
                sender="Notifications",
                recipient="user",
                type=MessageType.USER_ALERT,
                content=f"**{notif.title}**\n{notif.body}",
                metadata={
                    "emoji": "🔔",
                    "color": "#E74C3C" if notif.priority >= Priority.CRITICAL else "#F39C12",
                    "type": "notification",
                    "priority": notif.priority.value,
                    "source": notif.source,
                },
            ))
        elif notif.priority >= Priority.MEDIUM:
            # Add to feed
            await self.bus.publish(Message(
                sender="Notifications",
                recipient="all",
                type=MessageType.AGENT_UPDATE,
                content=f"[{notif.source}] {notif.summary}",
                metadata={
                    "emoji": "📬",
                    "color": "#95A5A6",
                    "type": "notification",
                    "priority": notif.priority.value,
                },
            ))

    async def summarize_batch(self, notifications: List[ProcessedNotification]) -> str:
        """Summarize a batch of notifications."""
        if not notifications:
            return "No new notifications."

        by_priority = {}
        for n in notifications:
            p = n.priority.name
            if p not in by_priority:
                by_priority[p] = []
            by_priority[p].append(n.summary)

        lines = []
        for p in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            items = by_priority.get(p, [])
            if items:
                lines.append(f"**{p}** ({len(items)}):")
                for item in items[:3]:
                    lines.append(f"  • {item}")
                if len(items) > 3:
                    lines.append(f"  ... and {len(items) - 3} more")

        return "\n".join(lines)
