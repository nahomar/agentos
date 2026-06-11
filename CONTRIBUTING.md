# Contributing to AgentOS

## Quick Start

```bash
git clone https://github.com/nahommohan/agentos.git
cd agentos
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[all]"
cp config.example.yaml config.yaml
agentos start
```

## Creating an Agent (No Code)

1. Create `agents/custom/my-agent/manifest.yaml`:

```yaml
agent:
  id: "my-agent"
  name: "My Agent"
  emoji: "🤖"
  color: "#9B59B6"
  personality: "helpful"
  triggers:
    - type: "interval"
      seconds: 60
  actions:
    - type: "notify"
      template: "Hello from my agent!"
```

2. Restart: `agentos restart`

## Creating an Agent (Python)

1. Create `agents/custom/my-agent/manifest.yaml` with `class: "agent.MyAgent"`
2. Create `agents/custom/my-agent/agent.py`:

```python
from backend.agents.base import BaseAgent

class MyAgent(BaseAgent):
    name = "My Agent"
    emoji = "🤖"

    async def run_cycle(self):
        result = await self.think("What's interesting right now?")
        if result:
            await self.report_finding(result, "my-category")
        await self.broadcast_status("thinking...")
```

## Architecture

```
backend/
  kernel/         — IPC, Scheduler, Governor, Watchdog, Audit, Checkpoint, MCP, Namespace
  semantic_bus/   — Typed action protocol (22 actions across 10 apps)
  context/        — User context engine + pattern learning
  verification/   — Deterministic safety layer
  identity/       — AES-256 encrypted credential vault
agents/           — Plugin agents (YAML + optional Python)
frontend/         — Animated wallpaper UI
```

## Security

- Never commit `config.yaml` (contains API keys)
- Never commit anything in `data/` (contains tokens, database)
- All file I/O uses parameterized queries (no SQL injection)
- No `eval()` anywhere (safe regex parser for conditions)
- All user content sanitized before rendering

## Pull Requests

1. Fork the repo
2. Create a branch: `git checkout -b feature/my-feature`
3. Run tests: `python3 tests/test_kernel.py`
4. Submit PR with description of changes
