"""
Start command callback handler.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from database import db

logger = logging.getLogger(__name__)


async def start(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    user_id = user.id
    welcome_msg = f"""
👋 Hi {user.first_name}! Welcome to *IssueNotified*! 🎉

Never miss a GitHub issue again.

Just type /track and let us take care of the rest.
    """

    # Add user to database if not exists
    try:
        db.add_user(
            user_id=user_id,
            username=user.username,
            first_name=user.first_name,
        )
        logger.info(f"User {user_id} (@{user.username}) started the bot.")
    except Exception as e:
        logger.error(f"Error registering user {user_id}: {e}")

    await update.message.reply_text(welcome_msg, parse_mode="Markdown")
