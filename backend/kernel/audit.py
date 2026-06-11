from __future__ import annotations

"""
Audit Log — Immutable append-only log of all agent actions.

Every action through the kernel gets logged. This is the forensic
record of everything agents do. Cannot be modified or deleted
(only appended). Like /var/log/audit on Linux.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.database import get_db

logger = logging.getLogger("kernel.audit")


class AuditLog:
    """Immutable append-only audit log."""

    def __init__(self):
        self._init_table()
        self._buffer: List[dict] = []
        self._flush_threshold = 10
        import threading
        self._lock = threading.Lock()  # M4: thread-safe buffer

    def _init_table(self):
        conn = get_db()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                agent_id TEXT NOT NULL,
                action TEXT NOT NULL,
                action_type TEXT DEFAULT '',
                params TEXT DEFAULT '{}',
                result TEXT DEFAULT 'success',
                duration_ms REAL DEFAULT 0,
                risk_level TEXT DEFAULT 'safe',
                verified INTEGER DEFAULT 1,
                blocked INTEGER DEFAULT 0,
                block_reason TEXT DEFAULT '',
                metadata TEXT DEFAULT '{}'
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(timestamp)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_agent ON audit_log(agent_id)
        """)
        conn.commit()
        conn.close()

    def log(
        self,
        agent_id: str,
        action: str,
        action_type: str = "",
        params: dict = None,
        result: str = "success",
        duration_ms: float = 0,
        risk_level: str = "safe",
        verified: bool = True,
        blocked: bool = False,
        block_reason: str = "",
        metadata: dict = None,
    ):
        """Log an action to the audit trail."""
        entry = {
            "timestamp": time.time(),
            "agent_id": agent_id,
            "action": action,
            "action_type": action_type,
            "params": json.dumps(params or {}),
            "result": result,
            "duration_ms": duration_ms,
            "risk_level": risk_level,
            "verified": 1 if verified else 0,
            "blocked": 1 if blocked else 0,
            "block_reason": block_reason,
            "metadata": json.dumps(metadata or {}),
        }
        with self._lock:  # M4: thread-safe
            self._buffer.append(entry)
            if len(self._buffer) >= self._flush_threshold:
                self._flush()

    def _flush(self):
        """Write buffered entries to database."""
        if not self._buffer:
            return
        conn = get_db()
        try:
            for entry in self._buffer:
                conn.execute(
                    """INSERT INTO audit_log
                       (timestamp, agent_id, action, action_type, params, result,
                        duration_ms, risk_level, verified, blocked, block_reason, metadata)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        entry["timestamp"], entry["agent_id"], entry["action"],
                        entry["action_type"], entry["params"], entry["result"],
                        entry["duration_ms"], entry["risk_level"], entry["verified"],
                        entry["blocked"], entry["block_reason"], entry["metadata"],
                    ),
                )
            conn.commit()
            self._buffer.clear()
        finally:
            conn.close()

    def query(
        self,
        agent_id: str = None,
        action: str = None,
        limit: int = 50,
        since: float = 0,
        blocked_only: bool = False,
    ) -> List[dict]:
        """Query the audit log."""
        self._flush()  # Ensure buffer is written

        conn = get_db()
        try:
            conditions = []
            params = []

            if agent_id:
                conditions.append("agent_id = ?")
                params.append(agent_id)
            if action:
                conditions.append("action LIKE ?")
                params.append(f"%{action}%")
            if since > 0:
                conditions.append("timestamp > ?")
                params.append(since)
            if blocked_only:
                conditions.append("blocked = 1")

            where = " AND ".join(conditions)
            query = f"SELECT * FROM audit_log {'WHERE ' + where if where else ''} ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(query, params).fetchall()
            return [
                {
                    "id": r["id"],
                    "timestamp": r["timestamp"],
                    "agent_id": r["agent_id"],
                    "action": r["action"],
                    "action_type": r["action_type"],
                    "params": json.loads(r["params"]),
                    "result": r["result"],
                    "duration_ms": r["duration_ms"],
                    "risk_level": r["risk_level"],
                    "verified": bool(r["verified"]),
                    "blocked": bool(r["blocked"]),
                    "block_reason": r["block_reason"],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def get_stats(self) -> dict:
        self._flush()
        conn = get_db()
        try:
            total = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
            blocked = conn.execute("SELECT COUNT(*) FROM audit_log WHERE blocked=1").fetchone()[0]
            agents = conn.execute("SELECT COUNT(DISTINCT agent_id) FROM audit_log").fetchone()[0]
            return {
                "total_entries": total,
                "blocked_actions": blocked,
                "unique_agents": agents,
                "buffer_size": len(self._buffer),
            }
        finally:
            conn.close()
