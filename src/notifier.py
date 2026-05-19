import logging
from typing import Any, Dict

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from ai import ai_client
from database import db
from github import format_webhook_issue

logger = logging.getLogger(__name__)

_EVENT_CONFIG = {
    "opened": {"icon": "🔔", "label": "NEW ISSUE"},
    "closed": {"icon": "✅", "label": "CLOSED"},
    "reopened": {"icon": "🔁", "label": "REOPENED"},
}


def _format_notification(owner: str, repo: str, issue: dict) -> str:
    title = issue.get("title", "No title")
    description = (issue.get("description") or "").strip()
    tags = issue.get("tags", [])
    assignee = issue.get("assignee")
    time_msg = issue.get("release_time_message", "").strip()
    number = issue.get("number", "?")
    ai_summary = issue.get("ai_summary")
    event_type = issue.get("event_type", "opened")

    ev = _EVENT_CONFIG.get(event_type, _EVENT_CONFIG["opened"])

    lines = [
        f"{ev['icon']} *{ev['label']}* • *{owner}/{repo}*",
        "",
        f"*#{number} — {title}*",
    ]

    if time_msg and "Unknown" not in time_msg:
        lines.append(time_msg)

    meta = []
    if tags:
        meta.append("🏷️ " + "  ".join(f"`{t}`" for t in tags[:5]))
    if assignee:
        meta.append(f"👤 @{assignee}")
    if meta:
        lines += ["", "  ".join(meta)]

    if ai_summary:
        lines += ["", "✨ *AI Summary:*", f"_{ai_summary}_"]
    elif description:
        excerpt = description[:280] + ("..." if len(description) > 280 else "")
        lines += ["", f"_{excerpt}_"]

    return "\n".join(lines)


def _matches_keywords(issue_info: Dict[str, Any], keywords_str: str) -> bool:
    if not keywords_str:
        return True

    keywords = [k.strip().lower() for k in keywords_str.split(",") if k.strip()]
    if not keywords:
        return True

    title = issue_info.get("title", "").lower()
    body = issue_info.get("description", "").lower()
    labels = [label.lower() for label in issue_info.get("tags", [])]

    return any(
        kw in title or kw in body or any(kw in label for label in labels)
        for kw in keywords
    )


def _build_reply_markup(owner: str, name: str, issue_url: str):
    if not issue_url:
        return None
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🌐 View on GitHub", url=issue_url),
                InlineKeyboardButton(
                    "🔕 Stop Tracking", callback_data=f"untrack|{owner}|{name}"
                ),
            ]
        ]
    )


async def process_github_webhook_event(payload: dict, bot: Bot) -> None:
    """Process a GitHub ``issues`` webhook event and dispatch Telegram notifications."""
    action = payload.get("action")
    if action not in ("opened", "closed", "reopened"):
        return

    repository = payload.get("repository", {})
    owner = repository.get("owner", {}).get("login", "")
    repo_name = repository.get("name", "")

    if not owner or not repo_name:
        logger.warning("Webhook payload missing repository owner/name.")
        return

    repo_data = db.get_repository_with_subscribers(owner, repo_name)
    if not repo_data:
        logger.debug("No subscribers for %s/%s — skipping.", owner, repo_name)
        return

    repo_id = repo_data["repo_id"]
    subscribers = repo_data["subscribers"]

    issue_info = format_webhook_issue(payload)
    issue_id = issue_info.get("id")

    if not issue_id or db.is_issue_tracked(issue_id):
        return

    try:
        summary = await ai_client.summarize_issue(
            title=issue_info.get("title", ""),
            description=issue_info.get("description", ""),
        )
        if summary:
            issue_info["ai_summary"] = summary
    except Exception as e:
        logger.error("AI summary failed for issue %s: %s", issue_id, e)

    # Record before sending — prevents duplicate notifications if send loop crashes mid-flight.
    db.add_tracked_issue(
        issue_id=issue_id,
        repository_id=repo_id,
        title=issue_info.get("title", ""),
        url=issue_info.get("url", ""),
    )

    message = _format_notification(owner, repo_name, issue_info)
    reply_markup = _build_reply_markup(owner, repo_name, issue_info.get("url", ""))

    logger.info(
        "Webhook: %s issue #%s in %s/%s",
        action,
        issue_info.get("number"),
        owner,
        repo_name,
    )

    for sub in subscribers:
        uid = sub["user_id"]
        keywords = sub["keywords"]

        if not _matches_keywords(issue_info, keywords):
            continue

        try:
            await bot.send_message(
                chat_id=uid,
                text=message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.error(
                "Failed to notify user %s for %s/%s#%s: %s",
                uid,
                owner,
                repo_name,
                issue_id,
                e,
            )

    db.update_repository_last_checked(repo_id)
