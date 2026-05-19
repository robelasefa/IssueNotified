import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import config
from database import db

logger = logging.getLogger(__name__)


async def stats_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    if user_id != config.ADMIN_USER_ID:
        logger.warning("Unauthorized access attempt to /stats by user %s", user_id)
        return

    stats = db.get_system_stats()
    top_repos = db.get_top_repositories(10)

    stats_text = (
        "📊 *System Statistics*\n\n"
        f"👥 *Total Users:* {stats['users']}\n"
        f"📂 *Total Repositories:* {stats['repositories']}\n"
        f"🔔 *Total Tracked Issues:* {stats['tracked_issues']}\n\n"
    )

    if top_repos:
        stats_text += "🏆 *Most Popular Repositories*\n"
        for i, repo in enumerate(top_repos, 1):
            stats_text += (
                f"{i}. `{repo['owner']}/{repo['name']}` — {repo['subscribers']} users\n"
            )
    else:
        stats_text += "🏆 *No repositories tracked yet.*"

    await update.message.reply_text(
        stats_text.strip(), parse_mode=ParseMode.MARKDOWN_V2
    )
