"""Tests for real device execution: AppleScript escaping, device-first
fallback semantics, and that simulation stays the default."""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_applescript_escape_blocks_injection():
    from backend.semantic_bus.device_macos import applescript_escape

    assert applescript_escape('hello "world"') == 'hello \\"world\\"'
    assert applescript_escape("back\\slash") == "back\\\\slash"
    # A classic breakout attempt stays inside the string literal
    evil = '" \n tell application "Finder" to delete every item of desktop \n "'
    escaped = applescript_escape(evil)
    assert '\\"' in escaped
    # No unescaped double quote remains
    assert '"' not in escaped.replace('\\"', "")


def test_device_first_uses_device_result():
    from backend.semantic_bus.handlers import _device_first

    class FakeDevice:
        async def set_volume(self, params):
            return {"volume": params["level"]}

    async def fallback(params):
        return {"volume": params["level"], "simulated": True}

    async def run():
        handler = _device_first(FakeDevice(), "set_volume", fallback)
        result = await handler({"level": 40})
        assert result["simulated"] is False
        assert result["device"] == "macos"
        assert result["volume"] == 40

    asyncio.run(run())


def test_device_first_falls_back_on_error():
    from backend.semantic_bus.handlers import _device_first

    class BrokenDevice:
        async def set_volume(self, params):
            raise RuntimeError("osascript missing")

    async def fallback(params):
        return {"volume": params["level"], "simulated": True}

    async def run():
        handler = _device_first(BrokenDevice(), "set_volume", fallback)
        result = await handler({"level": 40})
        assert result["simulated"] is True  # graceful degradation

    asyncio.run(run())


def test_default_config_stays_simulated():
    from backend.semantic_bus.handlers import get_builtin_handlers

    async def run():
        handlers = get_builtin_handlers({})  # no device_execution flag
        result = await handlers["settings.set_volume"]({"level": 10})
        assert result.get("simulated") is True

    asyncio.run(run())


def test_mac_action_map_matches_executor_methods():
    from backend.semantic_bus.device_macos import MacDeviceExecutor, MAC_ACTION_METHODS

    for action_id, method in MAC_ACTION_METHODS.items():
        assert hasattr(MacDeviceExecutor, method), (
            f"{action_id} maps to missing method {method}"
        )


def test_call_rejects_non_numeric_recipient():
    from backend.semantic_bus.device_macos import MacDeviceExecutor

    async def run():
        device = MacDeviceExecutor()
        try:
            await device.call({"recipient": "Mom"})
            assert False, "expected RuntimeError for non-numeric recipient"
        except RuntimeError:
            pass

    asyncio.run(run())


def test_open_url_rejects_non_http_schemes():
    from backend.semantic_bus.device_macos import MacDeviceExecutor

    async def run():
        device = MacDeviceExecutor()
        for url in ("file:///etc/passwd", "javascript:alert(1)", "ftp://x"):
            try:
                await device.open_url({"url": url})
                assert False, f"expected rejection for {url}"
            except RuntimeError:
                pass

    asyncio.run(run())


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  PASS {name}")
    print("All device execution tests passed")
