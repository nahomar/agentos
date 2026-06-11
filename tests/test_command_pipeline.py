"""Tests for the natural-language command pipeline: parsing, execution,
verification, and the confirmation flow."""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_pipeline(verification=None, speculative=None):
    from backend.semantic_bus.bus import SemanticBus
    from backend.semantic_bus.builtin_apps import get_builtin_apps
    from backend.semantic_bus.handlers import get_builtin_handlers
    from backend.command.pipeline import CommandPipeline

    bus = SemanticBus()
    handlers = get_builtin_handlers({})
    for manifest in get_builtin_apps():
        bus.register_app(manifest, handlers)

    pipeline = CommandPipeline(
        semantic_bus=bus,
        verification_layer=verification,
        speculative_engine=speculative,
    )
    return pipeline, bus


def test_deterministic_parser_coverage():
    pipeline, _ = _make_pipeline()
    cases = {
        "play some jazz": ("spotify.play_track", {"query": "jazz"}),
        "pause": ("spotify.pause", {}),
        "what's playing?": ("spotify.get_now_playing", {}),
        "text Sam: running late": ("messages.send", {"recipient": "Sam", "body": "running late"}),
        "message Alex saying see you at 6": ("messages.send", {"recipient": "Alex", "body": "see you at 6"}),
        "call Mom": ("phone.call", {"recipient": "Mom"}),
        "navigate to the airport": ("maps.navigate", {"destination": "the airport"}),
        "find a pharmacy nearby": ("maps.find_nearby", {"query": "pharmacy"}),
        "what's on my calendar": ("calendar.get_upcoming", {}),
        "note: buy milk": ("notes.create", {"title": "buy milk", "content": "buy milk"}),
        "search notes for groceries": ("notes.search", {"query": "groceries"}),
        "search for weather in addis ababa": ("browser.search", {"query": "weather in addis ababa"}),
        "send $20 to John": ("payments.send", {"recipient": "John", "amount": 20.0}),
        "volume 40": ("settings.set_volume", {"level": 40}),
        "dnd on": ("settings.toggle_dnd", {"enabled": True}),
        "take a photo": ("camera.take_photo", {}),
    }
    for text, (expected_action, expected_params) in cases.items():
        intent = pipeline._parse_deterministic(text)
        assert intent is not None, f"No parse for: {text}"
        assert intent["action_id"] == expected_action, (
            f"{text}: got {intent['action_id']}, want {expected_action}"
        )
        for k, v in expected_params.items():
            assert intent["params"].get(k) == v, (
                f"{text}: param {k}={intent['params'].get(k)!r}, want {v!r}"
            )


def test_safe_command_executes():
    async def run():
        pipeline, bus = _make_pipeline()
        result = await pipeline.handle("volume 25")
        assert result["success"] is True
        assert result["action_id"] == "settings.set_volume"
        assert any(e["action_id"] == "settings.set_volume" for e in bus._execution_log)

    asyncio.run(run())


def test_high_risk_command_requires_confirmation_then_executes():
    async def run():
        pipeline, bus = _make_pipeline()
        result = await pipeline.handle("text Sam: running late")
        assert result.get("requires_confirmation") is True
        pending_id = result["pending_id"]
        assert not any(e["action_id"] == "messages.send" for e in bus._execution_log)

        # Confirm via the natural-language path, as a Telegram user would
        confirmed = await pipeline.handle(f"confirm {pending_id}")
        assert confirmed["success"] is True
        assert any(e["action_id"] == "messages.send" for e in bus._execution_log)

        # Pending entry is consumed
        assert pipeline.get_pending() == []

    asyncio.run(run())


def test_deny_cancels_pending_action():
    async def run():
        pipeline, bus = _make_pipeline()
        result = await pipeline.handle("call Mom")
        pending_id = result["pending_id"]

        denied = await pipeline.confirm(pending_id, approved=False)
        assert "Cancelled" in denied["reply"]
        assert not any(e["action_id"] == "phone.call" for e in bus._execution_log)

    asyncio.run(run())


def test_verification_blocks_before_bus():
    from backend.verification.layer import VerificationLayer

    async def run():
        verification = VerificationLayer({"max_payment_amount": 100})
        pipeline, bus = _make_pipeline(verification=verification)
        result = await pipeline.handle("send $5000 to John")
        assert result.get("blocked") is True
        assert not any(e["action_id"] == "payments.send" for e in bus._execution_log)

    asyncio.run(run())


def test_unknown_text_gets_chat_fallback():
    async def run():
        pipeline, _ = _make_pipeline()
        result = await pipeline.handle("how are you doing today")
        assert result["success"] is None
        assert result["reply"]  # helpful guidance, not an error

    asyncio.run(run())


def test_speculative_cache_serves_command():
    from backend.execution.speculative import SpeculativeEngine, PredictedAction

    async def run():
        pipeline, bus = _make_pipeline()
        engine = SpeculativeEngine()
        engine.set_executor(bus.execute)

        async def predictor(ctx):
            return [PredictedAction(
                action_id="calendar.get_upcoming", params={},
                confidence=0.9, reason="test",
            )]

        engine.add_predictor(predictor)
        await engine._cycle({})

        pipeline.speculative = engine
        result = await pipeline.handle("what's on my calendar")
        assert result["success"] is True
        assert result.get("cached") is True

    asyncio.run(run())


def test_conversation_history_recorded():
    async def run():
        pipeline, _ = _make_pipeline()
        await pipeline.handle("volume 25")
        await pipeline.handle("what's on my calendar")
        assert len(pipeline._history) == 2
        assert pipeline._history[0][0] == "volume 25"
        assert pipeline._history_context().startswith("Recent conversation:")

    asyncio.run(run())


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  PASS {name}")
    print("All command pipeline tests passed")
