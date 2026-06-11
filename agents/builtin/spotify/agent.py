from __future__ import annotations

import random
import logging

from backend.agents.base import BaseAgent
from backend.bus import MessageBus
from backend.memory import SharedMemory

logger = logging.getLogger("agents.spotify")

DEMO_TRACKS = [
    {"track": "Fikir Yalew", "artist": "Teddy Afro", "genre": "Ethiopian pop"},
    {"track": "Midnight Drive", "artist": "Lo-Fi Chill", "genre": "lo-fi beats"},
    {"track": "Deep Focus", "artist": "Brain.fm", "genre": "focus music"},
    {"track": "Money Trees", "artist": "Kendrick Lamar", "genre": "hip-hop"},
    {"track": "Electric Feel", "artist": "MGMT", "genre": "electronic"},
    {"track": "Blinding Lights", "artist": "The Weeknd", "genre": "r&b"},
    {"track": "Ayat", "artist": "Zeritu Kebede", "genre": "Ethiopian"},
    {"track": "Snowfall", "artist": "Øneheart", "genre": "ambient"},
    {"track": "Good Days", "artist": "SZA", "genre": "r&b"},
    {"track": "Tadias", "artist": "Rophnan", "genre": "Ethiopian electronic"},
    {"track": "Retrograde", "artist": "James Blake", "genre": "electronic"},
    {"track": "Neon Lights", "artist": "Synthwave Collective", "genre": "synthwave"},
]

DEMO_DISCOVERIES = [
    "Found a fire playlist mixing Ethiopian jazz with lo-fi beats — 'Ethio-Chill Sessions'. Perfect for coding.",
    "Rophnan just dropped a new single blending traditional Ethiopian scales with electronic production. It's incredible.",
    "Your top genre this week: lo-fi beats (62% of listening time). You coded 3x longer during lo-fi sessions btw.",
    "Discovered an underground artist 'Addis Synth' — Ethiopian electronic fusion. Only 2K monthly listeners but the sound is next level.",
    "New release alert: The Weeknd's 'After Hours' extended mix is out. Based on your R&B plays, you'll probably loop this.",
    "Created a smart mix based on your recent vibes: 'Late Night Coding' — 80bpm, minimal vocals, deep bass. 47 tracks.",
]

DEMO_CHATS = [
    "yo {agent}, you should check this out — found a track that matches the vibe of what you're researching 🎵",
    "the algorithm just served me something wild — {genre} is trending up 200% this month",
    "hey {agent}, fun fact: {user}'s listening patterns show peak focus during {genre} sessions. science, baby 🎧",
    "new drop alert! this track goes hard. sending it to the group 🔥",
]


class SpotifyAgent(BaseAgent):
    name = "Spotify"
    emoji = "🎵"
    color = "#1DB954"
    app_name = "Spotify"
    personality = "chill, music-obsessed, uses music metaphors, always vibing"

    def __init__(self, bus: MessageBus, memory: SharedMemory, config: dict | None = None):
        super().__init__(bus, memory, config)
        self._client_id = (config or {}).get("spotify_client_id", "")
        self._client_secret = (config or {}).get("spotify_client_secret", "")
        self._cycle_count = 0

    @property
    def has_api_key(self) -> bool:
        return bool(self._client_id and self._client_secret)

    async def run_cycle(self):
        self._cycle_count += 1
        genres = self.config.get("spotify_genres", ["lo-fi", "hip-hop", "r&b"])
        genre = random.choice(genres) if genres else "lo-fi"

        result = await self.think(
            f"You're a music discovery agent. The user likes {', '.join(genres)}. "
            f"Share a music discovery — a new track, an underrated artist, a playlist idea, "
            f"or an interesting listening pattern. Be specific with artist/track names. "
            f"Stay chill and music-obsessed."
        )
        if result:
            await self.broadcast_status(f"discovered something in {genre}...")
            await self.report_finding(result, "music")
            return

        if self.has_api_key:
            await self._live_cycle()
        else:
            await self._demo_cycle()

    async def _demo_cycle(self):
        track = random.choice(DEMO_TRACKS)
        await self.broadcast_status(f"vibing to {track['artist']} — {track['track']}")

        if self._cycle_count % 2 == 0:
            discovery = random.choice(DEMO_DISCOVERIES)
            await self.report_finding(discovery, "music")

        if self._cycle_count % 3 == 0:
            agents = ["Claude", "Reddit", "X", "News", "Gemini"]
            target = random.choice(agents)
            user_config = self.config.get("user_name", "Nahom")
            genres = self.config.get("spotify_genres", ["lo-fi", "hip-hop"])
            chat = random.choice(DEMO_CHATS).format(
                agent=target, genre=random.choice(genres), user=user_config
            )
            await self.send_message(target, chat)

    async def _live_cycle(self):
        try:
            import spotipy
            from spotipy.oauth2 import SpotifyClientCredentials

            sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
                client_id=self._client_id,
                client_secret=self._client_secret,
            ))
            # Get new releases
            results = sp.new_releases(limit=5)
            if results and results.get("albums", {}).get("items"):
                album = random.choice(results["albums"]["items"])
                finding = f"New release: {album['name']} by {album['artists'][0]['name']}"
                await self.report_finding(finding, "music")
                await self.broadcast_status(f"checking out {album['name']}")
        except Exception as e:
            logger.error(f"Spotify API error: {e}")
            await self._demo_cycle()
