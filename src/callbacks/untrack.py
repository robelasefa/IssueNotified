"""
Untrack command callback handlers.
"""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from database import db
from github import get_github_client

logger = logging.getLogger(__name__)

SELECT_REPO = 1

# Use a pipe separator so owner/repo names with underscores parse correctly.
_CB_PREFIX = "untrack|"


def _make_untrack_callback(owner: str, name: str) -> str:
    return f"{_CB_PREFIX}{owner}|{name}"


def _parse_untrack_callback(data: str):
    _, owner, name = data.split("|", 2)
    return owner, name


async def _try_delete_webhook(owner: str, name: str) -> None:
    """Delete the GitHub webhook for a repository if it exists and the repo
    has no remaining subscribers.
    """
    repo_id = db.get_repository_id(owner, name)
    if repo_id is None:
        return

    # Only delete if no subscribers remain
    repo_data = db.get_repository_with_subscribers(owner, name)
    if repo_data is not None:
        # Still has subscribers
        return

    hook_id = db.get_webhook(repo_id)
    if not hook_id:
        return

    github_client = get_github_client()
    if github_client:
        await github_client.delete_webhook(owner, name, hook_id)

    db.remove_webhook(repo_id)
    logger.info(f"Webhook removed for {owner}/{name}")


async def untrack_command(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """Show inline buttons for every tracked repository."""
    user_id = update.effective_user.id
    repositories = db.get_user_repositories(user_id)

    if not repositories:
        await update.message.reply_text(
            "📋 You're not tracking any repositories yet.\n\nUse /track to add some!"
        )
        return ConversationHandler.END

    keyboard = [
        [
            InlineKeyboardButton(
                f"🗑️ {repo['owner']}/{repo['name']}",
                callback_data=_make_untrack_callback(repo["owner"], repo["name"]),
            )
        ]
        for repo in repositories
    ]

    await update.message.reply_text(
        "🗑️ *Select a repository to stop tracking:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return SELECT_REPO


async def handle_untrack_callback(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """Process the untrack button press."""
    query = update.callback_query
    await query.answer()

    if not query.data.startswith(_CB_PREFIX):
        return ConversationHandler.END

    owner, name = _parse_untrack_callback(query.data)
    user_id = update.effective_user.id

    success = db.remove_user_repository(user_id, owner, name)
    if success:
        logger.info(f"User {user_id} stopped tracking {owner}/{name}")
        await query.edit_message_text(
            f"✅ Stopped tracking `{owner}/{name}`.",
            parse_mode="Markdown",
        )
        # Clean up the GitHub webhook if no subscribers remain
        await _try_delete_webhook(owner, name)
    else:
        await query.edit_message_text(
            "❌ Could not remove that repository. It may have already been removed."
        )

    return ConversationHandler.END


async def cancel_command(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """Cancel the untrack conversation."""
    await update.message.reply_text("❌ Untrack cancelled.")
    return ConversationHandler.END


untrack_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("untrack", untrack_command)],
    states={
        SELECT_REPO: [
            # The user taps a button — handled by the global callback handler below.
            # This state only needs a text fallback for accidental messages.
            MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: SELECT_REPO)
        ]
    },
    fallbacks=[CommandHandler("cancel", cancel_command)],
)

# Standalone callback handler registered in main.py so button presses work
# regardless of conversation state (e.g. after a bot restart).
untrack_callback_handler = CallbackQueryHandler(
    handle_untrack_callback, pattern=r"^untrack\|"
)
