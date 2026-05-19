"""
Background notification engine.

Processes GitHub webhook events and sends Telegram notifications
to subscribers of affected repositories.
"""

import logging
from typing import Any, Dict

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from ai import ai_client
from database import db
from github import format_webhook_issue

logger = logging.getLogger(__name__)


def _format_notification(owner: str, repo: str, issue: dict) -> str:
    """Build a Telegram-ready notification message for a single issue."""
    title = issue.get("title", "No title")
    description = (issue.get("description") or "").strip()
    tags = issue.get("tags", [])
    assignee = issue.get("assignee")
    time_message = issue.get("release_time_message", "").strip()
    number = issue.get("number", "?")
    ai_summary = issue.get("ai_summary")

    event_type = issue.get("event_type", "opened")

    config = {
        "opened": {"icon": "🔔", "label": "NEW ISSUE"},
        "closed": {"icon": "✅", "label": "CLOSED"},
        "reopened": {"icon": "🔁", "label": "REOPENED"},
    }
    ev = config.get(event_type, config["opened"])

    lines = [
        f"{ev['icon']} *{ev['label']}* • *{owner}/{repo}*",
        "",
        f"*#{number} — {title}*",
    ]

    lines.append(time_message)

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
    """Return True if the issue matches any of the comma-separated keywords."""
    if not keywords_str:
        return True

    keywords = [k.strip().lower() for k in keywords_str.split(",") if k.strip()]
    if not keywords:
        return True

    title = issue_info.get("title", "").lower()
    body = issue_info.get("description", "").lower()
    labels = [label.lower() for label in issue_info.get("tags", [])]

    for kw in keywords:
        if kw in title or kw in body or any(kw in label for label in labels):
            return True

    return False


def _build_reply_markup(owner: str, name: str, issue_url: str):
    """Build inline keyboard with View and Stop Tracking buttons."""
    if not issue_url:
        return None
    keyboard = [
        [
            InlineKeyboardButton("🌐 View on GitHub", url=issue_url),
            InlineKeyboardButton(
                "🔕 Stop Tracking",
                callback_data=f"untrack|{owner}|{name}",
            ),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


async def process_github_webhook_event(payload: dict, bot: Bot) -> None:
    """Process a GitHub webhook ``issues`` event and notify subscribers.

    Called by the FastAPI GitHub webhook endpoint.
    """
    action = payload.get("action")
    if action not in ("opened", "closed", "reopened"):
        return

    repository = payload.get("repository", {})
    owner = repository.get("owner", {}).get("login", "")
    repo_name = repository.get("name", "")

    if not owner or not repo_name:
        logger.warning("Webhook payload missing repository owner/name.")
        return

    # Look up subscribers for this repository
    repo_data = db.get_repository_with_subscribers(owner, repo_name)
    if not repo_data:
        logger.debug(f"No subscribers for {owner}/{repo_name}, skipping.")
        return

    repo_id = repo_data["repo_id"]
    subscribers = repo_data["subscribers"]

    # Normalise the webhook payload into our standard issue format
    issue_info = format_webhook_issue(payload)
    issue_id = issue_info["id"]

    if not issue_id:
        return

    # Deduplicate: skip if already notified
    if db.is_issue_tracked(issue_id):
        return

    # Try to get an AI summary (fails gracefully if API key is not set or times out)
    summary = None
    try:
        summary = await ai_client.summarize_issue(
            title=issue_info.get("title", ""),
            description=issue_info.get("description", ""),
        )
    except Exception as e:
        logger.error(f"Error getting AI summary for {issue_id}: {e}")

    if summary:
        issue_info["ai_summary"] = summary

    # Record issue before sending to prevent duplicates on crash
    db.add_tracked_issue(
        issue_id=issue_id,
        repository_id=repo_id,
        title=issue_info.get("title", ""),
        url=issue_info.get("url", ""),
    )

    message = _format_notification(owner, repo_name, issue_info)
    reply_markup = _build_reply_markup(owner, repo_name, issue_info.get("url", ""))

    logger.info(
        f"Webhook: {action} issue #{issue_info.get('number')} in {owner}/{repo_name}"
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
                parse_mode="Markdown",
                reply_markup=reply_markup,
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.error(
                f"Failed to notify user {uid} about {owner}/{repo_name}#{issue_id}: {e}"
            )

    db.update_repository_last_checked(repo_id)
