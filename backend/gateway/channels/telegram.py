from __future__ import annotations

"""
Telegram Channel — Telegram Bot integration for AgentOS.

Users can interact with their agents via Telegram.
Agents can send findings, alerts, and responses through Telegram.
"""

import asyncio
import logging
from typing import Callable, Optional

logger = logging.getLogger("gateway.telegram")


class TelegramChannel:
    """Telegram Bot adapter for the AgentOS Gateway."""

    def __init__(self, bot_token: str, allowed_user_ids: list = None):
        self.bot_token = bot_token
        self.allowed_user_ids = set(allowed_user_ids or [])
        self.active = False
        self._bot = None
        self._app = None
        self._on_message: Optional[Callable] = None
        self._chat_ids: set = set()

    def set_message_handler(self, handler: Callable):
        self._on_message = handler

    async def start(self):
        """Start the Telegram bot."""
        if not self.bot_token:
            logger.info("Telegram: no bot token configured, skipping")
            return

        try:
            from telegram import Update
            from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters

            self._app = ApplicationBuilder().token(self.bot_token).build()

            # Command handlers
            self._app.add_handler(CommandHandler("start", self._cmd_start))
            self._app.add_handler(CommandHandler("status", self._cmd_status))
            self._app.add_handler(CommandHandler("agents", self._cmd_agents))

            # Message handler
            self._app.add_handler(MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self._handle_message,
            ))

            self.active = True
            logger.info("Telegram bot starting...")

            # Run in background
            await self._app.initialize()
            await self._app.start()
            await self._app.updater.start_polling(drop_pending_updates=True)

        except ImportError:
            logger.warning("Telegram: python-telegram-bot not installed")
        except Exception as e:
            logger.error(f"Telegram start error: {e}")

    async def stop(self):
        if self._app:
            try:
                await self._app.updater.stop()
                await self._app.stop()
                await self._app.shutdown()
            except Exception:
                pass
        self.active = False

    def _is_authorized(self, chat_id: int) -> bool:
        """M4: Check if user is authorized. If no whitelist, allow first user."""
        if not self.allowed_user_ids:
            # First user to connect becomes authorized
            self.allowed_user_ids.add(chat_id)
            return True
        return chat_id in self.allowed_user_ids

    async def _cmd_start(self, update, context):
        chat_id = update.effective_chat.id
        if not self._is_authorized(chat_id):
            await update.message.reply_text("Unauthorized. This AgentOS instance is not configured for your account.")
            return
        self._chat_ids.add(chat_id)
        await update.message.reply_text(
            "🧠 AgentOS connected!\n\n"
            "Your agents are running. I'll forward their findings and alerts here.\n\n"
            "Commands:\n"
            "/status — System health\n"
            "/agents — List active agents\n"
            "\nOr just type a message to interact with your agents."
        )

    def _api_url(self, path: str) -> str:
        """H4: Build authenticated local API URL."""
        from backend.auth import API_TOKEN
        return f"http://localhost:8000{path}?token={API_TOKEN}"

    async def _cmd_status(self, update, context):
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("Unauthorized.")
            return
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                r = await client.get(self._api_url("/api/health"), timeout=5)
                h = r.json()
                await update.message.reply_text(
                    f"⚡ AgentOS Status\n"
                    f"━━━━━━━━━━━━━━\n"
                    f"Agents: {h.get('agents', 0)} ({h.get('active', 0)} active)\n"
                    f"Capabilities: {h.get('capabilities', 0)}\n"
                    f"Rules: {h.get('rules', 0)}\n"
                    f"Bus Actions: {h.get('semantic_bus_actions', 0)}\n"
                    f"AI Brain: {h.get('ai_brain', '?')}"
                )
        except Exception as e:
            await update.message.reply_text(f"Error fetching status: {e}")

    async def _cmd_agents(self, update, context):
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("Unauthorized.")
            return
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                r = await client.get(self._api_url("/api/agents"), timeout=5)
                agents = r.json()
                lines = ["🤖 Active Agents:", ""]
                for a in agents:
                    status = a.get('current_task', 'idle')[:40]
                    lines.append(f"{a['emoji']} {a['name']} — {status}")
                await update.message.reply_text("\n".join(lines))
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")

    async def _handle_message(self, update, context):
        """Handle user text messages."""
        if not update.message or not update.message.text:
            return

        chat_id = update.effective_chat.id
        self._chat_ids.add(chat_id)

        # Forward to gateway handler
        if self._on_message:
            from backend.gateway.gateway import GatewayMessage
            msg = GatewayMessage(
                text=update.message.text,
                channel="telegram",
                user_id=str(chat_id),
            )
            try:
                response = await self._on_message(msg)
                if response:
                    await update.message.reply_text(response)
            except Exception as e:
                await update.message.reply_text(f"Processing error: {e}")
        else:
            await update.message.reply_text(
                "Message received! Your agents are processing it. "
                "Check /status for the latest."
            )

    async def send_message(self, text: str, user_id: str = ""):
        """Send a message to Telegram (to a specific user or all known chats)."""
        if not self._app or not self._app.bot:
            return

        targets = {int(user_id)} if user_id else self._chat_ids

        for chat_id in targets:
            try:
                await self._app.bot.send_message(
                    chat_id=chat_id,
                    text=text[:4096],  # Telegram message limit
                )
            except Exception as e:
                logger.error(f"Telegram send error to {chat_id}: {e}")
