from __future__ import annotations

"""
Built-in app action schemas for the Semantic Bus.
These define what agents can DO — not what they see on screen.
"""

from backend.semantic_bus.schema import (
    ActionSchema, ActionParam, AppManifest, ParamType, RiskLevel,
)


def get_builtin_apps() -> list:
    """Return all built-in app manifests with their action schemas."""
    return [
        _spotify_app(),
        _messages_app(),
        _phone_app(),
        _camera_app(),
        _maps_app(),
        _calendar_app(),
        _notes_app(),
        _browser_app(),
        _payments_app(),
        _settings_app(),
    ]


def _spotify_app() -> AppManifest:
    return AppManifest(
        app_id="spotify",
        name="Spotify",
        version="1.0",
        description="Music streaming and playback control",
        actions=[
            ActionSchema(
                id="spotify.play_track",
                app_id="spotify",
                name="Play Track",
                description="Play a specific track or search query",
                params=[
                    ActionParam("query", ParamType.STRING, "Track name or search query"),
                    ActionParam("uri", ParamType.STRING, "Spotify URI", required=False),
                ],
                risk_level=RiskLevel.SAFE,
                tags=["music", "play", "audio"],
            ),
            ActionSchema(
                id="spotify.play_playlist",
                app_id="spotify",
                name="Play Playlist",
                description="Play a playlist by name or mood",
                params=[
                    ActionParam("name", ParamType.STRING, "Playlist name or mood"),
                ],
                risk_level=RiskLevel.SAFE,
                tags=["music", "playlist"],
            ),
            ActionSchema(
                id="spotify.pause",
                app_id="spotify",
                name="Pause",
                description="Pause current playback",
                params=[],
                risk_level=RiskLevel.SAFE,
                tags=["music", "control"],
            ),
            ActionSchema(
                id="spotify.get_now_playing",
                app_id="spotify",
                name="Now Playing",
                description="Get currently playing track info",
                params=[],
                risk_level=RiskLevel.SAFE,
                tags=["music", "info"],
            ),
        ],
        events=["spotify.track_changed", "spotify.playback_paused"],
        auth_type="oauth2",
    )


def _messages_app() -> AppManifest:
    return AppManifest(
        app_id="messages",
        name="Messages",
        version="1.0",
        description="Send and read text messages",
        actions=[
            ActionSchema(
                id="messages.send",
                app_id="messages",
                name="Send Message",
                description="Send a text message to a contact",
                params=[
                    ActionParam("recipient", ParamType.CONTACT, "Contact name or phone number"),
                    ActionParam("body", ParamType.STRING, "Message text"),
                ],
                risk_level=RiskLevel.HIGH,
                requires_auth=True,
                tags=["message", "text", "sms", "communication"],
            ),
            ActionSchema(
                id="messages.get_unread",
                app_id="messages",
                name="Get Unread Messages",
                description="Get list of unread messages",
                params=[
                    ActionParam("limit", ParamType.NUMBER, "Max messages", required=False, default=10),
                ],
                risk_level=RiskLevel.SAFE,
                tags=["message", "read", "inbox"],
            ),
            ActionSchema(
                id="messages.draft_reply",
                app_id="messages",
                name="Draft Reply",
                description="Draft a reply to a message (requires user approval to send)",
                params=[
                    ActionParam("thread_id", ParamType.STRING, "Message thread ID"),
                    ActionParam("body", ParamType.STRING, "Reply text"),
                ],
                risk_level=RiskLevel.MEDIUM,
                tags=["message", "reply", "draft"],
            ),
        ],
        events=["messages.received", "messages.sent"],
        auth_type="session",
    )


def _phone_app() -> AppManifest:
    return AppManifest(
        app_id="phone",
        name="Phone",
        version="1.0",
        description="Make and manage phone calls",
        actions=[
            ActionSchema(
                id="phone.call",
                app_id="phone",
                name="Make Call",
                description="Call a contact or phone number",
                params=[
                    ActionParam("recipient", ParamType.CONTACT, "Contact name or phone number"),
                ],
                risk_level=RiskLevel.HIGH,
                requires_auth=True,
                tags=["call", "phone", "communication"],
            ),
            ActionSchema(
                id="phone.get_recents",
                app_id="phone",
                name="Recent Calls",
                description="Get recent call history",
                params=[
                    ActionParam("limit", ParamType.NUMBER, "Max results", required=False, default=10),
                ],
                risk_level=RiskLevel.SAFE,
                tags=["call", "history"],
            ),
        ],
        events=["phone.incoming_call", "phone.call_ended", "phone.missed_call"],
        auth_type="session",
    )


def _camera_app() -> AppManifest:
    return AppManifest(
        app_id="camera",
        name="Camera",
        version="1.0",
        description="Capture photos and videos",
        actions=[
            ActionSchema(
                id="camera.take_photo",
                app_id="camera",
                name="Take Photo",
                description="Capture a photo with the camera",
                params=[
                    ActionParam("mode", ParamType.ENUM, "Camera mode", required=False,
                               default="auto", enum_values=["auto", "portrait", "landscape", "night"]),
                    ActionParam("reason", ParamType.STRING, "Why taking this photo", required=False),
                ],
                risk_level=RiskLevel.LOW,
                tags=["photo", "camera", "capture"],
            ),
        ],
        events=["camera.photo_taken"],
    )


def _maps_app() -> AppManifest:
    return AppManifest(
        app_id="maps",
        name="Maps",
        version="1.0",
        description="Navigation and location services",
        actions=[
            ActionSchema(
                id="maps.navigate",
                app_id="maps",
                name="Navigate",
                description="Get directions to a destination",
                params=[
                    ActionParam("destination", ParamType.STRING, "Destination address or place"),
                    ActionParam("mode", ParamType.ENUM, "Travel mode", required=False,
                               default="driving", enum_values=["driving", "walking", "transit"]),
                ],
                risk_level=RiskLevel.SAFE,
                tags=["navigation", "directions", "maps"],
            ),
            ActionSchema(
                id="maps.find_nearby",
                app_id="maps",
                name="Find Nearby",
                description="Search for nearby places",
                params=[
                    ActionParam("query", ParamType.STRING, "What to search for"),
                    ActionParam("radius_km", ParamType.NUMBER, "Search radius", required=False, default=5),
                ],
                risk_level=RiskLevel.SAFE,
                tags=["search", "places", "nearby"],
            ),
        ],
        events=["maps.arrived_destination"],
    )


def _calendar_app() -> AppManifest:
    return AppManifest(
        app_id="calendar",
        name="Calendar",
        version="1.0",
        description="Schedule and event management",
        actions=[
            ActionSchema(
                id="calendar.create_event",
                app_id="calendar",
                name="Create Event",
                description="Add a new calendar event",
                params=[
                    ActionParam("title", ParamType.STRING, "Event title"),
                    ActionParam("start", ParamType.DATE, "Start time"),
                    ActionParam("duration_minutes", ParamType.NUMBER, "Duration", required=False, default=60),
                    ActionParam("location", ParamType.STRING, "Location", required=False),
                ],
                risk_level=RiskLevel.LOW,
                tags=["calendar", "schedule", "event"],
            ),
            ActionSchema(
                id="calendar.get_upcoming",
                app_id="calendar",
                name="Upcoming Events",
                description="Get upcoming calendar events",
                params=[
                    ActionParam("hours", ParamType.NUMBER, "Hours ahead to look", required=False, default=24),
                ],
                risk_level=RiskLevel.SAFE,
                tags=["calendar", "schedule"],
            ),
        ],
        events=["calendar.event_starting", "calendar.event_created"],
    )


def _notes_app() -> AppManifest:
    return AppManifest(
        app_id="notes",
        name="Notes",
        version="1.0",
        description="Note-taking and text storage",
        actions=[
            ActionSchema(
                id="notes.create",
                app_id="notes",
                name="Create Note",
                description="Create a new note",
                params=[
                    ActionParam("title", ParamType.STRING, "Note title"),
                    ActionParam("content", ParamType.STRING, "Note content"),
                ],
                risk_level=RiskLevel.SAFE,
                tags=["notes", "write", "save"],
            ),
            ActionSchema(
                id="notes.search",
                app_id="notes",
                name="Search Notes",
                description="Search through notes",
                params=[
                    ActionParam("query", ParamType.STRING, "Search query"),
                ],
                risk_level=RiskLevel.SAFE,
                tags=["notes", "search"],
            ),
        ],
        events=["notes.created", "notes.updated"],
    )


def _browser_app() -> AppManifest:
    return AppManifest(
        app_id="browser",
        name="Browser",
        version="1.0",
        description="Web browsing and research",
        actions=[
            ActionSchema(
                id="browser.search",
                app_id="browser",
                name="Web Search",
                description="Search the web",
                params=[
                    ActionParam("query", ParamType.STRING, "Search query"),
                ],
                risk_level=RiskLevel.SAFE,
                tags=["search", "web", "browse"],
            ),
            ActionSchema(
                id="browser.open_url",
                app_id="browser",
                name="Open URL",
                description="Open a webpage",
                params=[
                    ActionParam("url", ParamType.URL, "URL to open"),
                ],
                risk_level=RiskLevel.SAFE,
                tags=["web", "browse", "open"],
            ),
        ],
        events=[],
    )


def _payments_app() -> AppManifest:
    return AppManifest(
        app_id="payments",
        name="Payments",
        version="1.0",
        description="Send and receive money",
        actions=[
            ActionSchema(
                id="payments.send",
                app_id="payments",
                name="Send Payment",
                description="Send money to someone",
                params=[
                    ActionParam("recipient", ParamType.CONTACT, "Recipient"),
                    ActionParam("amount", ParamType.CURRENCY, "Amount to send",
                               constraints={"min": 0.01, "max": 10000}),
                    ActionParam("currency", ParamType.ENUM, "Currency", required=False,
                               default="USD", enum_values=["USD", "EUR", "GBP", "ETB"]),
                    ActionParam("note", ParamType.STRING, "Payment note", required=False),
                ],
                risk_level=RiskLevel.CRITICAL,
                requires_auth=True,
                tags=["payment", "money", "send", "finance"],
            ),
            ActionSchema(
                id="payments.get_balance",
                app_id="payments",
                name="Get Balance",
                description="Check account balance",
                params=[],
                risk_level=RiskLevel.MEDIUM,
                requires_auth=True,
                tags=["payment", "balance", "finance"],
            ),
        ],
        events=["payments.received", "payments.sent"],
        auth_type="oauth2",
    )


def _settings_app() -> AppManifest:
    return AppManifest(
        app_id="settings",
        name="Settings",
        version="1.0",
        description="Device settings and configuration",
        actions=[
            ActionSchema(
                id="settings.set_volume",
                app_id="settings",
                name="Set Volume",
                description="Adjust device volume",
                params=[
                    ActionParam("level", ParamType.NUMBER, "Volume 0-100",
                               constraints={"min": 0, "max": 100}),
                ],
                risk_level=RiskLevel.SAFE,
                tags=["settings", "volume", "audio"],
            ),
            ActionSchema(
                id="settings.toggle_dnd",
                app_id="settings",
                name="Do Not Disturb",
                description="Toggle Do Not Disturb mode",
                params=[
                    ActionParam("enabled", ParamType.BOOLEAN, "Enable DND"),
                    ActionParam("duration_minutes", ParamType.NUMBER, "Duration", required=False),
                ],
                risk_level=RiskLevel.LOW,
                tags=["settings", "dnd", "focus"],
            ),
        ],
        events=["settings.dnd_changed"],
    )
