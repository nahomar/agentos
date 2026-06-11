from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("spotify_auth")

TOKEN_FILE = Path(__file__).parent.parent / "data" / "spotify_token.json"
SCOPES = [
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
    "user-read-recently-played",
    "user-top-read",
    "playlist-read-private",
    "playlist-modify-public",
    "playlist-modify-private",
]


class SpotifyAuth:
    """Manages Spotify OAuth2 token lifecycle."""

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str = ""):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri or "http://localhost:8000/api/spotify/callback"
        self._token_data = self._load_token()

    def _load_token(self) -> Optional[dict]:
        if TOKEN_FILE.exists():
            try:
                with open(TOKEN_FILE) as f:
                    data = json.load(f)
                    return data
            except Exception:
                pass
        return None

    def _save_token(self, data: dict):
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_FILE, "w") as f:
            json.dump(data, f)
        import os
        os.chmod(str(TOKEN_FILE), 0o600)  # H8: restrict token file
        self._token_data = data

    @property
    def is_authenticated(self) -> bool:
        return self._token_data is not None and "access_token" in self._token_data

    @property
    def access_token(self) -> Optional[str]:
        if not self._token_data:
            return None

        # Check if token is expired
        expires_at = self._token_data.get("expires_at", 0)
        if time.time() > expires_at - 60:  # Refresh 60s before expiry
            if self._refresh_token():
                return self._token_data.get("access_token")
            return None

        return self._token_data.get("access_token")

    def get_auth_url(self) -> str:
        """Get the Spotify authorization URL for user to visit."""
        import urllib.parse
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(SCOPES),
            "show_dialog": "true",
        }
        return "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(params)

    async def exchange_code(self, code: str) -> bool:
        """Exchange authorization code for access token."""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://accounts.spotify.com/api/token",
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": self.redirect_uri,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    data["expires_at"] = time.time() + data.get("expires_in", 3600)
                    self._save_token(data)
                    logger.info("Spotify authenticated successfully")
                    return True
                else:
                    logger.error(f"Spotify token exchange failed: {resp.text}")
                    return False
        except Exception as e:
            logger.error(f"Spotify auth error: {e}")
            return False

    def _refresh_token(self) -> bool:
        """Refresh the access token using the refresh token."""
        refresh_token = self._token_data.get("refresh_token")
        if not refresh_token:
            return False

        try:
            import httpx
            with httpx.Client() as client:
                resp = client.post(
                    "https://accounts.spotify.com/api/token",
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    data["refresh_token"] = refresh_token  # Keep the refresh token
                    data["expires_at"] = time.time() + data.get("expires_in", 3600)
                    self._save_token(data)
                    logger.info("Spotify token refreshed")
                    return True
        except Exception as e:
            logger.error(f"Spotify refresh error: {e}")

        return False

    async def get_current_playback(self) -> Optional[dict]:
        """Get currently playing track."""
        token = self.access_token
        if not token:
            return None

        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api.spotify.com/v1/me/player",
                    headers={"Authorization": f"Bearer {token}"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    item = data.get("item", {})
                    return {
                        "is_playing": data.get("is_playing", False),
                        "track": item.get("name", ""),
                        "artist": item.get("artists", [{}])[0].get("name", ""),
                        "album": item.get("album", {}).get("name", ""),
                        "progress_ms": data.get("progress_ms", 0),
                        "duration_ms": item.get("duration_ms", 0),
                    }
        except Exception:
            pass
        return None

    async def play(self, uri: str = None, context_uri: str = None) -> bool:
        """Start/resume playback or play a specific track."""
        token = self.access_token
        if not token:
            return False

        try:
            import httpx
            body = {}
            if uri:
                body["uris"] = [uri]
            elif context_uri:
                body["context_uri"] = context_uri

            async with httpx.AsyncClient() as client:
                resp = await client.put(
                    "https://api.spotify.com/v1/me/player/play",
                    headers={"Authorization": f"Bearer {token}"},
                    json=body if body else None,
                )
                return resp.status_code in (200, 204)
        except Exception:
            return False

    async def search(self, query: str, type: str = "track", limit: int = 5) -> list:
        """Search Spotify."""
        token = self.access_token
        if not token:
            return []

        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api.spotify.com/v1/search",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"q": query, "type": type, "limit": limit},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    tracks = data.get("tracks", {}).get("items", [])
                    return [
                        {
                            "name": t["name"],
                            "artist": t["artists"][0]["name"],
                            "uri": t["uri"],
                            "album": t["album"]["name"],
                        }
                        for t in tracks
                    ]
        except Exception:
            pass
        return []

    async def get_recently_played(self, limit: int = 10) -> list:
        """Get recently played tracks."""
        token = self.access_token
        if not token:
            return []

        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api.spotify.com/v1/me/player/recently-played",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"limit": limit},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return [
                        {
                            "track": item["track"]["name"],
                            "artist": item["track"]["artists"][0]["name"],
                            "played_at": item["played_at"],
                        }
                        for item in data.get("items", [])
                    ]
        except Exception:
            pass
        return []
