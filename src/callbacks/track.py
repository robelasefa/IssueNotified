import logging

from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import config
import validators
from database import db
from github import get_github_client

logger = logging.getLogger(__name__)

TRACK_REPO = 1


async def track_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id

    if db.count_user_repositories(user_id) >= config.MAX_REPOS_PER_USER:
        await update.message.reply_text(
            f"⚠️ You are already tracking the maximum limit of {config.MAX_REPOS_PER_USER} repositories.\n\n"
            "Please use /untrack to stop tracking some repositories first!",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "📌 *Track a repository*\n\n"
        "Send the repository in `owner/repo` format:\n"
        "Example: `facebook/react`\n\n"
        "Or type /cancel to abort.",
        parse_mode="Markdown",
    )
    return TRACK_REPO


async def _try_create_webhook(owner: str, name: str, repo_id: int) -> None:
    github_client = get_github_client()
    if not github_client or not config.WEBHOOK_BASE_URL:
        return

    if db.get_webhook(repo_id):
        return

    webhook_url = f"{config.WEBHOOK_BASE_URL}{config.GITHUB_WEBHOOK_PATH}"
    hook_id = await github_client.create_webhook(
        owner, name, webhook_url, config.WEBHOOK_SECRET
    )

    if hook_id:
        db.add_webhook(repo_id, hook_id)
        logger.info("Webhook installed for %s/%s (hook_id=%s)", owner, name, hook_id)
    else:
        logger.info(
            "Could not create webhook for %s/%s — manual intervention required",
            owner,
            name,
        )


async def handle_track_input(update: Update, _: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id

    if db.count_user_repositories(user_id) >= config.MAX_REPOS_PER_USER:
        await update.message.reply_text(
            f"⚠️ You're already tracking {config.MAX_REPOS_PER_USER} repositories, "
            "which is the current limit.\n\n"
            "Use /untrack to remove one before adding another."
        )
        return ConversationHandler.END

    try:
        owner, repo, keywords = validators.validate_repository_input(
            update.message.text
        )
    except validators.ValidationError as e:
        await update.message.reply_text(
            f"❌ {e}\n\nPlease try again or type /cancel to abort."
        )
        return TRACK_REPO

    github_client = get_github_client()
    if not github_client:
        await update.message.reply_text(
            "❌ GitHub client is not initialised. Contact the bot admin."
        )
        return ConversationHandler.END

    repo_data = await github_client.get_repository_info(owner, repo)
    if not repo_data:
        await update.message.reply_text(
            f"🔍 *Repository not found:* `{owner}/{repo}`\n\n"
            "This could be because:\n"
            "1. The repository is **private** and the bot doesn't have access.\n"
            "2. The name is misspelled.\n"
            "3. The repository does not exist.\n\n"
            "Please check the name and try again, or type /cancel.",
            parse_mode="Markdown",
        )
        return TRACK_REPO

    canonical_owner = repo_data.get("owner", {}).get("login", owner)
    canonical_name = repo_data.get("name", repo)

    if db.is_user_tracking_repository(user_id, canonical_owner, canonical_name):
        await update.message.reply_text(
            f"⚠️ You're already tracking `{canonical_owner}/{canonical_name}`!",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    repo_id = db.add_repository(canonical_owner, canonical_name)
    if not repo_id:
        await update.message.reply_text("❌ Error: Could not register repository.")
        return ConversationHandler.END

    success = db.link_user_repository(user_id, repo_id, keywords)
    if success:
        logger.info(
            "User %s started tracking %s/%s (keywords: %s)",
            user_id,
            canonical_owner,
            canonical_name,
            keywords,
        )
        msg = f"✅ Now tracking `{canonical_owner}/{canonical_name}`!"
        if keywords:
            msg += f"\n\n🔍 *Filter:* `{keywords}`"
        msg += "\n\nYou'll be notified when new issues are opened or closed."

        await update.message.reply_text(msg, parse_mode="Markdown")
        await _try_create_webhook(canonical_owner, canonical_name, repo_id)
    else:
        await update.message.reply_text(
            "❌ Failed to save the repository. Please try again."
        )

    return ConversationHandler.END


async def cancel_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Operation cancelled.")
    return ConversationHandler.END


track_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("track", track_command)],
    states={
        TRACK_REPO: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_track_input)
        ]
    },
    fallbacks=[CommandHandler("cancel", cancel_command)],
)
