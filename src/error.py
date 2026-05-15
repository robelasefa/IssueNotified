"""
Centralised error handler for the bot.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log the exception and optionally notify the user."""
    logger.error(
        "Unhandled exception while processing an update.",
        exc_info=context.error,
    )

    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ Something went wrong. Please try again in a moment."
            )
        except Exception:
            pass  # Never raise inside an error handler
