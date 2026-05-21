import logging

from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ai import ai_client
from database import db
from github import get_github_client
from notifier import _build_reply_markup, _format_notification, _matches_keywords

logger = logging.getLogger(__name__)


async def poll_repositories(context: ContextTypes.DEFAULT_TYPE) -> None:
    github_client = get_github_client()
    if not github_client:
        logger.error("Poller: GitHub client not initialised.")
        return

    repositories = db.get_all_tracked_repositories()
    if not repositories:
        return

    logger.debug("Polling %d repositories for new issues.", len(repositories))

    for repo in repositories:
        repo_id = repo["repo_id"]
        owner = repo["owner"]
        name = repo["name"]
        subscribers = repo["subscribers"]

        tracked_ids = db.get_tracked_issue_ids_for_repo(repo_id)
        new_events = await github_client.get_new_issues(owner, name, tracked_ids)

        for issue_info in new_events:
            issue_id = issue_info["id"]

            # Persist before fan-out so a crash mid-send doesn't re-notify on restart
            db.add_tracked_issue(
                issue_id=issue_id,
                repository_id=repo_id,
                title=issue_info.get("title", ""),
                url=issue_info.get("url", ""),
            )

            try:
                summary = await ai_client.summarize_issue(
                    title=issue_info.get("title", ""),
                    description=issue_info.get("description", ""),
                )
                if summary:
                    issue_info["ai_summary"] = summary
            except Exception as e:
                logger.error("AI summary failed for issue %s: %s", issue_id, e)

            message = _format_notification(owner, name, issue_info)
            reply_markup = _build_reply_markup(owner, name, issue_info.get("url", ""))

            for sub in subscribers:
                if not _matches_keywords(issue_info, sub["keywords"]):
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
                        issue_id,
                        e,
                    )

        db.update_repository_last_checked(repo_id)
