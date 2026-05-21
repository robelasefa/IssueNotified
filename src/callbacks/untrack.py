import logging
from typing import Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, ContextTypes

from database import db

logger = logging.getLogger(__name__)

_CB_PREFIX = "untrack|"


def _make_untrack_callback(owner: str, name: str) -> str:
    return f"{_CB_PREFIX}{owner}|{name}"


def _parse_untrack_callback(data: str) -> Tuple[str, str]:
    _, owner, name = data.split("|", 2)
    return owner, name


async def untrack_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    repositories = db.get_user_repositories(user_id)

    if not repositories:
        await update.message.reply_text(
            "📋 You're not tracking any repositories yet.\n\nUse /track to add some!"
        )
        return

    keyboard = [
        [
            InlineKeyboardButton(
                f"🗑️ {repo['owner']}/{repo['name']}",
                callback_data=_make_untrack_callback(repo["owner"], repo["name"]),
            )
        ]
        for repo in repositories
    ]
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="untrack|cancel")])

    await update.message.reply_text(
        "🗑️ *Select a repository to stop tracking:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN,
    )


async def handle_untrack_callback(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "untrack|cancel":
        await query.edit_message_text("❌ Untracking cancelled.")
        return

    owner, name = _parse_untrack_callback(query.data)
    user_id = update.effective_user.id

    success = db.remove_user_repository(user_id, owner, name)
    if success:
        logger.info("User %s stopped tracking %s/%s", user_id, owner, name)
        await query.edit_message_text(
            f"✅ Stopped tracking `{owner}/{name}`.",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await query.edit_message_text(
            "❌ Could not remove that repository. It may have already been removed."
        )


untrack_callback_handler = CallbackQueryHandler(
    handle_untrack_callback, pattern=r"^untrack\|"
)
