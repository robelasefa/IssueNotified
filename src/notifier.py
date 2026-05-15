"""
Background notification engine.

Runs on a JobQueue schedule and pushes Telegram messages whenever new
issues are opened in a tracked repository.
"""

import logging
from typing import Any, Dict, List

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import db
from github import get_github_client

logger = logging.getLogger(__name__)


def _format_notification(owner: str, repo: str, issue: dict) -> str:
    """Build a Telegram-ready notification message for a single issue."""
    title = issue.get("title", "No title")
    description = (issue.get("description") or "").strip()
    tags = issue.get("tags", [])
    assignee = issue.get("assignee")
    time_message = issue.get("release_time_message", "")
    number = issue.get("number", "?")

    event_type = issue.get("event_type", "opened")
    icon = "🔔" if event_type == "opened" else "✅"
    action = "New Issue" if event_type == "opened" else "Issue Closed"

    header = f"{icon} *{action} in {owner}/{repo}*"

    lines = [
        header,
        "",
        f"*#{number} — {title}*",
        time_message.strip(),
    ]

    if description:
        # Trim long bodies so the message stays readable
        excerpt = description[:300] + ("…" if len(description) > 300 else "")
        lines += ["", excerpt]

    if tags:
        lines += ["", "🏷️ " + "  ".join(f"`{t}`" for t in tags)]

    if assignee:
        lines += [f"👤 Assigned to @{assignee}"]

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


async def check_for_new_issues(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    JobQueue callback - called every `ISSUE_CHECK_INTERVAL` seconds.

    Fetches issue events once per repository (not once per subscriber),
    marks new events as notified, then fans out Telegram messages to every
    user who tracks that repository.
    """
    github_client = get_github_client()
    if not github_client:
        logger.warning("Notification check skipped: GitHub client not initialised.")
        return

    repos = db.get_all_tracked_repositories()
    if not repos:
        return

    logger.info(f"Checking {len(repos)} tracked repositories for new issues…")

    for repo_entry in repos:
        repo_id: int = repo_entry["repo_id"]
        owner: str = repo_entry["owner"]
        name: str = repo_entry["name"]
        subscribers: List[Dict[str, Any]] = repo_entry["subscribers"]
        last_checked: str = repo_entry.get("last_checked_at")
        is_first_check = last_checked is None

        try:
            tracked_ids = db.get_tracked_issue_ids_for_repo(repo_id)
            new_issues = await github_client.get_new_issues(owner, name, tracked_ids)

            if not new_issues:
                continue

            logger.info(f"Found {len(new_issues)} new issue(s) in {owner}/{name}")

            for issue in new_issues:
                issue_id = issue["id"]
                # Persist before sending so a crash mid-loop doesn't re-send
                db.add_tracked_issue(
                    issue_id=issue_id,
                    repository_id=repo_id,
                    title=issue.get("title", ""),
                    url=issue.get("url", ""),
                )

                if is_first_check:
                    continue

                message = _format_notification(owner, name, issue)

                # Add inline button for the issue URL
                reply_markup = None
                if issue.get("url"):
                    keyboard = [
                        [
                            InlineKeyboardButton("🌐 View on GitHub", url=issue["url"]),
                            InlineKeyboardButton(
                                "🔕 Stop Tracking",
                                callback_data=f"untrack|{owner}|{name}",
                            ),
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                for sub in subscribers:
                    uid = sub["user_id"]
                    keywords = sub["keywords"]

                    if not _matches_keywords(issue, keywords):
                        continue

                    try:
                        await context.bot.send_message(
                            chat_id=uid,
                            text=message,
                            parse_mode="Markdown",
                            reply_markup=reply_markup,
                            disable_web_page_preview=True,
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to notify user {uid} about {owner}/{name}#{issue_id}: {e}"
                        )

            # If this is the first time we've checked this repo, we "seed" the state
            # by marking existing issues as tracked without sending notifications.
            # This prevents a flood of alerts when a user adds a popular repository.
            if is_first_check:
                logger.info(
                    f"First-time check for {owner}/{name}: seeded state without notifying."
                )

            db.update_repository_last_checked(repo_id)

        except Exception as e:
            logger.error(f"Error processing {owner}/{name}: {e}")
