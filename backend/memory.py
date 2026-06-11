from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Dict, List


@dataclass
class Finding:
    agent: str
    content: str
    category: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SharedMemory:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._user_context: dict[str, Any] = {
            "current_app": None,
            "last_activity": None,
            "active_tasks": [],
            "last_seen": time.time(),
        }
        self._findings: list[Finding] = []
        self._interests: list[str] = []
        self._agent_states: dict[str, dict] = {}

    async def update_user_context(self, **kwargs):
        async with self._lock:
            self._user_context.update(kwargs)
            self._user_context["last_seen"] = time.time()

    async def get_user_context(self) -> dict:
        async with self._lock:
            return dict(self._user_context)

    async def store_finding(self, agent: str, content: str, category: str, **meta):
        async with self._lock:
            self._findings.append(Finding(
                agent=agent, content=content, category=category, metadata=meta
            ))
            if len(self._findings) > 500:
                self._findings = self._findings[-500:]

        # Persist to SQLite
        try:
            from backend.database import store_finding as db_store
            db_store(agent, content, category, meta)
        except Exception:
            pass

    async def get_findings(self, limit: int = 20, agent: Optional[str] = None, category: Optional[str] = None) -> List[dict]:
        async with self._lock:
            findings = self._findings
            if agent:
                findings = [f for f in findings if f.agent == agent]
            if category:
                findings = [f for f in findings if f.category == category]
            return [
                {"agent": f.agent, "content": f.content, "category": f.category,
                 "timestamp": f.timestamp, "metadata": f.metadata}
                for f in findings[-limit:]
            ]

    def set_interests(self, interests: list[str]):
        self._interests = interests

    async def get_interests(self) -> list[str]:
        async with self._lock:
            return list(self._interests)

    async def update_agent_state(self, agent_name: str, state: dict):
        async with self._lock:
            self._agent_states[agent_name] = {**state, "updated_at": time.time()}

    async def get_agent_states(self) -> dict:
        async with self._lock:
            return dict(self._agent_states)
