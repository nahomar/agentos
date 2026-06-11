from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class WeatherData:
    temperature_f: float = 72.0
    feels_like_f: float = 72.0
    humidity: int = 50
    condition: str = "clear"  # clear, cloudy, rain, snow, etc.
    description: str = ""
    wind_mph: float = 5.0
    city: str = ""


@dataclass
class Location:
    lat: float = 0.0
    lon: float = 0.0
    city: str = ""
    region: str = ""
    country: str = ""
    location_type: str = "unknown"  # home, work, commuting, other


@dataclass
class CalendarEvent:
    title: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    location: str = ""
    has_documents: bool = False


@dataclass
class UserContext:
    # Temporal
    timestamp: float = 0.0
    time_of_day: str = "morning"  # early_morning, morning, midday, afternoon, evening, night, late_night
    hour: int = 0
    day_of_week: str = "monday"
    is_weekend: bool = False
    is_golden_hour: bool = False

    # Location
    location: Optional[Location] = None

    # Environmental
    weather: Optional[WeatherData] = None

    # Device
    current_app: str = ""
    app_duration_minutes: int = 0
    screen_on: bool = True
    battery_level: int = 100

    # Activity
    activity_level: str = "sedentary"  # sedentary, walking, exercising
    steps_today: int = 0
    sedentary_minutes: int = 0

    # Communication
    unread_messages: int = 0
    missed_calls: int = 0
    pending_replies: list = field(default_factory=list)

    # Behavioral (inferred)
    inferred_mood: str = "neutral"  # focused, relaxed, stressed, social, neutral
    focus_score: float = 0.5
    engagement_level: str = "active"  # active, passive, idle

    # Calendar
    next_event: Optional[CalendarEvent] = None
    minutes_until_next_event: int = 999

    def to_dict(self) -> dict:
        d = {}
        for k, v in self.__dict__.items():
            if v is None:
                d[k] = {}
            elif hasattr(v, '__dict__'):
                d[k] = v.__dict__
            elif isinstance(v, list):
                d[k] = v
            else:
                d[k] = v
        return d
