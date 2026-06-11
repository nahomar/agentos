from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class TriggerDef:
    type: str  # "interval", "event", "schedule", "command"
    seconds: int = 30
    event: str = ""
    cron: str = ""
    command: str = ""


@dataclass
class ApiKeyDef:
    key: str
    required: bool = False
    description: str = ""


@dataclass
class AgentManifest:
    id: str
    name: str
    emoji: str = "🤖"
    color: str = "#FFFFFF"
    app_name: str = ""
    personality: str = "helpful"
    description: str = ""
    author: str = "AgentOS"
    version: str = "1.0.0"

    capabilities_required: List[str] = field(default_factory=list)
    capabilities_provided: List[str] = field(default_factory=list)
    api_keys: List[ApiKeyDef] = field(default_factory=list)
    triggers: List[TriggerDef] = field(default_factory=list)

    # Python class to load (relative to agent directory)
    agent_class: str = ""  # e.g. "agent.SpotifyAgent"

    # For config-only agents (no Python code)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    rules: List[Dict[str, Any]] = field(default_factory=list)

    # Runtime
    directory: str = ""  # Set by loader
    category: str = ""  # "builtin", "community", "custom"

    def get_interval(self) -> int:
        for t in self.triggers:
            if t.type == "interval":
                return t.seconds
        return 30

    def get_events(self) -> List[str]:
        return [t.event for t in self.triggers if t.type == "event" and t.event]

    @property
    def is_config_only(self) -> bool:
        return not self.agent_class


def parse_manifest(path: Path) -> AgentManifest:
    with open(path) as f:
        raw = yaml.safe_load(f) or {}

    agent = raw.get("agent", raw)

    triggers = []
    for t in agent.get("triggers", []):
        triggers.append(TriggerDef(
            type=t.get("type", "interval"),
            seconds=t.get("seconds", 30),
            event=t.get("event", ""),
            cron=t.get("cron", ""),
            command=t.get("command", ""),
        ))
    if not triggers:
        triggers = [TriggerDef(type="interval", seconds=30)]

    api_keys = []
    for k in agent.get("api_keys", []):
        if isinstance(k, dict):
            api_keys.append(ApiKeyDef(
                key=k.get("key", ""),
                required=k.get("required", False),
                description=k.get("description", ""),
            ))
        elif isinstance(k, str):
            api_keys.append(ApiKeyDef(key=k))

    return AgentManifest(
        id=agent.get("id", path.parent.name),
        name=agent.get("name", path.parent.name.title()),
        emoji=agent.get("emoji", "🤖"),
        color=agent.get("color", "#FFFFFF"),
        app_name=agent.get("app_name", ""),
        personality=agent.get("personality", "helpful"),
        description=agent.get("description", ""),
        author=agent.get("author", "AgentOS"),
        version=agent.get("version", "1.0.0"),
        capabilities_required=agent.get("capabilities_required", []),
        capabilities_provided=agent.get("capabilities_provided", []),
        api_keys=api_keys,
        triggers=triggers,
        agent_class=agent.get("class", ""),
        actions=agent.get("actions", []),
        rules=agent.get("rules", []),
        directory=str(path.parent),
    )
