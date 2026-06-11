"""Tests for AgentOS Kernel subsystems."""
import asyncio
import json
import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import pytest
except ImportError:
    pass  # Tests can run without pytest


# === IPC Broker ===
def test_ipc_broker_publish():
    from backend.kernel.ipc import IPCBroker, IPCMessage, MessageType

    broker = IPCBroker()
    received = []

    async def handler(msg):
        received.append(msg)

    broker.subscribe_all(handler)

    msg = IPCMessage(sender="test", recipient="all", type=MessageType.SYSTEM, content="hello")

    asyncio.get_event_loop().run_until_complete(broker.publish(msg))
    assert len(received) == 1
    assert received[0].content == "hello"
    assert broker.get_stats()["messages_total"] == 1


def test_ipc_broker_history():
    from backend.kernel.ipc import IPCBroker, IPCMessage, MessageType

    broker = IPCBroker(max_history=5)
    loop = asyncio.get_event_loop()

    for i in range(10):
        msg = IPCMessage(sender="test", recipient="all", type=MessageType.SYSTEM, content=f"msg {i}")
        loop.run_until_complete(broker.publish(msg))

    history = broker.get_history(limit=100)
    assert len(history) == 5  # Only last 5 kept


# === Scheduler ===
def test_scheduler_register():
    from backend.kernel.scheduler import AgentScheduler, Priority

    sched = AgentScheduler()
    sched.register("agent1", lambda: None, interval=30, priority=Priority.NORMAL)
    sched.register("agent2", lambda: None, interval=60, priority=Priority.HIGH)

    queue = sched.get_queue()
    assert len(queue) == 2
    assert queue[0]["agent_id"] in ("agent1", "agent2")

    stats = sched.get_stats()
    assert stats["tasks"] == 2


def test_scheduler_enable_disable():
    from backend.kernel.scheduler import AgentScheduler

    sched = AgentScheduler()
    sched.register("agent1", lambda: None)

    sched.disable("agent1")
    queue = sched.get_queue()
    assert queue[0]["enabled"] is False

    sched.enable("agent1")
    queue = sched.get_queue()
    assert queue[0]["enabled"] is True


# === Governor ===
def test_governor_quotas():
    from backend.kernel.governor import ResourceGovernor, ResourceQuota

    gov = ResourceGovernor()
    gov.set_quota("agent1", ResourceQuota(max_api_calls_per_minute=5))

    for i in range(5):
        assert gov.record_api_call("agent1") is True

    assert gov.record_api_call("agent1") is False  # Exceeded


def test_governor_cpu_tracking():
    from backend.kernel.governor import ResourceGovernor

    gov = ResourceGovernor()
    gov.record_cpu("agent1", 100.0)
    gov.record_cpu("agent1", 200.0)

    usage = gov.get_all_usage()
    assert "agent1" in usage
    assert usage["agent1"]["cpu_ms_total"] == 300.0


# === Watchdog ===
def test_watchdog_health():
    from backend.kernel.watchdog import Watchdog

    wd = Watchdog()
    wd.register("agent1")
    wd.register("agent2")

    wd.heartbeat("agent1")

    health = wd.get_health()
    assert len(health) == 2
    assert all(h["status"] == "healthy" for h in health)


def test_watchdog_failure_report():
    from backend.kernel.watchdog import Watchdog

    wd = Watchdog()
    wd.register("agent1")

    wd.report_failure("agent1", "test error")
    wd.report_failure("agent1", "test error 2")
    wd.report_failure("agent1", "test error 3")

    health = wd.get_health()
    agent_health = [h for h in health if h["agent_id"] == "agent1"][0]
    assert agent_health["status"] == "critical"
    assert agent_health["consecutive_failures"] == 3


# === Audit Log ===
def test_audit_log():
    from backend.kernel.audit import AuditLog
    from backend import database
    database.init_db()

    audit = AuditLog()
    audit.log(agent_id="test", action="test.action", result="success", duration_ms=50)
    audit.log(agent_id="test", action="test.blocked", blocked=True, block_reason="rate limit")
    audit._flush()

    entries = audit.query(limit=10)
    assert len(entries) >= 2

    stats = audit.get_stats()
    assert stats["total_entries"] >= 2
    assert stats["blocked_actions"] >= 1


# === Checkpoint ===
def test_checkpoint_save_restore():
    from backend.kernel.checkpoint import CheckpointManager

    mgr = CheckpointManager()
    mgr.save("test_agent", {"counter": 42, "data": "hello"})

    restored = mgr.restore("test_agent")
    assert restored is not None
    assert restored["counter"] == 42
    assert restored["data"] == "hello"

    # Cleanup
    mgr.delete("test_agent")
    assert mgr.restore("test_agent") is None


# === Semantic Bus ===
def test_semantic_bus_actions():
    from backend.semantic_bus.builtin_apps import get_builtin_apps
    from backend.semantic_bus.bus import SemanticBus

    bus = SemanticBus()
    for app in get_builtin_apps():
        bus.register_app(app)

    actions = bus.get_available_actions()
    assert len(actions) >= 20

    # Test tag filtering
    music_actions = bus.get_available_actions(tags=["music"])
    assert len(music_actions) >= 2

    # Test context generation
    ctx = bus.get_actions_context()
    assert "Available actions:" in ctx


def test_semantic_bus_validation():
    from backend.semantic_bus.schema import ActionSchema, ActionParam, ParamType, RiskLevel

    action = ActionSchema(
        id="test.action",
        app_id="test",
        name="Test",
        description="Test action",
        params=[
            ActionParam("amount", ParamType.NUMBER, required=True, constraints={"min": 0, "max": 100}),
            ActionParam("name", ParamType.STRING, required=True),
        ],
    )

    valid, errors = action.validate_params({"amount": 50, "name": "test"})
    assert valid is True

    valid, errors = action.validate_params({"amount": 200, "name": "test"})
    assert valid is False
    assert any("maximum" in e for e in errors)

    valid, errors = action.validate_params({"name": "test"})  # Missing amount
    assert valid is False


# === Verification Layer ===
def test_verification_payment_limit():
    from backend.verification.layer import VerificationLayer

    vl = VerificationLayer({"max_payment_amount": 500})
    result = vl.verify("payments.send", {"amount": 200, "currency": "USD"})
    assert result.passed is True

    result = vl.verify("payments.send", {"amount": 1000, "currency": "USD"})
    assert result.passed is False
    assert any("exceeds limit" in f["reason"] for f in result.failures)


def test_verification_duplicate():
    from backend.verification.layer import VerificationLayer

    vl = VerificationLayer()
    vl.verify("messages.send", {"recipient": "mom", "body": "hi"})
    result = vl.verify("messages.send", {"recipient": "mom", "body": "hi"})
    assert result.passed is False
    assert any("Duplicate" in f["reason"] for f in result.failures)


# === Identity Vault ===
def test_vault_store_retrieve():
    from backend.identity.vault import IdentityVault

    vault = IdentityVault(master_key="test_key_12345")
    vault.store_credential("test_service", "api_key", {"key": "sk-test-123"})

    cred = vault.get_credential("test_service")
    assert cred is not None
    assert cred["data"]["key"] == "sk-test-123"

    # Test session token
    session = vault.issue_session_token("agent1", "test_service", ttl=60)
    assert session is not None

    validated = vault.validate_session(session)
    assert validated is not None
    assert validated["agent_id"] == "agent1"

    # Revoke
    vault.revoke("test_service")
    assert vault.get_credential("test_service") is None


# === MCP Server ===
def test_mcp_initialize():
    from backend.semantic_bus.bus import SemanticBus
    from backend.semantic_bus.builtin_apps import get_builtin_apps
    from backend.kernel.mcp import MCPServer

    bus = SemanticBus()
    for app in get_builtin_apps():
        bus.register_app(app)

    mcp = MCPServer(bus)

    request = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    response = asyncio.get_event_loop().run_until_complete(mcp.handle_request(request))
    data = json.loads(response)

    assert data["result"]["protocolVersion"] == "2024-11-05"
    assert data["result"]["serverInfo"]["name"] == "agentos"


def test_mcp_tools_list():
    from backend.semantic_bus.bus import SemanticBus
    from backend.semantic_bus.builtin_apps import get_builtin_apps
    from backend.kernel.mcp import MCPServer

    bus = SemanticBus()
    for app in get_builtin_apps():
        bus.register_app(app)

    mcp = MCPServer(bus)

    request = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    response = asyncio.get_event_loop().run_until_complete(mcp.handle_request(request))
    data = json.loads(response)

    tools = data["result"]["tools"]
    assert len(tools) >= 20

    # Check tool format
    tool = tools[0]
    assert "name" in tool
    assert "description" in tool
    assert "inputSchema" in tool


# === Namespace ===
def test_namespace_mount_resolve():
    from backend.kernel.namespace import AgentNamespace

    ns = AgentNamespace()

    async def test_handler(params):
        return {"status": "ok", "id": params.get("id", "?")}

    ns.mount("/test/status", test_handler)
    ns.mount("/test/{id}/info", test_handler)

    loop = asyncio.get_event_loop()

    result = loop.run_until_complete(ns.resolve("/test/status"))
    assert result["status"] == "ok"

    result = loop.run_until_complete(ns.resolve("/test/agent1/info"))
    assert result["id"] == "agent1"

    paths = ns.list_paths()
    assert len(paths) == 2


# === Pattern Engine ===
def test_pattern_recording():
    from backend.context.patterns import PatternEngine
    from backend import database
    database.init_db()

    engine = PatternEngine()
    for i in range(5):
        engine.record({
            "hour": 10,
            "day_of_week": "monday",
            "is_weekend": False,
            "current_app": "VS Code",
            "inferred_mood": "focused",
            "activity_level": "sedentary",
            "weather": {"condition": "clear", "temperature_f": 72},
            "location": {"location_type": "home"},
        })

    stats = engine.get_stats()
    assert stats["behavior_logs"] >= 5


# === Config ===
def test_config_loading():
    from backend.config import load_config

    config = load_config()
    assert config.user.name == "Nahom"
    assert len(config.user.interests) > 0
    assert config.server.port == 8000


# === Plugin Loader ===
def test_plugin_discovery():
    from backend.plugins.loader import PluginLoader
    from pathlib import Path

    loader = PluginLoader(Path(__file__).parent.parent)
    manifests = loader.discover()
    assert len(manifests) >= 12  # At least 12 builtin agents


if __name__ == "__main__":
    # Simple test runner
    import traceback

    tests = [v for k, v in globals().items() if k.startswith("test_")]
    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            print(f"  ✓ {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {test.__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'═'*50}")
    print(f"  {passed} passed, {failed} failed, {passed + failed} total")
    print(f"{'═'*50}")
    sys.exit(1 if failed > 0 else 0)
