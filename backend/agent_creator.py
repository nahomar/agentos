from __future__ import annotations

import logging
import os
import re
import yaml
from pathlib import Path
from typing import Optional

from backend.intelligence import AgentBrain

logger = logging.getLogger("agent_creator")

AGENTS_DIR = Path(__file__).parent.parent / "agents" / "custom"

# Template for generating manifests from natural language
CREATOR_PROMPT = """You are an agent manifest generator for AgentOS.
The user wants to create a new agent with this description:

"{description}"

Generate a YAML manifest for this agent. The manifest should follow this exact structure:

```yaml
agent:
  id: "unique-id"
  name: "Display Name"
  emoji: "relevant emoji"
  color: "#hex_color"
  app_name: "App Name"
  personality: "brief personality description"
  description: "what this agent does"

  triggers:
    - type: "interval"
      seconds: <appropriate_interval>

  actions:
    - type: "notify"
      template: "message template"
      condition: "optional condition using context.hour, context.day_of_week etc"

  rules:
    - when: "condition expression"
      do: "notify"
      message: "rule message"
```

Available context variables for conditions:
- context.hour (0-23)
- context.day_of_week (monday-sunday)
- context.is_weekend (True/False)
- context.time_of_day (early_morning, morning, midday, afternoon, evening, night, late_night)
- context.sedentary_minutes (int)
- context.inferred_mood (focused, relaxed, stressed, etc)
- context.current_app (string)

Rules:
- Choose an emoji that matches the agent's purpose
- Pick a color that's visually distinct
- Set interval based on how often the agent should check (60-300 seconds typical)
- Keep personality brief but distinctive
- Make templates friendly and helpful, not robotic
- Use conditions wisely — not every action needs one

Output ONLY the YAML content, no markdown fences or explanation."""


async def create_agent_from_description(
    description: str,
    brain: AgentBrain,
) -> dict:
    """Create a new agent from a natural language description.
    Returns {"success": bool, "agent_id": str, "manifest_path": str, "error": str}
    """

    if not brain.has_any_ai:
        # Fallback: parse simple descriptions without AI
        return _create_simple_agent(description)

    result = await brain._claude_think(
        "You generate YAML agent manifests. Output only valid YAML, nothing else.",
        CREATOR_PROMPT.format(description=description),
        500,
    )

    if not result:
        result = await brain._gemini_think(
            "You generate YAML agent manifests. Output only valid YAML, nothing else.",
            CREATOR_PROMPT.format(description=description),
            500,
        )

    if not result:
        return _create_simple_agent(description)

    # Clean up response — remove markdown fences if present
    result = result.strip()
    if result.startswith("```"):
        result = re.sub(r'^```\w*\n', '', result)
        result = re.sub(r'\n```$', '', result)

    try:
        parsed = yaml.safe_load(result)
        if not parsed:
            return {"success": False, "error": "Invalid YAML generated"}

        agent_data = parsed.get("agent", parsed)
        agent_id = agent_data.get("id", "custom-agent")

        # Sanitize ID — no path traversal
        agent_id = re.sub(r'[^a-z0-9-]', '-', agent_id.lower())
        if ".." in agent_id or "/" in agent_id:
            return {"success": False, "error": "Invalid agent ID"}

        # C6: SECURITY — strip dangerous fields from AI-generated manifest
        # Never allow AI to specify a Python class to load
        for dangerous_key in ["class", "agent_class", "module", "import"]:
            agent_data.pop(dangerous_key, None)
            if "agent" in parsed and isinstance(parsed["agent"], dict):
                parsed["agent"].pop(dangerous_key, None)

        # Sanitize actions — no eval, no code execution
        for action in agent_data.get("actions", []):
            if isinstance(action, dict):
                # Strip any condition containing dunder attributes
                cond = action.get("condition", "")
                if "__" in str(cond):
                    action["condition"] = ""

        # Create directory and write manifest
        agent_dir = AGENTS_DIR / agent_id
        agent_dir.mkdir(parents=True, exist_ok=True)

        manifest_path = agent_dir / "manifest.yaml"
        with open(manifest_path, "w") as f:
            yaml.dump(parsed, f, default_flow_style=False, allow_unicode=True)
        os.chmod(str(manifest_path), 0o600)

        logger.info(f"Created agent: {agent_data.get('emoji', '🤖')} {agent_data.get('name', agent_id)}")

        return {
            "success": True,
            "agent_id": agent_id,
            "name": agent_data.get("name", agent_id),
            "emoji": agent_data.get("emoji", "🤖"),
            "manifest_path": str(manifest_path),
        }

    except yaml.YAMLError as e:
        return {"success": False, "error": f"YAML parse error: {e}"}


def _create_simple_agent(description: str) -> dict:
    """Create a basic agent from description without AI."""

    # Extract key info from description
    desc_lower = description.lower()

    # Guess interval
    interval = 120
    if "every hour" in desc_lower:
        interval = 3600
    elif "every 30 min" in desc_lower:
        interval = 1800
    elif "every 2 hour" in desc_lower:
        interval = 7200
    elif "every 5 min" in desc_lower:
        interval = 300

    # Guess emoji
    emoji = "🤖"
    emoji_map = {
        "water": "💧", "drink": "💧", "hydrat": "💧",
        "exercise": "🏃", "walk": "🚶", "move": "💪", "stretch": "🧘",
        "read": "📚", "book": "📖", "learn": "🎓",
        "meditat": "🧘", "breath": "🌬️", "relax": "😌",
        "sleep": "😴", "bed": "🛏️", "rest": "💤",
        "food": "🍽️", "eat": "🍽️", "meal": "🥗",
        "code": "💻", "program": "💻", "work": "⚡",
        "call": "📞", "phone": "📱", "text": "💬",
        "photo": "📸", "picture": "📷",
        "music": "🎵", "song": "🎶",
        "money": "💰", "finance": "📊", "budget": "💸",
    }
    for keyword, em in emoji_map.items():
        if keyword in desc_lower:
            emoji = em
            break

    # Generate ID
    words = re.findall(r'[a-z]+', desc_lower)
    agent_id = "-".join(words[:3]) or "custom-agent"

    # Generate name
    name = " ".join(w.capitalize() for w in words[:2]) or "Custom Agent"

    manifest = {
        "agent": {
            "id": agent_id,
            "name": name,
            "emoji": emoji,
            "color": "#9B59B6",
            "personality": "helpful and punctual",
            "description": description,
            "triggers": [{"type": "interval", "seconds": interval}],
            "actions": [
                {"type": "notify", "template": description}
            ],
        }
    }

    agent_dir = AGENTS_DIR / agent_id
    agent_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = agent_dir / "manifest.yaml"
    with open(manifest_path, "w") as f:
        yaml.dump(manifest, f, default_flow_style=False, allow_unicode=True)

    return {
        "success": True,
        "agent_id": agent_id,
        "name": name,
        "emoji": emoji,
        "manifest_path": str(manifest_path),
    }
