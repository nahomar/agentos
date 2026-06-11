from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.auth import AuthMiddleware, verify_ws_token, API_TOKEN
from backend.rate_limit import RateLimitMiddleware
from backend.config import load_config
from backend.orchestrator import Orchestrator
from backend.context.engine import ContextEngine
from backend.proactive.evaluator import RulesEvaluator
from backend.capabilities.registry import CapabilityRegistry
from backend.capabilities.providers.communication import (
    TwilioCallProvider, TwilioSMSProvider, EmailProvider, PushNotificationProvider,
)
from backend.capabilities.providers.information import (
    WeatherProvider, LocationProvider, TimeProvider,
)
from backend.capabilities.providers.media import SpotifyPlayProvider, CameraTriggerProvider
from backend.capabilities.providers.ai import ClaudeAIProvider, GeminiAIProvider
from backend.capabilities.providers.content import WebBrowseProvider, WebSearchProvider
from backend.capabilities.providers.device import NotificationProvider, ShortcutTriggerProvider
from backend.notifications.processor import NotificationProcessor
from backend import database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("server")

config = load_config()
orchestrator = Orchestrator(config)

# Build config dict for capabilities
cap_config = {
    "anthropic": config.api_keys.anthropic,
    "gemini": config.api_keys.gemini,
    "spotify_client_id": config.api_keys.spotify_client_id,
    "spotify_client_secret": config.api_keys.spotify_client_secret,
    "openweathermap_key": getattr(config.api_keys, 'openweathermap', '') or config.api_keys.newsapi,
}

# Initialize subsystems
context_engine = ContextEngine(orchestrator.memory, cap_config)
capabilities = CapabilityRegistry(orchestrator.bus, cap_config)
rules_evaluator = RulesEvaluator(orchestrator.bus, cap_config)
notif_processor = NotificationProcessor(orchestrator.bus, cap_config)

# Register all capability providers
for provider_class in [
    TwilioCallProvider, TwilioSMSProvider, EmailProvider, PushNotificationProvider,
    WeatherProvider, LocationProvider, TimeProvider,
    SpotifyPlayProvider, CameraTriggerProvider,
    ClaudeAIProvider, GeminiAIProvider,
    WebBrowseProvider, WebSearchProvider,
    NotificationProvider, ShortcutTriggerProvider,
]:
    capabilities.register(provider_class(cap_config))

# OS-level systems
from backend.semantic_bus.bus import SemanticBus
from backend.semantic_bus.builtin_apps import get_builtin_apps
from backend.execution.speculative import (
    SpeculativeEngine, time_based_predictor, context_based_predictor,
)
from backend.verification.layer import VerificationLayer
from backend.identity.vault import IdentityVault

from backend.semantic_bus.handlers import get_builtin_handlers

semantic_bus = SemanticBus()
_action_handlers = get_builtin_handlers(cap_config)
for app_manifest in get_builtin_apps():
    semantic_bus.register_app(app_manifest, _action_handlers)

speculative_engine = SpeculativeEngine()
speculative_engine.add_predictor(time_based_predictor)
speculative_engine.add_predictor(context_based_predictor)

verification_layer = VerificationLayer(cap_config)
identity_vault = IdentityVault()

# Kernel subsystems
from backend.kernel.ipc import IPCBroker
from backend.kernel.scheduler import AgentScheduler
from backend.kernel.governor import ResourceGovernor
from backend.kernel.watchdog import Watchdog
from backend.kernel.audit import AuditLog
from backend.kernel.checkpoint import CheckpointManager
from backend.kernel.namespace import AgentNamespace, register_default_namespace
from backend.kernel.mcp import MCPServer
from backend.gateway.gateway import Gateway
from backend.gateway.channels.telegram import TelegramChannel

ipc_broker = IPCBroker()
scheduler = AgentScheduler()
governor = ResourceGovernor()
watchdog = Watchdog()
audit_log = AuditLog()
checkpoint_mgr = CheckpointManager()
namespace = AgentNamespace()

from backend.kernel.process import ProcessManager
process_mgr = ProcessManager()
mcp_server = MCPServer(semantic_bus)

# Gateway with channels
gateway = Gateway()
telegram_channel = TelegramChannel(
    bot_token=config.api_keys.telegram_bot_token,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AgentOS Kernel...")
    database.init_db()

    # H2: Wire IPCBroker as the real message bus backend
    orchestrator.bus.set_ipc_broker(ipc_broker)

    # M3: Wire watchdog heartbeats from ProcessManager
    process_mgr.set_heartbeat_callback(watchdog.heartbeat)
    # N3: Wire resource governor
    process_mgr.set_governor(governor)

    # Wire kernel subsystems to every agent
    for name, agent in orchestrator.agents.items():
        agent.semantic_bus = semantic_bus
        agent.audit_log = audit_log
        agent.checkpoint_mgr = checkpoint_mgr

        # Register with kernel services
        watchdog.register(name)
        process_mgr.register(name, agent)

        # Restore checkpoint if exists
        try:
            await agent.restore_state()
        except Exception:
            pass

    # Register namespace handlers
    register_default_namespace(
        namespace, orchestrator, scheduler, governor, watchdog,
        audit_log, checkpoint_mgr, context_engine, semantic_bus,
        verification_layer, identity_vault, ipc_broker,
    )

    # Wire proactive rules to real capability execution (verified, then bus)
    rules_evaluator.set_action_executor(semantic_bus, verification_layer)
    # Wire speculative engine so high-confidence predictions actually pre-warm
    speculative_engine.set_executor(semantic_bus.execute)

    # Start all subsystems
    await process_mgr.start_all(orchestrator.config.agents.cycle_interval)
    asyncio.create_task(context_engine.start(interval=30))
    asyncio.create_task(rules_evaluator.start(
        context_getter=context_engine.get_context,
        interval=30,
    ))
    asyncio.create_task(speculative_engine.start(
        context_getter=context_engine.get_context,
        interval=10,
    ))
    asyncio.create_task(watchdog.start())

    # Start Telegram gateway if configured
    if config.api_keys.telegram_bot_token:
        gateway.register_channel("telegram", telegram_channel)
        asyncio.create_task(telegram_channel.start())

    # Start orchestrator conversation/briefing loops (not agent cycles — ProcessManager handles those)
    orchestrator._running = True
    orchestrator._tasks.append(asyncio.create_task(orchestrator._conversation_loop()))
    orchestrator._tasks.append(asyncio.create_task(orchestrator._briefing_loop()))

    logger.info(f"AgentOS Kernel booted — {len(orchestrator.agents)} agents, "
                f"{len(namespace.list_paths())} namespace paths, "
                f"{len(semantic_bus.get_available_actions())} bus actions")
    # C1: Never log the token — tell user where to find it
    logger.info("API token stored in: data/api_token")

    from backend.platform.detect import get_platform
    _plat = get_platform()
    logger.info(f"Access: http://{_plat.get_local_ip()}:8000")

    yield

    # Checkpoint all agents before shutdown
    for name, agent in orchestrator.agents.items():
        try:
            await agent.checkpoint()
        except Exception:
            pass

    await process_mgr.stop_all()
    orchestrator._running = False
    for t in orchestrator._tasks:
        t.cancel()
    await context_engine.stop()
    await rules_evaluator.stop()
    await speculative_engine.stop()
    await watchdog.stop()
    audit_log._flush()
    logger.info("AgentOS Kernel shut down")


app = FastAPI(title="AgentOS", lifespan=lifespan)

# H9: Rate limiting
app.add_middleware(RateLimitMiddleware)

# C2: Authentication
app.add_middleware(AuthMiddleware)

# CORS — restrict to same origin + local network (M2 fix)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    # H2: Anchored regex, valid octets only
    allow_origin_regex=r"^http://192\.168\.\d{1,3}\.\d{1,3}:\d{1,5}$",
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    allow_credentials=True,
)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


@app.get("/")
async def root():
    return FileResponse(FRONTEND_DIR / "index.html")


# Static files
for subdir in ["css", "js", "assets"]:
    static_dir = FRONTEND_DIR / subdir
    if static_dir.exists():
        app.mount(f"/{subdir}", StaticFiles(directory=static_dir), name=subdir)


# === WebSocket (bidirectional) ===

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    # C3: WebSocket authentication
    if not await verify_ws_token(ws):
        await ws.accept()
        await ws.send_text(json.dumps({"error": "Unauthorized — connect with ?token=<api_token>"}))
        await ws.close(code=4001)
        return
    await ws.accept()
    orchestrator.bus.register_ws(ws)
    logger.info("WebSocket client connected (authenticated)")
    try:
        while True:
            raw = await ws.receive_text()
            # H1: Message size limit (1MB max)
            if len(raw) > 1_048_576:
                await ws.send_text('{"error":"Message too large (1MB max)"}')
                continue
            try:
                data = json.loads(raw)
                await _handle_ws_message(data)
            except json.JSONDecodeError:
                # L2: Don't log raw message content (could fill disk)
                logger.warning("Invalid JSON from WebSocket client")
    except WebSocketDisconnect:
        orchestrator.bus.unregister_ws(ws)
        logger.info("WebSocket client disconnected")


async def _on_context_change():
    """Refresh derived context and evaluate rules now, instead of waiting
    up to 30s for the next timer tick. Weather/location sources cache, so
    this is cheap."""
    try:
        await context_engine.update()
        rules_evaluator.poke()
    except Exception as e:
        logger.error(f"Context-triggered evaluation error: {e}")


async def _handle_ws_message(data: dict):
    msg_type = data.get("type", "")

    if msg_type == "context_update":
        ctx_data = data.get("data", {})
        # H5: Only allow known context fields
        ALLOWED_CTX = {"current_app", "battery_level", "lat", "lon", "screen_on",
                       "charging", "step_count", "active_app", "wifi_connected",
                       "sedentary_minutes", "unread_messages", "missed_calls"}
        safe_data = {k: v for k, v in ctx_data.items() if k in ALLOWED_CTX}
        await orchestrator.memory.update_user_context(**safe_data)
        asyncio.create_task(_on_context_change())

    elif msg_type == "permission_response":
        request_id = data.get("request_id", "")
        granted = data.get("granted", False)
        capabilities.resolve_permission(request_id, granted)

    elif msg_type == "user_command":
        text = data.get("text", "")
        logger.info(f"User command: {text}")

    elif msg_type == "trigger_agent":
        agent_name = data.get("agent", "")
        await orchestrator.trigger_agent(agent_name)


# === REST API ===

@app.get("/api/health")
async def health():
    return {
        "status": "running",
        "agents": len(orchestrator.agents),
        "active": sum(1 for a in orchestrator.agents.values() if a.status != "offline"),
        "capabilities": len(capabilities.list_capabilities()),
        "rules": len(rules_evaluator.get_rules_info()),
        "semantic_bus_actions": len(semantic_bus.get_available_actions()),
        "semantic_bus_apps": len(semantic_bus.get_app_info()),
        "verification_rules": verification_layer.get_stats()["rules_count"],
        "identity_credentials": identity_vault.get_stats()["stored_credentials"],
        "ai_brain": "active" if orchestrator.brain.has_any_ai else "demo_mode",
    }


@app.get("/api/agents")
async def get_agents():
    return orchestrator.get_agents_info()


@app.get("/api/feed")
async def get_feed(limit: int = 50):
    return orchestrator.get_feed(limit=min(limit, 500))  # M8: bound limit


# H5: Notification ingest endpoint for Android
class NotificationIngest(BaseModel):
    app: str = ""
    title: str = ""
    text: str = ""
    timestamp: float = 0
    key: str = ""

    class Config:
        # H6: Input length limits
        str_max_length = 2000


@app.post("/api/notifications/ingest")
async def ingest_notification(notif: NotificationIngest):
    result = await notif_processor.process(notif.app, notif.title, notif.text)
    return {"priority": result.priority.value, "summary": result.summary}


@app.get("/api/plugins")
async def get_plugins():
    return orchestrator.get_plugins_info()


@app.post("/api/agents/{agent_id}/enable")
async def enable_agent(agent_id: str):
    ok = await orchestrator.enable_agent(agent_id)
    return {"success": ok}


@app.post("/api/agents/{agent_id}/disable")
async def disable_agent(agent_id: str):
    ok = await orchestrator.disable_agent(agent_id)
    return {"success": ok}


@app.post("/api/agents/{agent_name}/trigger")
async def trigger_agent(agent_name: str):
    ok = await orchestrator.trigger_agent(agent_name)
    return {"success": ok}


class ContextUpdate(BaseModel):
    current_app: Optional[str] = None
    last_activity: Optional[str] = None
    active_tasks: Optional[List[str]] = None
    battery_level: Optional[int] = None
    lat: Optional[float] = None
    lon: Optional[float] = None


@app.post("/api/context")
async def update_context(ctx: ContextUpdate):
    update = {k: v for k, v in ctx.model_dump().items() if v is not None}
    await orchestrator.memory.update_user_context(**update)
    asyncio.create_task(_on_context_change())
    return {"status": "ok"}


@app.get("/api/context")
async def get_context():
    return context_engine.get_context_dict()


@app.get("/api/capabilities")
async def get_capabilities():
    return capabilities.list_capabilities()


@app.get("/api/rules")
async def get_rules():
    return rules_evaluator.get_rules_info()


@app.get("/api/permissions")
async def get_permissions():
    return capabilities.permissions.get_all_grants()


# === Kernel Namespace (Virtual Filesystem) ===

@app.get("/ns/{path:path}")
async def namespace_resolve(path: str):
    """Resolve any namespace path — the Plan 9-inspired virtual filesystem."""
    return await namespace.resolve(f"/{path}")


@app.get("/api/kernel/status")
async def kernel_status():
    """Full kernel status — like `uname -a` for AgentOS."""
    return {
        "version": "0.1.0",
        "codename": "genesis",
        "uptime_note": "kernel status snapshot",
        "scheduler": scheduler.get_stats(),
        "governor": {"agents_tracked": len(governor.get_all_usage())},
        "watchdog": watchdog.get_stats(),
        "audit": audit_log.get_stats(),
        "checkpoints": checkpoint_mgr.get_stats(),
        "ipc": ipc_broker.get_stats(),
        "namespace_paths": len(namespace.list_paths()),
        "semantic_bus": semantic_bus.get_execution_stats(),
        "verification": verification_layer.get_stats(),
        "identity": identity_vault.get_stats(),
    }


@app.get("/api/kernel/namespace")
async def list_namespace():
    """List all mounted namespace paths."""
    return namespace.list_paths()


@app.get("/api/kernel/processes")
async def get_processes():
    """Process table — like `ps aux` for agents."""
    return process_mgr.get_process_table()


@app.get("/api/kernel/audit")
async def get_audit(limit: int = 50, agent: str = ""):
    return audit_log.query(agent_id=agent or None, limit=min(limit, 500))


@app.get("/api/kernel/watchdog")
async def get_watchdog():
    return watchdog.get_health()


# === MCP Protocol ===

@app.websocket("/mcp")
async def mcp_endpoint(ws: WebSocket):
    """MCP JSON-RPC 2.0 over WebSocket."""
    if not await verify_ws_token(ws):
        await ws.accept()
        await ws.send_text('{"error":"Unauthorized"}')
        await ws.close(code=4001)
        return
    await ws.accept()
    logger.info("MCP client connected (authenticated)")
    try:
        while True:
            raw = await ws.receive_text()
            response = await mcp_server.handle_request(raw)
            await ws.send_text(response)
    except WebSocketDisconnect:
        logger.info("MCP client disconnected")


@app.post("/mcp")
async def mcp_http(request: dict):
    """MCP JSON-RPC 2.0 over HTTP."""
    import json as json_mod
    response = await mcp_server.handle_request(json_mod.dumps(request))
    return json_mod.loads(response)


# === Gateway ===

@app.get("/api/gateway/channels")
async def get_gateway_channels():
    return gateway.get_channels()


# === Semantic Bus ===

@app.get("/api/semantic-bus/actions")
async def get_actions(tags: str = ""):
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    actions = semantic_bus.get_available_actions(tag_list)
    return [a.to_dict() for a in actions]


@app.get("/api/semantic-bus/apps")
async def get_registered_apps():
    return semantic_bus.get_app_info()


@app.get("/api/semantic-bus/stats")
async def get_bus_stats():
    return semantic_bus.get_execution_stats()


@app.get("/api/semantic-bus/context")
async def get_actions_context(tags: str = ""):
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    return {"context": semantic_bus.get_actions_context(tag_list)}


# === Speculative Execution ===

@app.get("/api/speculative/predictions")
async def get_predictions():
    return {
        "predictions": speculative_engine.get_predictions(),
        "stats": speculative_engine.get_stats(),
    }


# === Verification ===

@app.get("/api/verification/stats")
async def get_verification_stats():
    return verification_layer.get_stats()


@app.get("/api/verification/blocked")
async def get_blocked_actions():
    return verification_layer.get_blocked_log()


# === Identity Vault ===

@app.get("/api/identity/services")
async def get_identity_services():
    return identity_vault.list_services()


@app.get("/api/identity/stats")
async def get_identity_stats():
    return identity_vault.get_stats()


@app.get("/api/patterns")
async def get_patterns():
    return {
        "habits": context_engine.patterns.get_habits(),
        "predictions": context_engine.patterns.predict(context_engine.get_context_dict()),
        "stats": context_engine.patterns.get_stats(),
    }


@app.get("/api/findings")
async def get_findings(limit: int = 20, agent: str = ""):
    from backend.database import get_findings
    return get_findings(limit=min(limit, 500), agent=agent or None)


# === Agent Creator ===

class AgentCreateRequest(BaseModel):
    description: str

    class Config:
        str_max_length = 1000  # H6: limit description length


@app.post("/api/agents/create")
async def create_agent(req: AgentCreateRequest):
    from backend.agent_creator import create_agent_from_description
    result = await create_agent_from_description(req.description, orchestrator.brain)
    return result


# === Spotify OAuth ===

_spotify_auth = None

def _get_spotify_auth():
    global _spotify_auth
    if _spotify_auth is None:
        from backend.spotify_auth import SpotifyAuth
        _spotify_auth = SpotifyAuth(
            client_id=config.api_keys.spotify_client_id,
            client_secret=config.api_keys.spotify_client_secret,
        )
    return _spotify_auth


@app.get("/api/spotify/auth-url")
async def spotify_auth_url():
    auth = _get_spotify_auth()
    if not auth.client_id:
        return {"error": "Spotify client_id not configured in config.yaml"}
    return {"url": auth.get_auth_url()}


@app.get("/api/spotify/callback")
async def spotify_callback(code: str = ""):
    if not code:
        return {"error": "No authorization code"}
    auth = _get_spotify_auth()
    success = await auth.exchange_code(code)
    if success:
        return FileResponse(FRONTEND_DIR / "index.html")
    return {"error": "Failed to authenticate with Spotify"}


@app.get("/api/spotify/status")
async def spotify_status():
    auth = _get_spotify_auth()
    if not auth.is_authenticated:
        return {"authenticated": False}
    playback = await auth.get_current_playback()
    return {"authenticated": True, "playback": playback}


@app.get("/api/spotify/search")
async def spotify_search(q: str = ""):
    auth = _get_spotify_auth()
    results = await auth.search(q)
    return {"results": results}


@app.post("/api/spotify/play")
async def spotify_play(uri: str = ""):
    auth = _get_spotify_auth()
    ok = await auth.play(uri=uri if uri else None)
    return {"success": ok}


# PWA manifest
@app.get("/manifest.json")
async def pwa_manifest():
    manifest_path = FRONTEND_DIR / "manifest.json"
    if manifest_path.exists():
        return FileResponse(manifest_path)
    return {"name": "AgentOS", "short_name": "AgentOS"}


@app.get("/sw.js")
async def service_worker():
    sw_path = FRONTEND_DIR / "sw.js"
    if sw_path.exists():
        return FileResponse(sw_path, media_type="application/javascript")
    return ""
