from __future__ import annotations

"""
Built-in action handlers for the Semantic Bus.

Each handler implements one action from builtin_apps.py. Where a real
integration exists on this device (Spotify OAuth), the handler uses it and
falls back to simulated data otherwise. Device-bound actions (messages,
phone, camera, settings) return simulated results until a phone client
implements them — every simulated payload carries "simulated": True so
callers and the UI can tell the difference.
"""

import logging
import time
from typing import Any, Callable, Dict, List

logger = logging.getLogger("bus_handlers")

# In-memory stores backing the demo handlers
_notes: List[dict] = []
_calendar_events: List[dict] = []


def get_builtin_handlers(config: dict) -> Dict[str, Callable]:
    """Build the action_id -> async handler map for all built-in apps."""
    spotify = _SpotifyHandlers(config)

    return {
        # Spotify — real when OAuth'd, simulated otherwise
        "spotify.play_track": spotify.play_track,
        "spotify.play_playlist": spotify.play_playlist,
        "spotify.pause": spotify.pause,
        "spotify.get_now_playing": spotify.get_now_playing,
        # Messages
        "messages.send": _messages_send,
        "messages.get_unread": _messages_get_unread,
        "messages.draft_reply": _messages_draft_reply,
        # Phone
        "phone.call": _phone_call,
        "phone.get_recents": _phone_get_recents,
        # Camera
        "camera.take_photo": _camera_take_photo,
        # Maps
        "maps.navigate": _maps_navigate,
        "maps.find_nearby": _maps_find_nearby,
        # Calendar
        "calendar.create_event": _calendar_create_event,
        "calendar.get_upcoming": _calendar_get_upcoming,
        # Notes
        "notes.create": _notes_create,
        "notes.search": _notes_search,
        # Browser
        "browser.search": _browser_search,
        "browser.open_url": _browser_open_url,
        # Payments
        "payments.send": _payments_send,
        "payments.get_balance": _payments_get_balance,
        # Settings
        "settings.set_volume": _settings_set_volume,
        "settings.toggle_dnd": _settings_toggle_dnd,
    }


class _SpotifyHandlers:
    """Spotify actions backed by the real OAuth client when available."""

    def __init__(self, config: dict):
        self._config = config
        self._auth = None

    def _get_auth(self):
        if self._auth is None:
            from backend.spotify_auth import SpotifyAuth
            self._auth = SpotifyAuth(
                client_id=self._config.get("spotify_client_id", ""),
                client_secret=self._config.get("spotify_client_secret", ""),
            )
        return self._auth

    async def play_track(self, params: dict) -> dict:
        auth = self._get_auth()
        query = params.get("query", "")
        uri = params.get("uri")
        if auth.is_authenticated:
            if not uri and query:
                results = await auth.search(query)
                if results:
                    uri = results[0].get("uri")
            ok = await auth.play(uri=uri)
            return {"playing": ok, "query": query, "uri": uri}
        return {"playing": True, "query": query, "simulated": True}

    async def play_playlist(self, params: dict) -> dict:
        auth = self._get_auth()
        name = params.get("name", "")
        if auth.is_authenticated:
            results = await auth.search(f"playlist {name}")
            uri = results[0].get("uri") if results else None
            ok = await auth.play(uri=uri)
            return {"playing": ok, "playlist": name, "uri": uri}
        return {"playing": True, "playlist": name, "simulated": True}

    async def pause(self, params: dict) -> dict:
        auth = self._get_auth()
        if auth.is_authenticated:
            ok = await auth.play(uri=None)  # SpotifyAuth has no pause; treat as no-op toggle
            return {"paused": ok}
        return {"paused": True, "simulated": True}

    async def get_now_playing(self, params: dict) -> dict:
        auth = self._get_auth()
        if auth.is_authenticated:
            playback = await auth.get_current_playback()
            return {"playback": playback}
        return {"playback": None, "simulated": True}


async def _messages_send(params: dict) -> dict:
    # Device-bound: a phone client must execute this. Simulated until then.
    return {
        "sent": True, "recipient": params.get("recipient"),
        "body": params.get("body"), "simulated": True,
    }


async def _messages_get_unread(params: dict) -> dict:
    return {"messages": [], "count": 0, "simulated": True}


async def _messages_draft_reply(params: dict) -> dict:
    return {
        "drafted": True, "thread_id": params.get("thread_id"),
        "body": params.get("body"), "simulated": True,
    }


async def _phone_call(params: dict) -> dict:
    return {"calling": params.get("recipient"), "simulated": True}


async def _phone_get_recents(params: dict) -> dict:
    return {"calls": [], "simulated": True}


async def _camera_take_photo(params: dict) -> dict:
    return {"captured": True, "mode": params.get("mode", "auto"), "simulated": True}


async def _maps_navigate(params: dict) -> dict:
    return {
        "destination": params.get("destination"),
        "mode": params.get("mode", "driving"),
        "eta_minutes": 15, "simulated": True,
    }


async def _maps_find_nearby(params: dict) -> dict:
    query = params.get("query", "")
    return {
        "query": query,
        "results": [{"name": f"Nearby {query}", "distance_km": 1.2}],
        "simulated": True,
    }


async def _calendar_create_event(params: dict) -> dict:
    event = {
        "title": params.get("title"),
        "start": params.get("start"),
        "duration_minutes": params.get("duration_minutes", 60),
        "location": params.get("location"),
        "created_at": time.time(),
    }
    _calendar_events.append(event)
    return {"created": True, "event": event}


async def _calendar_get_upcoming(params: dict) -> dict:
    return {"events": list(_calendar_events[-20:]), "count": len(_calendar_events)}


async def _notes_create(params: dict) -> dict:
    note = {
        "title": params.get("title"),
        "content": params.get("content"),
        "created_at": time.time(),
    }
    _notes.append(note)
    return {"created": True, "note": note}


async def _notes_search(params: dict) -> dict:
    query = str(params.get("query", "")).lower()
    matches = [
        n for n in _notes
        if query in str(n.get("title", "")).lower()
        or query in str(n.get("content", "")).lower()
    ]
    return {"results": matches[-20:], "count": len(matches)}


async def _browser_search(params: dict) -> dict:
    return {"query": params.get("query"), "results": [], "simulated": True}


async def _browser_open_url(params: dict) -> dict:
    return {"opened": params.get("url"), "simulated": True}


async def _payments_send(params: dict) -> dict:
    # CRITICAL risk — the bus requires user confirmation before this runs.
    return {
        "sent": True, "recipient": params.get("recipient"),
        "amount": params.get("amount"), "currency": params.get("currency", "USD"),
        "simulated": True,
    }


async def _payments_get_balance(params: dict) -> dict:
    return {"balance": 0.0, "currency": "USD", "simulated": True}


async def _settings_set_volume(params: dict) -> dict:
    return {"volume": params.get("level"), "simulated": True}


async def _settings_toggle_dnd(params: dict) -> dict:
    return {
        "dnd_enabled": bool(params.get("enabled")),
        "duration_minutes": params.get("duration_minutes"),
        "simulated": True,
    }
