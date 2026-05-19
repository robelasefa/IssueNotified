from telegram import Update
from telegram.ext import ContextTypes

import config


async def help_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
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

*Features:*
• Real-time issue notifications
• GitHub repository search with one-tap tracking
"""
    await update.message.reply_text(help_text.strip(), parse_mode="Markdown")
