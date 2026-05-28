import logging

from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ai import ai_client
from database import db
from github import build_notification_payload, get_github_client
from notifier import build_reply_markup, format_notification, matches_keywords

logger = logging.getLogger(__name__)


async def _enrich_with_summary(issue: dict) -> None:
    try:
        summary = await ai_client.summarize_issue(
            title=issue.get("title", ""),
            description=issue.get("description", ""),
        )
        if summary:
            issue["ai_summary"] = summary
    except Exception as e:
        logger.error("AI summary failed for issue %s: %s", issue.get("id"), e)


async def _notify_subscribers(context, subscribers, payload, owner, name) -> None:
    message = format_notification(owner, name, payload)
    reply_markup = build_reply_markup(owner, name, payload.get("url", ""))

    for sub in subscribers:
        if not matches_keywords(payload, sub["keywords"]):
            continue
        try:
            await context.bot.send_message(
                chat_id=sub["user_id"],
                text=message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.error(
                "Failed to notify user %s for %s/%s#%s: %s",
                sub["user_id"],
                owner,
                name,
                payload.get("number"),
                e,
            )


async def poll_repositories(context: ContextTypes.DEFAULT_TYPE) -> None:
    github_client = get_github_client()
    if not github_client:
        logger.error("Poller: GitHub client not initialised.")
        return

    repositories = db.get_all_tracked_repositories()
    if not repositories:
        return

    logger.debug("Polling %d repositories.", len(repositories))

    for repo in repositories:
        repo_id = repo["repo_id"]
        owner = repo["owner"]
        name = repo["name"]
        subscribers = repo["subscribers"]
        last_checked_at = repo.get("last_checked_at")  # ISO 8601 string or None

        is_first_poll = last_checked_at is None

        logger.debug("Polling %s/%s (since=%s)", owner, name, last_checked_at)

        current = await github_client.get_issues_snapshot(
            owner, name, since=last_checked_at
        )

        # Do NOT skip when current is empty — an empty result is legitimate
        #  (nothing changed since last check). Skipping would also mask a 422
        #  from a malformed `since` value and freeze last_checked_at permanently.
        stored = db.get_tracked_issues_for_repo(repo_id)

        for issue_id, issue in current.items():
            current_state = issue["state"]
            stored_state = stored.get(issue_id)

            if stored_state is None:
                # Record the issue in the DB regardless of whether we notify.
                db.add_tracked_issue(
                    issue_id=issue_id,
                    repository_id=repo_id,
                    title=issue.get("title", ""),
                    url=issue.get("url", ""),
                    state=current_state,
                )
                if is_first_poll:
                    # Silently snapshot all pre-existing issues so the user
                    #  isn't flooded with old notifications when they first
                    #  track a repository. Only issues that appear AFTER this
                    #  initial sweep will trigger a notification.
                    continue
                event_type = "opened"

            elif stored_state == "open" and current_state == "closed":
                event_type = "closed"
                db.update_issue_state(issue_id, "closed")
            elif stored_state == "closed" and current_state == "open":
                event_type = "reopened"
                db.update_issue_state(issue_id, "open")
            else:
                continue

            payload = build_notification_payload(issue, event_type)
            await _enrich_with_summary(payload)
            await _notify_subscribers(context, subscribers, payload, owner, name)

            logger.info(
                "Notified: %s %s/%s#%s", event_type, owner, name, issue.get("number")
            )

        db.update_repository_last_checked(repo_id)
