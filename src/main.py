"""
Main entry point for IssueNotified bot.
"""

import logging
import os
from typing import cast

from telegram import (
    Bot,
    BotCommand,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeChat,
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
from config import ADMIN_USER_ID, BOT_TOKEN, DEBUG, DEV_BOT_TOKEN, ISSUE_CHECK_INTERVAL
from error import error_handler
from github import initialize_github_client
from notifier import check_for_new_issues

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def post_init(application: Application) -> None:
    """Initializes the application and sets bot commands."""
    bot = cast(Bot, application.bot)

    # General commands for everyone
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

    # admin-only commands
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


def main():
    """Build and run the bot."""
    logger.info("Starting IssueNotified bot…")

    token = DEV_BOT_TOKEN if DEBUG else BOT_TOKEN
    if not token:
        raise RuntimeError(
            "No bot token configured. Set BOT_TOKEN (or DEV_BOT_TOKEN) in .env."
        )

    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        initialize_github_client(github_token)
        logger.info("GitHub client initialised.")
    else:
        logger.warning("GITHUB_TOKEN not set — GitHub features will be unavailable.")

    application = Application.builder().token(token).post_init(post_init).build()

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

    # Periodic background job to poll GitHub for updates.
    job_queue = application.job_queue
    job_queue.run_repeating(
        check_for_new_issues,
        interval=ISSUE_CHECK_INTERVAL,
        first=30,  # first check 30s after startup
        name="issue_notifier",
    )

    application.run_polling()


if __name__ == "__main__":
    main()
