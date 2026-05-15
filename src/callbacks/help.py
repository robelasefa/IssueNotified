"""
Help command callback handler.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

import config

logger = logging.getLogger(__name__)


async def help_command(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_text = f"""
🤖 *IssueNotified Bot Help*

*Commands:*
• `/start` — Register your account
• `/track <owner/repo> [keywords]` — Track a repo
• `/list` — View all your tracked repositories
• `/search <query>` — Search GitHub repositories
• `/untrack` — Stop tracking a repository
• `/stop` — Delete your account and all data
• `/help` — Show this message

*Tracking a repository:*
Use `/track`, then send the repository in `owner/repo` format.
Example: `torvalds/linux`

*Searching:*
• `/search react` — find repos by name
• `/search facebook/react` — scoped to a specific owner

*Limits:*
• Max {config.MAX_REPOS_PER_USER} tracked repositories per user
• Notifications are checked every {config.ISSUE_CHECK_INTERVAL // 60} minutes

*Features:*
🔔 Automatic issue notifications
🔍 GitHub repository search with one-tap tracking
"""
    await update.message.reply_text(help_text.strip(), parse_mode="Markdown")
