import logging
from typing import Any, Dict, List, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, ContextTypes

import config
from database import db
from github import get_github_client

logger = logging.getLogger(__name__)

_CB_PREFIX = "track|"


def _make_track_callback(owner: str, repo: str) -> str:
    return f"{_CB_PREFIX}{owner}|{repo}"


def _parse_track_callback(data: str) -> Tuple[str, str]:
    _, owner, repo = data.split("|", 2)
    return owner, repo


async def _delete_loading(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    msg_id = context.chat_data.pop("search_loading_msg_id", None)
    if msg_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass


def _build_results_message(
    search_term: str,
    results: List[Dict[str, Any]],
    current_repos: List[Dict[str, Any]],
) -> Tuple[str, InlineKeyboardMarkup]:
    tracked_set = {(r["owner"], r["name"]) for r in current_repos}
    slots_left = config.MAX_REPOS_PER_USER - len(current_repos)

    lines = [f"🔍 *Results for* `{search_term}`\n"]
    keyboard = []

    for i, repo in enumerate(results[:10], 1):
        owner = repo["owner"]
        name = repo["name"]
        desc_raw = repo.get("description") or "No description"
        description = desc_raw[:60] + ("..." if len(desc_raw) > 60 else "")
        stars = repo.get("stars", 0)
        language = repo.get("language") or "Unknown"
        is_tracked = (owner, name) in tracked_set

        status_icon = "✅" if is_tracked else "📂"
        repo_url = repo.get("url") or f"https://github.com/{owner}/{name}"
        lines.append(
            f"{i}. {status_icon} **[{owner}/{name}]({repo_url})**\n"
            f"   ⭐ {stars:,}  •  {language}\n"
            f"   _{description}_\n"
        )

        btn_label = (
            f"✅ {owner}/{name} (tracked)"
            if is_tracked
            else f"➕ Track  {owner}/{name}"
        )
        keyboard.append(
            [
                InlineKeyboardButton(
                    btn_label, callback_data=_make_track_callback(owner, name)
                )
            ]
        )

    total = len(results)
    if total > 10:
        lines.append(f"\n_Showing 10 of {total} results._")

    lines.append(
        f"\n📊 *Tracked:* {len(current_repos)}/{config.MAX_REPOS_PER_USER}"
        + (
            f" — {slots_left} slot{'s' if slots_left != 1 else ''} remaining"
            if slots_left > 0
            else " — limit reached"
        )
    )

    return "\n".join(lines), InlineKeyboardMarkup(keyboard)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            "🔍 *Usage:* `/search <repository_name>`\n\n"
            "Examples:\n"
            "• `/search react` — search by repository name\n"
            "• `/search facebook/react` — search within an owner's repos\n",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    search_term = " ".join(context.args).strip()
    github_client = get_github_client()

    if not github_client:
        await update.message.reply_text(
            "Sorry, this is on us not your problem! Please try again later."
        )
        logger.error("[CRITICAL] GITHUB CLIENT IS NOT INITIALISED!")
        return

    loading_msg = await update.message.reply_text("🔍 Searching…")
    context.chat_data["search_loading_msg_id"] = loading_msg.message_id

    try:
        results = await github_client.search_repositories(search_term, per_page=10)
    except Exception as e:
        logger.error("search_repositories raised unexpectedly: %s", e)
        await _delete_loading(context, update.effective_chat.id)
        await update.message.reply_text(
            "❌ An error occurred while searching. Please try again."
        )
        return

    await _delete_loading(context, update.effective_chat.id)

    if not results:
        await update.message.reply_text(
            f"😕 No repositories found for `{search_term}`.\n\n"
            "Try a different name or check the spelling.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    user_id = update.effective_user.id
    current_repos = db.get_user_repositories(user_id)

    text, markup = _build_results_message(search_term, results, current_repos)
    await update.message.reply_text(
        text,
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
    )


async def handle_search_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()

    if not query.data.startswith(_CB_PREFIX):
        return

    owner, repo = _parse_track_callback(query.data)
    user_id = update.effective_user.id

    if db.is_user_tracking_repository(user_id, owner, repo):
        await query.answer(f"You're already tracking {owner}/{repo}!", show_alert=True)
        return

    if db.count_user_repositories(user_id) >= config.MAX_REPOS_PER_USER:
        await query.edit_message_text(
            f"⚠️ You have reached your limit of {config.MAX_REPOS_PER_USER} tracked repositories.\n\n"
            "Please untrack a repository first using /untrack before tracking new ones!",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    repo_id = db.add_repository(owner, repo)
    if not repo_id:
        await query.answer("❌ Error: Could not register repository.", show_alert=True)
        return

    success = db.link_user_repository(user_id, repo_id)
    if success:
        logger.info("User %s added %s/%s via search", user_id, owner, repo)
        await query.edit_message_text(
            f"✅ Now tracking `{owner}/{repo}`!\n\n"
            f"Use /list to see all your tracked repositories.",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await query.edit_message_text("❌ Failed to add repository. Please try again.")


search_callback_handler = CallbackQueryHandler(
    handle_search_callback, pattern=r"^track\|"
)
