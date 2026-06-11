from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Dict
from pathlib import Path

import yaml


@dataclass
class Condition:
    field: str       # Dot-notation path into UserContext
    operator: str    # eq, neq, gt, lt, gte, lte, in, contains, between
    value: Any = None


@dataclass
class Action:
    type: str        # notify, suggest, execute_capability, agent_task
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProactiveRule:
    id: str
    name: str
    description: str = ""
    conditions: List[Condition] = field(default_factory=list)
    actions: List[Action] = field(default_factory=list)
    cooldown_minutes: int = 60
    priority: int = 2  # 1=low, 5=critical
    enabled: bool = True
    source: str = "system"  # system, agent, user


def load_rules_from_yaml(path: Path) -> List[ProactiveRule]:
    if not path.exists():
        return []

    with open(path) as f:
        raw = yaml.safe_load(f) or {}

    rules = []
    for r in raw.get("rules", []):
        conditions = []
        for c in r.get("conditions", []):
            conditions.append(Condition(
                field=c.get("field", ""),
                operator=c.get("operator", "eq"),
                value=c.get("value"),
            ))

        actions = []
        for a in r.get("actions", []):
            actions.append(Action(
                type=a.get("type", "notify"),
                params=a.get("params", {}),
            ))

        rules.append(ProactiveRule(
            id=r.get("id", ""),
            name=r.get("name", ""),
            description=r.get("description", ""),
            conditions=conditions,
            actions=actions,
            cooldown_minutes=r.get("cooldown_minutes", 60),
            priority=r.get("priority", 2),
            enabled=r.get("enabled", True),
            source=r.get("source", "system"),
        ))

    return rules
