from __future__ import annotations

import yaml
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    ssl_certfile: str = ""
    ssl_keyfile: str = ""


@dataclass
class ApiKeys:
    anthropic: str = ""
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_username: str = ""
    x_bearer_token: str = ""
    newsapi: str = ""
    gemini: str = ""
    google_maps: str = ""
    telegram_bot_token: str = ""


@dataclass
class UserConfig:
    name: str = "User"
    interests: list[str] = field(default_factory=list)
    subreddits: list[str] = field(default_factory=list)
    x_accounts: list[str] = field(default_factory=list)
    spotify_genres: list[str] = field(default_factory=list)


@dataclass
class AgentSettings:
    cycle_interval: int = 30
    chat_interval: int = 45
    briefing_interval: int = 300
    max_history: int = 200


@dataclass
class Config:
    server: ServerConfig = field(default_factory=ServerConfig)
    api_keys: ApiKeys = field(default_factory=ApiKeys)
    user: UserConfig = field(default_factory=UserConfig)
    agents: AgentSettings = field(default_factory=AgentSettings)


def load_config() -> Config:
    config_path = Path(__file__).parent.parent / "config.yaml"
    if not config_path.exists():
        return Config()

    with open(config_path) as f:
        raw = yaml.safe_load(f) or {}

    cfg = Config()
    if "server" in raw:
        cfg.server = ServerConfig(**raw["server"])
    if "api_keys" in raw:
        cfg.api_keys = ApiKeys(**raw["api_keys"])

    # H8: Environment variable overrides for secrets
    import os
    env_map = {
        "ANTHROPIC_API_KEY": "anthropic",
        "GEMINI_API_KEY": "gemini",
        "SPOTIFY_CLIENT_ID": "spotify_client_id",
        "SPOTIFY_CLIENT_SECRET": "spotify_client_secret",
        "TELEGRAM_BOT_TOKEN": "telegram_bot_token",
        "NEWSAPI_KEY": "newsapi",
        "X_BEARER_TOKEN": "x_bearer_token",
    }
    for env_var, field_name in env_map.items():
        val = os.environ.get(env_var, "")
        if val:
            setattr(cfg.api_keys, field_name, val)
    if "user" in raw:
        u = raw["user"]
        cfg.user = UserConfig(
            name=u.get("name", "User"),
            interests=u.get("interests", []),
            subreddits=u.get("subreddits", []),
            x_accounts=u.get("x_accounts", []),
            spotify_genres=u.get("spotify_genres", []),
        )
    if "agents" in raw:
        cfg.agents = AgentSettings(**raw["agents"])
    return cfg
