import logging

from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from database import db
from github import get_github_client
from notifier import _build_reply_markup, _dispatch, _enrich_with_summary, _format_notification

logger = logging.getLogger(__name__)


async def poll_repositories(context: ContextTypes.DEFAULT_TYPE) -> None:
    github_client = get_github_client()
    if not github_client:
        logger.error("Poller: GitHub client not initialised.")
        return

    for repo in db.get_all_tracked_repositories():
        repo_id = repo["repo_id"]
        owner = repo["owner"]
        name = repo["name"]
        subscribers = repo["subscribers"]

        # Repos with active webhooks are handled by the push path
        if db.get_webhook(repo_id):
            continue

        logger.debug("Polling %s/%s", owner, name)

        tracked_ids = db.get_tracked_issue_ids_for_repo(repo_id)
        new_events = await github_client.get_new_issues(owner, name, tracked_ids)

        for issue_info in new_events:
            issue_id = issue_info["id"]

            # Persist before fan-out
            db.add_tracked_issue(
                issue_id=issue_id,
                repository_id=repo_id,
                title=issue_info.get("title", ""),
                url=issue_info.get("url", ""),
            )

            await _enrich_with_summary(issue_info)

            message = _format_notification(owner, name, issue_info)
            reply_markup = _build_reply_markup(owner, name, issue_info.get("url", ""))
            await _dispatch(context.bot, subscribers, issue_info, message, reply_markup, owner, name)

        db.update_repository_last_checked(repo_id)
