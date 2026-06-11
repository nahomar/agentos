from __future__ import annotations

import json
import logging
import time
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from backend.database import get_db

logger = logging.getLogger("patterns")


class PatternEngine:
    """Learns user behavioral patterns from historical context snapshots.

    Tracks time-bucketed behavior (what does the user do at X time on Y day?)
    and sequential patterns (after doing X, user usually does Y).
    """

    def __init__(self):
        self._init_tables()
        self._snapshot_count = 0

    def _init_tables(self):
        conn = get_db()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS behavior_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hour INTEGER NOT NULL,
                day_of_week TEXT NOT NULL,
                is_weekend INTEGER NOT NULL,
                app TEXT DEFAULT '',
                mood TEXT DEFAULT '',
                activity TEXT DEFAULT '',
                weather_condition TEXT DEFAULT '',
                temperature_f REAL DEFAULT 0,
                location_type TEXT DEFAULT '',
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS learned_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_type TEXT NOT NULL,
                pattern_key TEXT NOT NULL,
                pattern_value TEXT NOT NULL,
                frequency INTEGER DEFAULT 1,
                confidence REAL DEFAULT 0.0,
                last_seen REAL NOT NULL,
                UNIQUE(pattern_type, pattern_key, pattern_value)
            );

            CREATE INDEX IF NOT EXISTS idx_behavior_hour ON behavior_log(hour, day_of_week);
        """)
        conn.commit()
        conn.close()

    def record(self, context_dict: dict):
        """Record a context snapshot for pattern learning."""
        conn = get_db()
        try:
            weather = context_dict.get("weather", {})
            if isinstance(weather, dict):
                weather_condition = weather.get("condition", "")
                temp = weather.get("temperature_f", 0)
            else:
                weather_condition = ""
                temp = 0

            location = context_dict.get("location", {})
            if isinstance(location, dict):
                loc_type = location.get("location_type", "")
            else:
                loc_type = ""

            conn.execute(
                """INSERT INTO behavior_log
                   (hour, day_of_week, is_weekend, app, mood, activity,
                    weather_condition, temperature_f, location_type, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    context_dict.get("hour", 0),
                    context_dict.get("day_of_week", ""),
                    1 if context_dict.get("is_weekend") else 0,
                    context_dict.get("current_app", ""),
                    context_dict.get("inferred_mood", ""),
                    context_dict.get("activity_level", ""),
                    weather_condition,
                    temp,
                    loc_type,
                    time.time(),
                ),
            )
            conn.commit()
            self._snapshot_count += 1

            # Recompute patterns every 20 snapshots
            if self._snapshot_count % 20 == 0:
                self._compute_patterns(conn)

            # Keep only last 5000 records
            conn.execute(
                "DELETE FROM behavior_log WHERE id NOT IN "
                "(SELECT id FROM behavior_log ORDER BY created_at DESC LIMIT 5000)"
            )
            conn.commit()
        finally:
            conn.close()

    def _compute_patterns(self, conn: sqlite3.Connection):
        """Analyze behavior_log to extract patterns."""
        # Pattern 1: What app does user use at each hour?
        rows = conn.execute(
            """SELECT hour, day_of_week, app, COUNT(*) as freq
               FROM behavior_log WHERE app != ''
               GROUP BY hour, day_of_week, app
               ORDER BY freq DESC"""
        ).fetchall()

        for row in rows:
            if row["freq"] >= 3:  # Need at least 3 occurrences
                key = f"hour:{row['hour']}:day:{row['day_of_week']}"
                self._upsert_pattern(conn, "app_usage", key, row["app"], row["freq"])

        # Pattern 2: What mood at each time?
        rows = conn.execute(
            """SELECT hour, is_weekend, mood, COUNT(*) as freq
               FROM behavior_log WHERE mood != ''
               GROUP BY hour, is_weekend, mood
               ORDER BY freq DESC"""
        ).fetchall()

        for row in rows:
            if row["freq"] >= 3:
                key = f"hour:{row['hour']}:weekend:{row['is_weekend']}"
                self._upsert_pattern(conn, "mood", key, row["mood"], row["freq"])

        # Pattern 3: Activity patterns by time/weather
        rows = conn.execute(
            """SELECT hour, weather_condition, activity, COUNT(*) as freq
               FROM behavior_log WHERE activity != ''
               GROUP BY hour, weather_condition, activity
               ORDER BY freq DESC"""
        ).fetchall()

        for row in rows:
            if row["freq"] >= 3:
                key = f"hour:{row['hour']}:weather:{row['weather_condition']}"
                self._upsert_pattern(conn, "activity", key, row["activity"], row["freq"])

        conn.commit()

    def _upsert_pattern(self, conn, ptype: str, key: str, value: str, freq: int):
        # Calculate confidence based on frequency
        total = conn.execute(
            "SELECT COUNT(*) FROM behavior_log"
        ).fetchone()[0]
        confidence = min(freq / max(total * 0.1, 1), 1.0)  # Normalize

        conn.execute(
            """INSERT INTO learned_patterns (pattern_type, pattern_key, pattern_value, frequency, confidence, last_seen)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(pattern_type, pattern_key, pattern_value)
               DO UPDATE SET frequency=?, confidence=?, last_seen=?""",
            (ptype, key, value, freq, confidence, time.time(),
             freq, confidence, time.time()),
        )

    def predict(self, context_dict: dict) -> List[Dict[str, Any]]:
        """Based on learned patterns, predict what user likely wants right now."""
        predictions = []
        conn = get_db()
        try:
            hour = context_dict.get("hour", datetime.now().hour)
            day = context_dict.get("day_of_week", datetime.now().strftime("%A").lower())
            is_weekend = 1 if context_dict.get("is_weekend") else 0
            weather = ""
            w = context_dict.get("weather", {})
            if isinstance(w, dict):
                weather = w.get("condition", "")

            # Predict expected app
            rows = conn.execute(
                """SELECT pattern_value, confidence FROM learned_patterns
                   WHERE pattern_type='app_usage' AND pattern_key=?
                   ORDER BY confidence DESC LIMIT 3""",
                (f"hour:{hour}:day:{day}",),
            ).fetchall()
            for r in rows:
                predictions.append({
                    "type": "app_usage",
                    "prediction": f"User usually uses {r['pattern_value']} at this time",
                    "value": r["pattern_value"],
                    "confidence": r["confidence"],
                })

            # Predict expected mood
            rows = conn.execute(
                """SELECT pattern_value, confidence FROM learned_patterns
                   WHERE pattern_type='mood' AND pattern_key=?
                   ORDER BY confidence DESC LIMIT 1""",
                (f"hour:{hour}:weekend:{is_weekend}",),
            ).fetchall()
            for r in rows:
                predictions.append({
                    "type": "mood",
                    "prediction": f"User is usually {r['pattern_value']} at this time",
                    "value": r["pattern_value"],
                    "confidence": r["confidence"],
                })

            # Predict activity based on weather
            if weather:
                rows = conn.execute(
                    """SELECT pattern_value, confidence FROM learned_patterns
                       WHERE pattern_type='activity' AND pattern_key=?
                       ORDER BY confidence DESC LIMIT 1""",
                    (f"hour:{hour}:weather:{weather}",),
                ).fetchall()
                for r in rows:
                    predictions.append({
                        "type": "activity",
                        "prediction": f"User usually does {r['pattern_value']} in this weather",
                        "value": r["pattern_value"],
                        "confidence": r["confidence"],
                    })

        finally:
            conn.close()

        return predictions

    def get_habits(self) -> List[Dict[str, Any]]:
        """Return all learned habits with confidence scores."""
        conn = get_db()
        try:
            rows = conn.execute(
                """SELECT pattern_type, pattern_key, pattern_value, frequency, confidence
                   FROM learned_patterns
                   WHERE confidence > 0.3
                   ORDER BY confidence DESC
                   LIMIT 50"""
            ).fetchall()
            return [
                {
                    "type": dict(r)["pattern_type"],
                    "key": dict(r)["pattern_key"],
                    "value": dict(r)["pattern_value"],
                    "frequency": dict(r)["frequency"],
                    "confidence": dict(r)["confidence"],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def get_stats(self) -> dict:
        conn = get_db()
        try:
            total_logs = conn.execute("SELECT COUNT(*) FROM behavior_log").fetchone()[0]
            total_patterns = conn.execute("SELECT COUNT(*) FROM learned_patterns").fetchone()[0]
            return {
                "behavior_logs": total_logs,
                "learned_patterns": total_patterns,
                "snapshots_this_session": self._snapshot_count,
            }
        finally:
            conn.close()
