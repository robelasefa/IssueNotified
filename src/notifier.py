import logging
from typing import Any, Dict

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

_EVENT_CONFIG = {
    "opened": {"icon": "🔔", "label": "NEW ISSUE"},
    "closed": {"icon": "✅", "label": "CLOSED"},
    "reopened": {"icon": "🔁", "label": "REOPENED"},
}


def _format_notification(owner: str, repo: str, issue: dict) -> str:
    ev = _EVENT_CONFIG.get(issue.get("event_type", "opened"), _EVENT_CONFIG["opened"])
    number = issue.get("number", "?")
    title = issue.get("title", "No title")
    time_msg = issue.get("release_time_message", "").strip()
    tags = issue.get("tags", [])
    assignee = issue.get("assignee")
    ai_summary = issue.get("ai_summary")
    description = (issue.get("description") or "").strip()

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


def _build_reply_markup(
    owner: str, name: str, issue_url: str
) -> InlineKeyboardMarkup | None:
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
