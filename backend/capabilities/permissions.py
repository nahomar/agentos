from __future__ import annotations

from enum import Enum
from typing import Dict


class PermissionLevel(str, Enum):
    AUTO = "auto"              # Always allowed
    ASK_ONCE = "ask_once"      # Ask user, remember answer
    ASK_ALWAYS = "ask_always"  # Ask every time
    DENY = "deny"              # Never allowed


# Default permission levels per capability pattern
DEFAULT_PERMISSIONS: Dict[str, PermissionLevel] = {
    # Information — always safe
    "info.weather": PermissionLevel.AUTO,
    "info.time": PermissionLevel.AUTO,
    "info.location": PermissionLevel.AUTO,
    "info.calendar": PermissionLevel.AUTO,
    "info.reminders": PermissionLevel.AUTO,

    # Content — always safe
    "content.web_browse": PermissionLevel.AUTO,
    "content.web_search": PermissionLevel.AUTO,
    "content.reddit": PermissionLevel.AUTO,
    "content.twitter": PermissionLevel.AUTO,
    "content.rss": PermissionLevel.AUTO,

    # AI — always safe
    "ai.claude": PermissionLevel.AUTO,
    "ai.gemini": PermissionLevel.AUTO,
    "ai.local_llm": PermissionLevel.AUTO,

    # Memory — always safe
    "memory.store": PermissionLevel.AUTO,
    "memory.recall": PermissionLevel.AUTO,

    # Device — mostly safe
    "device.notification": PermissionLevel.AUTO,
    "device.haptic": PermissionLevel.AUTO,
    "device.shortcut": PermissionLevel.ASK_ONCE,

    # Media — ask once
    "media.play_music": PermissionLevel.ASK_ONCE,
    "media.take_photo": PermissionLevel.ASK_ONCE,
    "media.record_audio": PermissionLevel.ASK_ALWAYS,

    # Communication — always ask
    "communication.sms": PermissionLevel.ASK_ALWAYS,
    "communication.call": PermissionLevel.ASK_ALWAYS,
    "communication.email": PermissionLevel.ASK_ONCE,
    "communication.push": PermissionLevel.ASK_ONCE,
}


class PermissionStore:
    """Manages permission grants for capabilities per agent."""

    def __init__(self):
        self._grants: Dict[str, Dict[str, bool]] = {}  # agent_id -> cap_id -> granted

    def get_level(self, capability_id: str) -> PermissionLevel:
        return DEFAULT_PERMISSIONS.get(capability_id, PermissionLevel.ASK_ONCE)

    def check(self, agent_id: str, capability_id: str) -> bool | None:
        """Check if permission is granted. Returns None if needs to ask."""
        level = self.get_level(capability_id)

        if level == PermissionLevel.AUTO:
            return True
        if level == PermissionLevel.DENY:
            return False
        if level == PermissionLevel.ASK_ALWAYS:
            return None  # Always ask
        if level == PermissionLevel.ASK_ONCE:
            key = f"{agent_id}:{capability_id}"
            if key in self._grants.get(agent_id, {}):
                return self._grants[agent_id][key]
            return None  # Need to ask

        return None

    def grant(self, agent_id: str, capability_id: str, allowed: bool):
        if agent_id not in self._grants:
            self._grants[agent_id] = {}
        self._grants[agent_id][f"{agent_id}:{capability_id}"] = allowed

    def revoke(self, agent_id: str, capability_id: str):
        if agent_id in self._grants:
            self._grants[agent_id].pop(f"{agent_id}:{capability_id}", None)

    def get_all_grants(self) -> Dict[str, Dict[str, bool]]:
        return dict(self._grants)
