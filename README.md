# AgentOS — Your Phone's AI Brain

> **12 autonomous AI agents** that manage your digital life from a stunning live wallpaper. Research, music, news, photos, fitness, contacts — all running autonomously while you live your life.

```
⚡ 12 agents  |  15 capabilities  |  10 proactive rules  |  Zero config needed
```

---

## What It Does

Your phone becomes an intelligent system where AI agents **autonomously**:

- **Continue your research** on Claude and Gemini when you walk away
- **Play music** matching your mood, weather, and location
- **Take photos** when the light is beautiful (golden hour detection)
- **Remind you to call** people you haven't talked to in a while
- **Summarize notifications** and filter noise from signal
- **Track your wellness** — hydration, movement, posture reminders
- **Prep meeting briefings** from your calendar
- **Find content** on Reddit, X, and news matching your interests
- **Talk to each other** — agents collaborate and share findings

All visible on a **stunning animated wallpaper** with floating agent avatars, glowing connections, and real-time speech bubbles.

---

## Quick Start (30 seconds)

```bash
git clone https://github.com/nahommohan/agentos.git
cd agentos
./start.sh
```

Open on your iPhone (same WiFi):
```
http://<your-local-ip>:8000
```

Add to Home Screen for the full-screen experience.

**No API keys needed** — all agents run in demo mode out of the box.

---

## Architecture

```
┌──────────────────┐
│  iPhone (PWA)    │  Animated wallpaper with floating agents
│  Wallpaper UI    │  Speech bubbles, connection lines, feed
└────────┬─────────┘
         │ WebSocket + REST
┌────────┴──────────────────────┐
│        FastAPI Server         │
├──────┬──────────┬─────────────┤
│Plugin│ Context  │  Proactive  │  Dynamic agent loading
│Loader│ Engine   │  Rules      │  Weather/location/mood aware
├──────┴──────────┴─────────────┤  10 intelligent rules
│     Capability Registry       │
│ (Twilio, Spotify, Weather,   │  15 typed capabilities
│  Claude, Camera, Calendar)   │  Permission system
├───────────────────────────────┤
│  12 Autonomous Agents         │
├───────────────────────────────┤
│  Message Bus + SQLite Memory  │  Persistent across restarts
└───────────────────────────────┘
```

---

## Built-in Agents

| Agent | App | What It Does |
|-------|-----|-------------|
| 🧠 Claude | Claude | Continues research, synthesizes findings |
| 🔬 Gemini | Gemini | Cross-references data, analytical insights |
| 🎵 Spotify | Spotify | Discovers music, mood-based playlists |
| 🔥 Reddit | Reddit | Monitors subreddits, surfaces trending posts |
| 🐦 X | X/Twitter | Tracks trends, curates tweets |
| 📰 News | News | Aggregates headlines, fact-checks |
| ⛅ Weather | Weather | Monitors conditions, outdoor suggestions |
| 📸 Photos | Camera | Detects photo opportunities, golden hour |
| 👥 Contacts | Contacts | Communication reminders, social patterns |
| 📅 Calendar | Calendar | Meeting prep, schedule awareness |
| 💪 Fitness | Health | Movement reminders, wellness tracking |
| ⏰ Reminder | Reminders | Productivity nudges, daily check-ins |

---

## Create Your Own Agent (No Code)

Drop a `manifest.yaml` in `agents/custom/my-agent/`:

```yaml
agent:
  id: "water-reminder"
  name: "Water"
  emoji: "💧"
  color: "#3498DB"
  personality: "hydration enthusiast"

  triggers:
    - type: "interval"
      seconds: 120

  actions:
    - type: "notify"
      template: "Time to drink water! Stay hydrated 💧"
```

Restart the server — your agent appears on the wallpaper automatically.

For agents with custom logic, add an `agent.py` with a class inheriting `BaseAgent`.

---

## Proactive Intelligence

AgentOS doesn't just respond — it **anticipates**. Built-in rules include:

| Rule | What Happens |
|------|-------------|
| Morning Briefing | Summarizes overnight agent activity |
| Focus Mode | Detects deep work, silences noise |
| Golden Hour | Alerts for perfect photo lighting |
| Movement Reminder | Nudges after 2+ hours sitting |
| Weather Walk | Suggests walks in nice weather |
| Hydration Check | Periodic water reminders |
| Late Night Wind-down | Encourages rest after 10 PM |
| Meeting Prep | Preps briefings before meetings |

Create custom rules in `backend/proactive/builtin_rules.yaml`.

---

## Capabilities

Agents request typed capabilities with a permission system:

| Capability | Provider | Permission |
|-----------|----------|-----------|
| `communication.call` | Twilio | Always ask |
| `communication.sms` | Twilio | Always ask |
| `communication.email` | SMTP | Ask once |
| `media.play_music` | Spotify API | Ask once |
| `media.take_photo` | iOS Shortcut | Ask once |
| `info.weather` | OpenWeatherMap | Auto |
| `info.location` | IP / CoreLocation | Auto |
| `ai.claude` | Anthropic API | Auto |
| `ai.gemini` | Google AI | Auto |
| `content.web_search` | SerpAPI | Auto |

Add API keys in `config.yaml` to enable live capabilities.

---

## API

```
GET  /api/health         # System status
GET  /api/agents         # All agents and status
GET  /api/plugins        # Discovered plugins
GET  /api/feed           # Activity feed
GET  /api/context        # Current user context
GET  /api/capabilities   # Available capabilities
GET  /api/rules          # Proactive rules
POST /api/context        # Update user context
POST /api/agents/{id}/trigger  # Manually trigger agent
WS   /ws                 # Real-time bidirectional
```

---

## Configuration

Edit `config.yaml`:

```yaml
user:
  name: "Your Name"
  interests: ["AI", "startups", "music"]
  subreddits: ["programming", "MachineLearning"]

api_keys:
  anthropic: "sk-..."     # Optional - enables live Claude
  spotify_client_id: ""   # Optional - enables live Spotify
```

---

## Docker

```bash
cd docker && docker-compose up
```

---

## Tech Stack

- **Backend**: Python 3.9+, FastAPI, asyncio, WebSocket
- **Frontend**: Vanilla JS, CSS animations, Canvas particles
- **Storage**: SQLite (zero-dependency persistence)
- **AI**: Claude API, Gemini API (optional)
- **Communication**: Twilio (optional)
- **No external dependencies for demo mode**

---

## Privacy

- All data stays on your machine
- No telemetry, no cloud sync, no tracking
- API keys never leave your system
- SQLite database stored locally in `data/`
- Works fully offline in demo mode

---

## Roadmap

- [ ] Native iOS app (CoreLocation, HealthKit, Camera, Siri)
- [ ] Agent marketplace with community plugins
- [ ] Pattern learning (predicts what you need)
- [ ] Auto-respond to messages (with approval)
- [ ] Natural language agent creation ("make an agent that...")
- [ ] Local LLM support (Ollama/MLX)
- [ ] Android companion app

---

## License

MIT — build whatever you want with it.
