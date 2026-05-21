import asyncio
import hashlib
import logging
import os
import sys
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import cast

# src/ is the package root; insert it so internal imports resolve without a package prefix.
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

from ai import ai_client, initialize_ai_client
from callbacks.broadcast import broadcast_conv_handler
from callbacks.feedback import feedback_command
from callbacks.help import help_command
from callbacks.list import list_command
from callbacks.search import search_callback_handler, search_command
from callbacks.start import start
from callbacks.stats import stats_command
from callbacks.stop import stop_callback_handler, stop_command
from callbacks.track import track_conv_handler
from callbacks.untrack import untrack_callback_handler, untrack_command
from config import (
    ADMIN_USER_ID,
    BOT_TOKEN,
    DEBUG,
    DEV_BOT_TOKEN,
    WEBHOOK_BASE_URL,
    WEBHOOK_SECRET,
)
from error import error_handler
from github import initialize_github_client
from poller import poll_repositories

logger = logging.getLogger(__name__)

_RATE_LIMIT_WINDOW = 60
_RATE_LIMIT_MAX_REQUESTS = 60
_ip_request_history: dict[str, deque] = defaultdict(deque)


def _get_token() -> str:
    token = DEV_BOT_TOKEN if DEBUG else BOT_TOKEN
    if not token:
        raise RuntimeError(
            "No bot token configured. Set BOT_TOKEN (or DEV_BOT_TOKEN) in .env."
        )
    return token


def _build_ptb_app(token: str) -> Application:
    """PTB Application wired to FastAP."""
    app = Application.builder().token(token).updater(None).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("untrack", untrack_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("feedback", feedback_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats_command))

    app.add_handler(track_conv_handler)
    app.add_handler(broadcast_conv_handler)

    app.add_handler(untrack_callback_handler)
    app.add_handler(stop_callback_handler)
    app.add_handler(search_callback_handler)

    app.add_error_handler(error_handler)

    if app.job_queue:
        app.job_queue.run_repeating(poll_repositories, interval=300, first=10)

    return app


async def _set_bot_commands(bot: Bot) -> None:
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
            logger.error("Error setting admin commands: %s", e)


def _generate_telegram_secret(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    token = _get_token()
    ptb_app = _build_ptb_app(token)

    fastapi_app.state.ptb_app = ptb_app
    fastapi_app.state.telegram_secret = _generate_telegram_secret(token)

    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        initialize_github_client(github_token)
        logger.info("GitHub client initialised.")
    else:
        logger.warning("GITHUB_TOKEN not set — GitHub features unavailable.")

    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        initialize_ai_client(gemini_key)
        await ai_client.start()
        logger.info("Gemini AI client initialised.")
    else:
        logger.warning("GEMINI_API_KEY not set — AI features disabled.")

    await ptb_app.initialize()
    await ptb_app.start()
    await _set_bot_commands(cast(Bot, ptb_app.bot))

    if WEBHOOK_BASE_URL:
        webhook_url = f"{WEBHOOK_BASE_URL}/telegram"
        await ptb_app.bot.set_webhook(
            url=webhook_url, secret_token=fastapi_app.state.telegram_secret
        )
        logger.info("Telegram webhook set: %s", webhook_url)
    else:
        logger.warning("WEBHOOK_BASE_URL not set — Telegram webhook not registered.")

    logger.info("IssueNotified started.")
    yield

    if WEBHOOK_BASE_URL:
        try:
            await ptb_app.bot.delete_webhook()
        except Exception as e:
            logger.warning("Error deleting Telegram webhook: %s", e)

    await ptb_app.stop()
    await ptb_app.shutdown()
    await ai_client.stop()
    logger.info("IssueNotified stopped.")


app = FastAPI(title="IssueNotified", lifespan=lifespan)


@app.middleware("http")
async def _rate_limit(request: Request, call_next):
    if request.url.path == "/telegram":
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        history = _ip_request_history[ip]
        while history and history[0] < now - _RATE_LIMIT_WINDOW:
            history.popleft()
        if len(history) >= _RATE_LIMIT_MAX_REQUESTS:
            logger.warning("Rate limit exceeded for IP: %s", ip)
            return Response(status_code=429, content="Rate limit exceeded.")
        history.append(now)
    return await call_next(request)


@app.post("/telegram")
async def telegram_webhook(request: Request):
    if (
        request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        != request.app.state.telegram_secret
    ):
        raise HTTPException(status_code=403, detail="Invalid secret token")

    data = await request.json()
    update = Update.de_json(data, request.app.state.ptb_app.bot)
    try:
        await asyncio.wait_for(
            request.app.state.ptb_app.process_update(update), timeout=20.0
        )
    except asyncio.TimeoutError:
        logger.error("Timeout processing Telegram update %s", data.get("update_id"))
        return Response(status_code=504)
    return Response(status_code=200)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "IssueNotified"}
