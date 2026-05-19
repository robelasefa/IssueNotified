"""
FastAPI webhook server for IssueNotified bot.

Replaces the polling-based architecture with webhook endpoints:
- POST /telegram       — receives Telegram bot updates
- POST /github/webhook — receives GitHub issue events
- GET  /health         — health check
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import sys
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import cast

# Dynamic path helper: ensure the current src/ directory is in Python's search path
# so that internal imports like `from callbacks import ...` and `import config` resolve perfectly.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, HTTPException, Request, Response
from telegram import (
    Bot,
    BotCommand,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeChat,
    Update,
)
from telegram.ext import Application, CommandHandler

from callbacks.broadcast import broadcast_conv_handler
from callbacks.feedback import feedback_command
from callbacks.help import help_command
from callbacks.list import list_command
from callbacks.search import search_callback_handler, search_command
from callbacks.start import start
from callbacks.stats import stats_command
from callbacks.stop import stop_callback_handler, stop_command
from callbacks.track import track_conv_handler
from callbacks.untrack import untrack_callback_handler, untrack_conv_handler
from config import (
    ADMIN_USER_ID,
    BOT_TOKEN,
    DEBUG,
    DEV_BOT_TOKEN,
    GITHUB_WEBHOOK_PATH,
    WEBHOOK_BASE_URL,
    WEBHOOK_SECRET,
)
from error import error_handler
from github import initialize_github_client
from notifier import process_github_webhook_event

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Telegram Application builder
# ---------------------------------------------------------------------------


def get_token() -> str:
    """Return the active bot token."""
    token = DEV_BOT_TOKEN if DEBUG else BOT_TOKEN
    if not token:
        raise RuntimeError(
            "No bot token configured. Set BOT_TOKEN (or DEV_BOT_TOKEN) in .env."
        )
    return token


def build_ptb_application(token: str) -> Application:
    """Build a python-telegram-bot Application with all handlers registered.

    The updater is disabled (``updater=None``) because we feed updates
    manually from the FastAPI route handler.
    """
    application = Application.builder().token(token).updater(None).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("feedback", feedback_command))
    application.add_handler(CommandHandler("stats", stats_command))

    # Conversation handlers
    application.add_handler(track_conv_handler)
    application.add_handler(untrack_conv_handler)
    application.add_handler(broadcast_conv_handler)

    # Callback (inline button) handlers
    application.add_handler(stop_callback_handler)
    application.add_handler(untrack_callback_handler)
    application.add_handler(search_callback_handler)

    # Error handler
    application.add_error_handler(error_handler)

    return application


async def set_bot_commands(bot: Bot) -> None:
    """Register bot commands with Telegram."""
    commands = [
        BotCommand("start", "✨ Start"),
        BotCommand("track", "➕ Track a repo"),
        BotCommand("search", "🔍 Search for a repo"),
        BotCommand("untrack", "➖ Untrack a repo"),
        BotCommand("list", "📄 List tracked repos"),
        BotCommand("feedback", "📣 Feedback"),
        BotCommand("stop", "⏹️ Stop the bot"),
        BotCommand("help", "❓ Help"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeAllPrivateChats())

    if ADMIN_USER_ID > 0:
        admin_commands = commands + [
            BotCommand("stats", "📊 System stats"),
            BotCommand("broadcast", "📢 Broadcast message"),
        ]
        try:
            await bot.set_my_commands(
                admin_commands, scope=BotCommandScopeChat(chat_id=ADMIN_USER_ID)
            )
        except Exception as e:
            logger.error(f"Error setting admin commands: {e}")


# ---------------------------------------------------------------------------
# Webhook signature helpers
# ---------------------------------------------------------------------------


def generate_telegram_secret(token: str) -> str:
    """Derive a secret token from the bot token for Telegram webhook verification."""
    return hashlib.sha256(token.encode()).hexdigest()


def verify_github_signature(payload_body: bytes, signature_header: str | None) -> bool:
    """Validate a GitHub webhook payload using HMAC-SHA256."""
    if not signature_header or not WEBHOOK_SECRET:
        return False
    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        payload_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature_header)


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """Manage startup and shutdown of the Telegram bot application."""
    token = get_token()
    ptb_app = build_ptb_application(token)

    # Store references on app state for route handlers
    fastapi_app.state.ptb_app = ptb_app
    fastapi_app.state.telegram_secret = generate_telegram_secret(token)

    # Initialise GitHub client
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        initialize_github_client(github_token)
        logger.info("GitHub client initialised.")
    else:
        logger.warning("GITHUB_TOKEN not set — GitHub features will be unavailable.")

    # Start the PTB application (without polling)
    await ptb_app.initialize()
    await ptb_app.start()

    # Register bot commands
    await set_bot_commands(cast(Bot, ptb_app.bot))

    # Set Telegram webhook
    if WEBHOOK_BASE_URL:
        webhook_url = f"{WEBHOOK_BASE_URL}/telegram"
        await ptb_app.bot.set_webhook(
            url=webhook_url,
            secret_token=fastapi_app.state.telegram_secret,
        )
        logger.info(f"Telegram webhook set: {webhook_url}")
    else:
        logger.warning("WEBHOOK_BASE_URL not set — Telegram webhook not registered.")

    logger.info("IssueNotified webhook server started.")
    yield

    # ----- Shutdown -----
    if WEBHOOK_BASE_URL:
        try:
            await ptb_app.bot.delete_webhook()
            logger.info("Telegram webhook deleted.")
        except Exception as e:
            logger.warning(f"Error deleting Telegram webhook: {e}")

    await ptb_app.stop()
    await ptb_app.shutdown()
    logger.info("IssueNotified webhook server stopped.")


app = FastAPI(title="IssueNotified", lifespan=lifespan)

# ---------------------------------------------------------------------------
# Rate Limiting Middleware
# ---------------------------------------------------------------------------

RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = 60  # max 60 requests per minute
ip_request_history = defaultdict(deque)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Only rate limit webhook endpoints to protect them from spam / DDoS floods
    if request.url.path in ("/telegram", GITHUB_WEBHOOK_PATH):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        history = ip_request_history[client_ip]

        # Remove requests older than the sliding window
        while history and history[0] < now - RATE_LIMIT_WINDOW:
            history.popleft()

        if len(history) >= RATE_LIMIT_MAX_REQUESTS:
            logger.warning(f"Rate limit exceeded for client IP: {client_ip}")
            return Response(
                content=json.dumps({"detail": "Rate limit exceeded. Try again later."}),
                status_code=429,
                media_type="application/json",
            )

        history.append(now)

    return await call_next(request)


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@app.post("/telegram")
async def telegram_webhook(request: Request):
    """Receive Telegram bot updates pushed by the Telegram Bot API."""
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if secret != request.app.state.telegram_secret:
        raise HTTPException(status_code=403, detail="Invalid secret token")

    data = await request.json()
    update = Update.de_json(data, request.app.state.ptb_app.bot)

    try:
        await asyncio.wait_for(
            request.app.state.ptb_app.process_update(update), timeout=20.0
        )
    except asyncio.TimeoutError:
        logger.error("Timeout processing Telegram update")
        return Response(status_code=504)

    return Response(status_code=200)


@app.post(GITHUB_WEBHOOK_PATH)
async def github_webhook(request: Request):
    """Receive GitHub webhook events (issues)."""
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")

    if not verify_github_signature(body, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    event_type = request.headers.get("X-GitHub-Event", "")

    # Respond to GitHub's initial ping
    if event_type == "ping":
        return {"status": "pong"}

    # We only care about issue events
    if event_type != "issues":
        return Response(status_code=200)

    payload = json.loads(body)
    bot = cast(Bot, request.app.state.ptb_app.bot)
    await process_github_webhook_event(payload, bot)
    return Response(status_code=200)


@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "ok", "service": "IssueNotified"}
