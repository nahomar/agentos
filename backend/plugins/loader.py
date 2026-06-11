from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Type

from backend.bus import MessageBus
from backend.memory import SharedMemory
from backend.agents.base import BaseAgent
from backend.plugins.manifest import AgentManifest, parse_manifest
from backend.plugins.config_agent import ConfigAgent

logger = logging.getLogger("plugins.loader")

AGENT_DIRS = ["agents/builtin", "agents/community", "agents/custom"]


class PluginLoader:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self._manifests: Dict[str, AgentManifest] = {}

    def discover(self) -> List[AgentManifest]:
        manifests = []
        for dir_name in AGENT_DIRS:
            agent_dir = self.project_root / dir_name
            if not agent_dir.exists():
                continue

            category = dir_name.split("/")[-1]  # "builtin", "community", "custom"

            for manifest_path in sorted(agent_dir.glob("*/manifest.yaml")):
                try:
                    manifest = parse_manifest(manifest_path)
                    manifest.category = category
                    manifests.append(manifest)
                    self._manifests[manifest.id] = manifest
                    logger.info(f"Discovered agent: {manifest.emoji} {manifest.name} ({category})")
                except Exception as e:
                    logger.error(f"Failed to parse {manifest_path}: {e}")

        return manifests

    def load_agent(
        self,
        manifest: AgentManifest,
        bus: MessageBus,
        memory: SharedMemory,
        config: dict,
    ) -> BaseAgent:
        if manifest.is_config_only:
            return self._load_config_agent(manifest, bus, memory, config)
        else:
            return self._load_python_agent(manifest, bus, memory, config)

    def _load_python_agent(
        self,
        manifest: AgentManifest,
        bus: MessageBus,
        memory: SharedMemory,
        config: dict,
    ) -> BaseAgent:
        # Parse "agent.SpotifyAgent" -> module="agent", class="SpotifyAgent"
        parts = manifest.agent_class.rsplit(".", 1)
        if len(parts) == 2:
            module_name, class_name = parts
        else:
            module_name = parts[0]
            class_name = parts[0]

        agent_dir = Path(manifest.directory)
        module_path = agent_dir / f"{module_name}.py"

        if not module_path.exists():
            raise FileNotFoundError(f"Agent module not found: {module_path}")

        # Dynamic import
        spec = importlib.util.spec_from_file_location(
            f"agentos.agents.{manifest.id}.{module_name}",
            module_path,
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        agent_class: Type[BaseAgent] = getattr(module, class_name)
        agent = agent_class(bus, memory, config)

        # Override properties from manifest
        agent.name = manifest.name
        agent.emoji = manifest.emoji
        agent.color = manifest.color
        agent.app_name = manifest.app_name or manifest.name
        agent.personality = manifest.personality

        return agent

    def _load_config_agent(
        self,
        manifest: AgentManifest,
        bus: MessageBus,
        memory: SharedMemory,
        config: dict,
    ) -> BaseAgent:
        agent = ConfigAgent(bus, memory, config, manifest)
        return agent

    def get_manifest(self, agent_id: str) -> Optional[AgentManifest]:
        return self._manifests.get(agent_id)

    def get_all_manifests(self) -> List[AgentManifest]:
        return list(self._manifests.values())
