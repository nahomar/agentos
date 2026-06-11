"""Tests for the proactive execution path: rules -> verification -> semantic bus,
speculative pre-warming, and event-driven rule evaluation."""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_bus():
    from backend.semantic_bus.bus import SemanticBus
    from backend.semantic_bus.builtin_apps import get_builtin_apps
    from backend.semantic_bus.handlers import get_builtin_handlers

    bus = SemanticBus()
    handlers = get_builtin_handlers({})
    for manifest in get_builtin_apps():
        bus.register_app(manifest, handlers)
    return bus


def _make_evaluator(semantic_bus, verification=None):
    # Must be called inside a running loop (MessageBus creates asyncio.Lock)
    from backend.bus import MessageBus
    from backend.proactive.evaluator import RulesEvaluator

    msg_bus = MessageBus()
    evaluator = RulesEvaluator(msg_bus, {})
    evaluator.rules = []  # isolate from builtin rules
    evaluator.set_action_executor(semantic_bus, verification)
    return evaluator, msg_bus


def test_all_builtin_actions_have_handlers():
    bus = _make_bus()
    missing = [a.id for a in bus.get_available_actions() if a.id not in bus._handlers]
    assert missing == [], f"Actions without handlers: {missing}"


def test_bus_executes_safe_action():
    async def run():
        bus = _make_bus()
        result = await bus.execute(
            "calendar.create_event",
            {"title": "Standup", "start": "2026-06-12T09:00"},
            agent_id="test",
        )
        assert result.success, result.error

        result = await bus.execute("calendar.get_upcoming", {}, agent_id="test")
        assert result.success
        assert result.data["count"] >= 1

    asyncio.run(run())


def test_rule_executes_low_risk_capability():
    from backend.bus import MessageType
    from backend.context.models import UserContext
    from backend.proactive.rules import ProactiveRule, Action

    async def run():
        bus = _make_bus()
        evaluator, msg_bus = _make_evaluator(bus)
        evaluator.rules = [ProactiveRule(
            id="test_dnd", name="Test DND",
            actions=[Action(type="execute_capability", params={
                "action_id": "settings.toggle_dnd",
                "action_params": {"enabled": True, "duration_minutes": 30},
            })],
        )]

        await evaluator.evaluate(UserContext())

        alerts = msg_bus.get_history(msg_type=MessageType.USER_ALERT)
        assert any(a["metadata"].get("type") == "proactive_action" for a in alerts)
        assert any(e["action_id"] == "settings.toggle_dnd" for e in bus._execution_log)

    asyncio.run(run())


def test_high_risk_capability_requires_confirmation():
    from backend.bus import MessageType
    from backend.context.models import UserContext
    from backend.proactive.rules import ProactiveRule, Action

    async def run():
        bus = _make_bus()
        evaluator, msg_bus = _make_evaluator(bus)
        evaluator.rules = [ProactiveRule(
            id="test_msg", name="Test Message",
            actions=[Action(type="execute_capability", params={
                "action_id": "messages.send",
                "action_params": {"recipient": "John", "body": "hi"},
            })],
        )]

        await evaluator.evaluate(UserContext())

        alerts = msg_bus.get_history(msg_type=MessageType.USER_ALERT)
        assert any(
            a["metadata"].get("type") == "proactive_action_confirmation"
            for a in alerts
        )
        # Never executed without confirmation
        assert not any(e["action_id"] == "messages.send" for e in bus._execution_log)

    asyncio.run(run())


def test_verification_blocks_payment_over_limit():
    from backend.bus import MessageType
    from backend.context.models import UserContext
    from backend.proactive.rules import ProactiveRule, Action
    from backend.verification.layer import VerificationLayer

    async def run():
        bus = _make_bus()
        verification = VerificationLayer({"max_payment_amount": 1000})
        evaluator, msg_bus = _make_evaluator(bus, verification)
        evaluator.rules = [ProactiveRule(
            id="test_pay", name="Test Payment",
            actions=[Action(type="execute_capability", params={
                "action_id": "payments.send",
                "action_params": {"recipient": "John", "amount": 5000},
            })],
        )]

        await evaluator.evaluate(UserContext())

        alerts = msg_bus.get_history(msg_type=MessageType.USER_ALERT)
        assert any(
            a["metadata"].get("type") == "proactive_action_blocked" for a in alerts
        )
        assert not any(e["action_id"] == "payments.send" for e in bus._execution_log)
        assert verification.get_stats()["actions_blocked"] == 1

    asyncio.run(run())


def test_speculative_engine_executes_and_caches():
    from backend.execution.speculative import SpeculativeEngine, PredictedAction

    async def run():
        bus = _make_bus()
        engine = SpeculativeEngine()
        engine.set_executor(bus.execute)

        async def predictor(ctx):
            return [PredictedAction(
                action_id="calendar.get_upcoming", params={},
                confidence=0.9, reason="test",
            )]

        engine.add_predictor(predictor)
        await engine._cycle({})

        assert engine.get_cached_result("calendar.get_upcoming", {}) is not None
        assert engine.get_stats()["hits"] == 1

    asyncio.run(run())


def test_poke_wakes_evaluator():
    async def run():
        bus = _make_bus()
        evaluator, _ = _make_evaluator(bus)

        evaluator.poke()  # before start(): must be a safe no-op
        assert evaluator._wake is None

        evaluator._wake = asyncio.Event()  # what start() does
        evaluator.poke()
        assert evaluator._wake.is_set()

    asyncio.run(run())


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  PASS {name}")
    print("All proactive execution tests passed")
