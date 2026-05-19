from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from database import db

_PAGE_SIZE = 10


async def list_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    repositories = db.get_user_repositories(user_id)

    if not repositories:
        await update.message.reply_text(
            "📋 You're not tracking any repositories yet.\n\nUse /track to add one!"
        )
        return

    total = len(repositories)
    pages = [repositories[i : i + _PAGE_SIZE] for i in range(0, total, _PAGE_SIZE)]

    for page_num, page in enumerate(pages, 1):
        header = (
            "📋 *Tracked repositories:*\n\n"
            if page_num == 1
            else "📋 *…continued:*\n\n"
        )
        lines = []
        for i, r in enumerate(page, 1):
            line = f"{(page_num - 1) * _PAGE_SIZE + i}. `{r['owner']}/{r['name']}`"
            if r.get("keywords"):
                line += f"  (🔍 `{r['keywords']}`)"
            lines.append(line)
        await update.message.reply_text(
            header + "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
        )
