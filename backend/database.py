from __future__ import annotations

import os
import sqlite3
import json
import time
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("database")

DB_PATH = Path(__file__).parent.parent / "data" / "agentos.db"


def get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    # C4: Restrict file permissions
    if DB_PATH.exists():
        os.chmod(str(DB_PATH), 0o600)
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT NOT NULL,
            metadata TEXT DEFAULT '{}',
            created_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS context_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            context_json TEXT NOT NULL,
            created_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS rule_triggers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id TEXT NOT NULL,
            triggered_at REAL NOT NULL,
            context_json TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS user_preferences (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS notification_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            title TEXT DEFAULT '',
            body TEXT NOT NULL,
            priority INTEGER DEFAULT 2,
            read INTEGER DEFAULT 0,
            created_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_type TEXT NOT NULL,
            pattern_key TEXT NOT NULL,
            pattern_data TEXT NOT NULL,
            confidence REAL DEFAULT 0.5,
            updated_at REAL NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_findings_agent ON findings(agent);
        CREATE INDEX IF NOT EXISTS idx_findings_created ON findings(created_at);
        CREATE INDEX IF NOT EXISTS idx_rule_triggers_rule ON rule_triggers(rule_id);
        CREATE INDEX IF NOT EXISTS idx_notifications_created ON notification_history(created_at);
    """)
    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {DB_PATH}")


def store_finding(agent: str, content: str, category: str, metadata: dict = None):
    conn = get_db()
    conn.execute(
        "INSERT INTO findings (agent, content, category, metadata, created_at) VALUES (?, ?, ?, ?, ?)",
        (agent, content[:2000], category, json.dumps(metadata or {}), time.time()),
    )
    # M3: Cap findings table
    conn.execute(
        "DELETE FROM findings WHERE id NOT IN "
        "(SELECT id FROM findings ORDER BY created_at DESC LIMIT 10000)"
    )
    conn.commit()
    conn.close()


def get_findings(limit: int = 20, agent: str = None) -> List[dict]:
    conn = get_db()
    if agent:
        rows = conn.execute(
            "SELECT * FROM findings WHERE agent=? ORDER BY created_at DESC LIMIT ?",
            (agent, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM findings ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    return [
        {"agent": r["agent"], "content": r["content"], "category": r["category"],
         "timestamp": r["created_at"], "metadata": json.loads(r["metadata"])}
        for r in rows
    ]


def store_notification(source: str, title: str, body: str, priority: int = 2):
    conn = get_db()
    conn.execute(
        "INSERT INTO notification_history (source, title, body, priority, created_at) VALUES (?, ?, ?, ?, ?)",
        (source, title[:500], body[:2000], priority, time.time()),
    )
    # M3: Cap notification history
    conn.execute(
        "DELETE FROM notification_history WHERE id NOT IN "
        "(SELECT id FROM notification_history ORDER BY created_at DESC LIMIT 5000)"
    )
    conn.commit()
    conn.close()


def store_context_snapshot(context_dict: dict):
    conn = get_db()
    conn.execute(
        "INSERT INTO context_history (context_json, created_at) VALUES (?, ?)",
        (json.dumps(context_dict), time.time()),
    )
    # Keep last 1000 snapshots
    conn.execute(
        "DELETE FROM context_history WHERE id NOT IN (SELECT id FROM context_history ORDER BY created_at DESC LIMIT 1000)"
    )
    conn.commit()
    conn.close()


def set_preference(key: str, value: Any):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO user_preferences (key, value, updated_at) VALUES (?, ?, ?)",
        (key, json.dumps(value), time.time()),
    )
    conn.commit()
    conn.close()


def get_preference(key: str, default: Any = None) -> Any:
    conn = get_db()
    row = conn.execute("SELECT value FROM user_preferences WHERE key=?", (key,)).fetchone()
    conn.close()
    if row:
        return json.loads(row["value"])
    return default
