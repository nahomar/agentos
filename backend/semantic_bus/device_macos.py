from __future__ import annotations

"""
Real device execution on macOS.

The backend usually runs on a Mac — which is itself a device. This module
implements semantic bus actions with real side effects via osascript and
`open`: volume actually changes, music actually plays, confirmed iMessages
actually send. Handlers fall back to simulated results if anything here
raises (app missing, TCC permission denied, not macOS).

Security: every user-supplied string that reaches AppleScript goes through
applescript_escape() — quotes and backslashes are escaped so input like
'foo" \n tell app ...' cannot inject script.
"""

import asyncio
import logging
import shutil
import sys
import urllib.parse

logger = logging.getLogger("device_macos")

OSASCRIPT_TIMEOUT = 15


def applescript_escape(value) -> str:
    """Escape a value for safe embedding inside an AppleScript string literal."""
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


class MacDeviceExecutor:
    """Executes semantic bus actions for real on this Mac."""

    @staticmethod
    def available() -> bool:
        return sys.platform == "darwin" and shutil.which("osascript") is not None

    async def _osascript(self, script: str) -> str:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), OSASCRIPT_TIMEOUT)
        except asyncio.TimeoutError:
            proc.kill()
            raise RuntimeError("osascript timed out")
        if proc.returncode != 0:
            raise RuntimeError(err.decode().strip() or "osascript failed")
        return out.decode().strip()

    async def _open(self, target: str):
        """Open a URL or app via the system `open` command."""
        proc = await asyncio.create_subprocess_exec(
            "open", target,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, err = await asyncio.wait_for(proc.communicate(), 10)
        if proc.returncode != 0:
            raise RuntimeError(err.decode().strip() or f"open failed: {target}")

    # === Settings ===

    async def set_volume(self, params: dict) -> dict:
        level = max(0, min(100, int(params.get("level", 50))))
        await self._osascript(f"set volume output volume {level}")
        return {"volume": level}

    # === Music (Spotify app preferred, Music.app fallback) ===

    async def _music_app(self) -> str:
        running = await self._osascript(
            'tell application "System Events" to get name of every process '
            'whose name is "Spotify"'
        )
        return "Spotify" if "Spotify" in running else "Music"

    async def play_track(self, params: dict) -> dict:
        query = params.get("query", "")
        if not query:
            app = await self._music_app()
            await self._osascript(f'tell application "{app}" to play')
            return {"playing": True, "app": app}
        # No public search-and-play AppleScript API — open the search so one
        # tap starts it, and resume playback if something was paused
        encoded = urllib.parse.quote(query)
        await self._open(f"spotify:search:{encoded}")
        return {"opened_search": query, "app": "Spotify"}

    async def play_playlist(self, params: dict) -> dict:
        name = params.get("name", "")
        encoded = urllib.parse.quote(name)
        await self._open(f"spotify:search:{encoded}")
        return {"opened_search": name, "app": "Spotify"}

    async def pause(self, params: dict) -> dict:
        app = await self._music_app()
        await self._osascript(f'tell application "{app}" to pause')
        return {"paused": True, "app": app}

    async def get_now_playing(self, params: dict) -> dict:
        app = await self._music_app()
        state = await self._osascript(f'tell application "{app}" to player state as string')
        if state != "playing":
            return {"playback": None, "state": state, "app": app}
        track = await self._osascript(
            f'tell application "{app}" to name of current track & " — " & '
            f'artist of current track'
        )
        return {"playback": track, "state": "playing", "app": app}

    # === Messages (iMessage) — only reachable after user confirmation ===

    async def send_message(self, params: dict) -> dict:
        recipient = applescript_escape(params.get("recipient", ""))
        body = applescript_escape(params.get("body", ""))
        await self._osascript(
            'tell application "Messages"\n'
            '  set targetService to 1st account whose service type = iMessage\n'
            f'  set targetBuddy to participant "{recipient}" of targetService\n'
            f'  send "{body}" to targetBuddy\n'
            'end tell'
        )
        return {"sent": True, "recipient": params.get("recipient"),
                "body": params.get("body"), "via": "iMessage"}

    # === Phone (FaceTime) — macOS shows its own confirm prompt too ===

    async def call(self, params: dict) -> dict:
        recipient = str(params.get("recipient", "")).strip()
        digits = recipient.replace(" ", "").replace("-", "")
        if not digits or not all(c.isdigit() or c == "+" for c in digits):
            raise RuntimeError("FaceTime call needs a phone number")
        await self._open(f"tel:{urllib.parse.quote(digits)}")
        return {"calling": recipient, "via": "FaceTime"}

    # === Browser / Maps ===

    async def open_url(self, params: dict) -> dict:
        url = str(params.get("url", ""))
        if not url.startswith(("http://", "https://")):
            raise RuntimeError("Only http(s) URLs can be opened")
        await self._open(url)
        return {"opened": url}

    async def search(self, params: dict) -> dict:
        query = params.get("query", "")
        url = f"https://duckduckgo.com/?q={urllib.parse.quote(query)}"
        await self._open(url)
        return {"query": query, "opened": url}

    async def navigate(self, params: dict) -> dict:
        dest = params.get("destination", "")
        await self._open(f"maps://?daddr={urllib.parse.quote(dest)}")
        return {"destination": dest, "opened_in": "Apple Maps"}

    async def find_nearby(self, params: dict) -> dict:
        query = params.get("query", "")
        await self._open(f"maps://?q={urllib.parse.quote(query)}")
        return {"query": query, "opened_in": "Apple Maps"}

    # === Notes ===

    async def create_note(self, params: dict) -> dict:
        title = applescript_escape(params.get("title", "Note"))
        content = applescript_escape(params.get("content", ""))
        await self._osascript(
            f'tell application "Notes" to make new note with properties '
            f'{{name:"{title}", body:"{content}"}}'
        )
        return {"created": True, "title": params.get("title"), "app": "Notes"}


# Maps action_id -> MacDeviceExecutor method name
MAC_ACTION_METHODS = {
    "settings.set_volume": "set_volume",
    "spotify.play_track": "play_track",
    "spotify.play_playlist": "play_playlist",
    "spotify.pause": "pause",
    "spotify.get_now_playing": "get_now_playing",
    "messages.send": "send_message",
    "phone.call": "call",
    "browser.open_url": "open_url",
    "browser.search": "search",
    "maps.navigate": "navigate",
    "maps.find_nearby": "find_nearby",
    "notes.create": "create_note",
}
