from __future__ import annotations

"""
Checkpoint/Restore — Agent state persistence.

Agents can save their state and resume from it after restart.
Enables: pause/resume, crash recovery, cross-device migration.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("kernel.checkpoint")

CHECKPOINT_DIR = Path(__file__).parent.parent.parent / "data" / "checkpoints"


class CheckpointManager:
    """Manages agent state checkpoints."""

    def __init__(self):
        CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    def save(self, agent_id: str, state: Dict[str, Any]) -> str:
        """Save an agent's state checkpoint. Returns checkpoint ID."""
        checkpoint = {
            "agent_id": agent_id,
            "state": state,
            "saved_at": time.time(),
            "version": 1,
        }

        path = CHECKPOINT_DIR / f"{agent_id}.json"
        with open(path, "w") as f:
            json.dump(checkpoint, f, default=str)
        os.chmod(str(path), 0o600)  # H7: restrict permissions

        logger.debug(f"Checkpoint saved: {agent_id}")
        return str(path)

    def restore(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Restore an agent's state from its last checkpoint."""
        path = CHECKPOINT_DIR / f"{agent_id}.json"
        if not path.exists():
            return None

        try:
            with open(path) as f:
                checkpoint = json.load(f)
            logger.info(f"Checkpoint restored: {agent_id} (saved {time.time() - checkpoint['saved_at']:.0f}s ago)")
            return checkpoint.get("state")
        except Exception as e:
            logger.error(f"Checkpoint restore error for {agent_id}: {e}")
            return None

    def delete(self, agent_id: str):
        """Delete an agent's checkpoint."""
        path = CHECKPOINT_DIR / f"{agent_id}.json"
        if path.exists():
            path.unlink()

    def list_checkpoints(self) -> list:
        """List all saved checkpoints."""
        checkpoints = []
        for path in CHECKPOINT_DIR.glob("*.json"):
            try:
                with open(path) as f:
                    data = json.load(f)
                checkpoints.append({
                    "agent_id": data["agent_id"],
                    "saved_at": data["saved_at"],
                    "age_seconds": time.time() - data["saved_at"],
                    "size_bytes": path.stat().st_size,
                })
            except Exception:
                pass
        return checkpoints

    def get_stats(self) -> dict:
        checkpoints = self.list_checkpoints()
        total_bytes = sum(c["size_bytes"] for c in checkpoints)
        return {
            "checkpoints": len(checkpoints),
            "total_size_bytes": total_bytes,
            "total_size_kb": round(total_bytes / 1024, 1),
        }
