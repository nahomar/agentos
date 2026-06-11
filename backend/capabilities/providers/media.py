from __future__ import annotations

import logging
from backend.capabilities.registry import CapabilityProvider, CapabilityResult

logger = logging.getLogger("capabilities.media")


class SpotifyPlayProvider(CapabilityProvider):
    id = "media.play_music"
    name = "Play Music"
    description = "Play music on Spotify"
    category = "media"

    @property
    def available(self) -> bool:
        return True  # Demo mode always available

    async def execute(self, params: dict) -> CapabilityResult:
        query = params.get("query", "")
        track_uri = params.get("track_uri", "")
        playlist = params.get("playlist", "")

        client_id = self.config.get("spotify_client_id", "")
        client_secret = self.config.get("spotify_client_secret", "")

        if client_id and client_secret:
            try:
                import spotipy
                from spotipy.oauth2 import SpotifyClientCredentials
                sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
                    client_id=client_id, client_secret=client_secret,
                ))
                if query:
                    results = sp.search(q=query, limit=1, type="track")
                    tracks = results.get("tracks", {}).get("items", [])
                    if tracks:
                        track = tracks[0]
                        return CapabilityResult(success=True, data={
                            "track": track["name"],
                            "artist": track["artists"][0]["name"],
                            "uri": track["uri"],
                        })
            except Exception as e:
                logger.error(f"Spotify API error: {e}")

        return CapabilityResult(success=True, data={
            "demo": True,
            "message": f"[Demo] Would play: {query or playlist or 'Focus playlist'}",
        })


class CameraTriggerProvider(CapabilityProvider):
    id = "media.take_photo"
    name = "Take Photo"
    description = "Trigger camera to take a photo via iOS Shortcut"
    category = "media"

    @property
    def available(self) -> bool:
        return True  # Demo mode always available

    async def execute(self, params: dict) -> CapabilityResult:
        pushcut_url = self.config.get("pushcut_webhook", "")

        if pushcut_url:
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        f"{pushcut_url}/take-photo",
                        json={"reason": params.get("reason", "Beautiful moment detected")},
                    )
                    if resp.status_code == 200:
                        return CapabilityResult(success=True, data={"triggered": True})
            except Exception as e:
                logger.error(f"Pushcut error: {e}")

        return CapabilityResult(success=True, data={
            "demo": True,
            "message": f"[Demo] Would take photo: {params.get('reason', 'nice view')}",
        })
