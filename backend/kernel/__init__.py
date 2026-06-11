"""
AgentOS Kernel — The microkernel for agentic computing.

Subsystems:
- IPC Broker: Inter-agent communication over sockets
- Scheduler: Priority-based agent scheduling with fairness
- Governor: Resource limits (CPU, memory, network)
- Watchdog: Crash detection and auto-restart
- Audit: Immutable action log
- Checkpoint: Agent state persistence
- Namespace: Virtual filesystem for agent introspection
- MCP: Model Context Protocol compatibility
"""
