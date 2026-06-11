from __future__ import annotations

"""
AgentOS Semantic Bus — Action Schema Protocol

Instead of agents "seeing" a screen and clicking buttons, apps publish their
available actions as typed schemas. The agent's context window receives:

    action: send_payment
    params: {recipient: str, amount: float, currency: str}
    constraints: {max_amount: 10000, requires_biometric: true}

Instead of:
    "I see a blue button that says 'Send' next to a text field..."

This reduces reasoning steps from ~10 (see → OCR → understand → plan → click)
to 1 (receive action → fill params → execute).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import json
import time


class ParamType(str, Enum):
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ENUM = "enum"
    DATE = "date"
    PHONE = "phone"
    EMAIL = "email"
    URL = "url"
    FILE = "file"
    LOCATION = "location"
    CONTACT = "contact"
    CURRENCY = "currency"


class RiskLevel(str, Enum):
    SAFE = "safe"                # No confirmation needed
    LOW = "low"                  # Show in feed, auto-approve after 5s
    MEDIUM = "medium"            # Require tap to confirm
    HIGH = "high"                # Require biometric (FaceID/fingerprint)
    CRITICAL = "critical"        # Require biometric + explicit confirmation


@dataclass
class ActionParam:
    name: str
    type: ParamType
    description: str = ""
    required: bool = True
    default: Any = None
    enum_values: List[str] = field(default_factory=list)  # For ParamType.ENUM
    constraints: Dict[str, Any] = field(default_factory=dict)  # min, max, pattern, etc.


@dataclass
class ActionSchema:
    """A single action an app exposes to agents."""
    id: str                          # e.g. "spotify.play_track"
    app_id: str                      # e.g. "spotify"
    name: str                        # e.g. "Play Track"
    description: str                 # What this action does
    params: List[ActionParam]        # Required/optional parameters
    risk_level: RiskLevel = RiskLevel.SAFE
    returns: str = ""                # Description of return value
    cooldown_seconds: int = 0        # Min time between executions
    requires_auth: bool = False      # Needs identity vault credentials
    tags: List[str] = field(default_factory=list)  # Searchable tags

    def to_context(self, filled_params: Dict[str, Any] = None) -> str:
        """Render this action as a concise string for an agent's context window."""
        params_str = ", ".join(
            f"{p.name}: {p.type.value}"
            + (f" = {p.default}" if p.default is not None else "")
            + (" [required]" if p.required else " [optional]")
            for p in self.params
        )
        filled = ""
        if filled_params:
            filled = "\n  filled: " + json.dumps(filled_params)
        return (
            f"action: {self.id}\n"
            f"  description: {self.description}\n"
            f"  params: ({params_str})\n"
            f"  risk: {self.risk_level.value}"
            f"{filled}"
        )

    def validate_params(self, params: Dict[str, Any]) -> tuple:
        """Validate parameters against schema. Returns (valid, errors)."""
        errors = []
        for p in self.params:
            if p.required and p.name not in params:
                errors.append(f"Missing required param: {p.name}")
                continue

            if p.name in params:
                val = params[p.name]
                # Type checking
                if p.type == ParamType.NUMBER and not isinstance(val, (int, float)):
                    errors.append(f"{p.name}: expected number, got {type(val).__name__}")
                if p.type == ParamType.BOOLEAN and not isinstance(val, bool):
                    errors.append(f"{p.name}: expected boolean")
                if p.type == ParamType.ENUM and val not in p.enum_values:
                    errors.append(f"{p.name}: must be one of {p.enum_values}")

                # Constraint checking
                if "min" in p.constraints and val < p.constraints["min"]:
                    errors.append(f"{p.name}: below minimum {p.constraints['min']}")
                if "max" in p.constraints and val > p.constraints["max"]:
                    errors.append(f"{p.name}: above maximum {p.constraints['max']}")

        return len(errors) == 0, errors

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "app_id": self.app_id,
            "name": self.name,
            "description": self.description,
            "risk_level": self.risk_level.value,
            "params": [
                {
                    "name": p.name,
                    "type": p.type.value,
                    "description": p.description,
                    "required": p.required,
                    "default": p.default,
                    "constraints": p.constraints,
                }
                for p in self.params
            ],
            "requires_auth": self.requires_auth,
            "tags": self.tags,
        }


@dataclass
class ActionResult:
    """Result of executing an action."""
    success: bool
    action_id: str
    data: Any = None
    error: str = ""
    execution_ms: float = 0
    timestamp: float = field(default_factory=time.time)


@dataclass
class AppManifest:
    """
    An app's agent-compatible manifest — the MCP wrapper.
    App developers add this as `agentos.json` in their app root
    to make their app agent-enabled in 5 minutes.
    """
    app_id: str
    name: str
    version: str
    description: str
    icon: str = ""
    actions: List[ActionSchema] = field(default_factory=list)
    events: List[str] = field(default_factory=list)  # Events this app emits
    data_schemas: Dict[str, Any] = field(default_factory=dict)  # Shared data formats
    auth_type: str = "none"  # none, oauth2, api_key, session
    auth_config: Dict[str, str] = field(default_factory=dict)
