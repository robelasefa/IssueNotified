"""
Feedback command callback handler.
"""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def feedback_command(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """Handle /feedback command."""
    feedback_text = (
        "📣 *Feedback & Support*\n\n"
        "Do you have suggestions, bugs to report, or need help? "
        "We'd love to hear from you!\n\n"
        "👤 *Developer:* @robelasefa\n\n"
        "Loved it? ⭐ Star us on [GitHub](https://github.com/robelasefa/IssueNotified)."
    )

    keyboard = [
        [
            InlineKeyboardButton("💬 Message Developer", url="https://t.me/robelasefa"),
            InlineKeyboardButton(
                "🌐 GitHub Repository",
                url="https://github.com/robelasefa/IssueNotified",
            ),
        ]
    ]

    await update.message.reply_text(
        feedback_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )
