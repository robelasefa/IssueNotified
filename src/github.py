import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp

import ratelimit

logger = logging.getLogger(__name__)


class GitHubClient:
    def __init__(self, token: str):
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "IssueNotified-Bot",
        }
        self.rate_limiter = ratelimit.github_rate_limiter

    async def _get(
        self, endpoint: str, params: Dict = None, *, full_url: str = None
    ) -> Optional[Any]:
        await self.rate_limiter.wait_if_needed("github")
        url = full_url or f"{self.base_url}/{endpoint}"
        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    if response.status == 404:
                        logger.warning("GitHub 404: %s", url)
                    elif response.status == 403:
                        logger.error("GitHub 403 (rate limit or forbidden): %s", url)
                    else:
                        logger.error("GitHub %s: %s", response.status, url)
                    return None
        except aiohttp.ClientError as e:
            logger.error("Network error for %s: %s", url, e)
            return None

    async def get_repository_info(self, owner: str, repo: str) -> Optional[Dict]:
        return await self._get(f"repos/{owner}/{repo}")

    async def search_repositories(
        self, query: str, per_page: int = 10
    ) -> List[Dict[str, Any]]:
        # Scope to owner when caller passes owner/repo
        if "/" in query:
            owner_q, name_q = [p.strip() for p in query.split("/", 1)]
            q = f"{name_q} user:{owner_q}"
        else:
            q = query.strip()

        data = await self._get(
            "",
            full_url=f"{self.base_url}/search/repositories",
            params={
                "q": q,
                "sort": "stars",
                "order": "desc",
                "per_page": str(per_page),
            },
        )
        if not data or "items" not in data:
            return []

        return [
            {
                "owner": item["owner"]["login"],
                "name": item["name"],
                "description": item.get("description") or "No description available",
                "stars": item.get("stargazers_count", 0),
                "language": item.get("language") or "Unknown",
                "url": item.get("html_url", ""),
            }
            for item in data["items"]
        ]

    async def get_repository_issues_events(self, owner: str, repo: str) -> List[Dict]:
        data = await self._get(f"repos/{owner}/{repo}/issues/events")
        return data if isinstance(data, list) else []

    async def get_new_issues(
        self, owner: str, repo: str, tracked_ids: set
    ) -> List[Dict]:
        events = await self.get_repository_issues_events(owner, repo)
        result = []
        for event in events:
            issue_id = str(event.get("id", ""))
            if issue_id and issue_id not in tracked_ids:
                info = _parse_issue_event(event)
                if info:
                    result.append(info)
        return result

    async def create_webhook(
        self, owner: str, repo: str, webhook_url: str, secret: str
    ) -> Optional[int]:
        await self.rate_limiter.wait_if_needed("github")
        payload = {
            "name": "web",
            "active": True,
            "events": ["issues"],
            "config": {
                "url": webhook_url,
                "content_type": "json",
                "secret": secret,
                "insecure_ssl": "0",
            },
        }
        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.post(
                    f"{self.base_url}/repos/{owner}/{repo}/hooks", json=payload
                ) as response:
                    if response.status == 201:
                        data = await response.json()
                        logger.info("Webhook created for %s/%s", owner, repo)
                        return data.get("id")
                    body = await response.text()
                    logger.warning(
                        "Failed to create webhook for %s/%s: %s — %s",
                        owner,
                        repo,
                        response.status,
                        body,
                    )
                    return None
        except aiohttp.ClientError as e:
            logger.error("Network error creating webhook for %s/%s: %s", owner, repo, e)
            return None

    async def delete_webhook(self, owner: str, repo: str, hook_id: int) -> bool:
        await self.rate_limiter.wait_if_needed("github")
        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.delete(
                    f"{self.base_url}/repos/{owner}/{repo}/hooks/{hook_id}"
                ) as response:
                    if response.status == 204:
                        logger.info(
                            "Webhook %s deleted for %s/%s", hook_id, owner, repo
                        )
                        return True
                    logger.warning(
                        "Failed to delete webhook %s for %s/%s: %s",
                        hook_id,
                        owner,
                        repo,
                        response.status,
                    )
                    return False
        except aiohttp.ClientError as e:
            logger.error("Network error deleting webhook for %s/%s: %s", owner, repo, e)
            return False


def _format_time_message(created_at: str) -> str:
    try:
        dt = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        secs = int((datetime.now(timezone.utc) - dt).total_seconds())

        if secs >= 86400:
            d = secs // 86400
            relative = f"{d} day{'s' if d > 1 else ''} ago"
        elif secs >= 3600:
            h = secs // 3600
            relative = f"{h} hour{'s' if h > 1 else ''} ago"
        elif secs >= 60:
            m = secs // 60
            relative = f"{m} minute{'s' if m > 1 else ''} ago"
        else:
            relative = "just now"

        return f"🕐 {dt.strftime('%Y-%m-%d %I:%M %p UTC')} ({relative})\n"
    except ValueError:
        return "🕐 Time released: Unknown\n"


def _parse_issue_event(event: Dict) -> Dict[str, Any]:
    """Normalise a polling issue-event payload into the shared notification shape."""
    if not event or "issue" not in event:
        return {}
    if event.get("event") not in ("opened", "closed"):
        return {}

    issue = event["issue"]
    assignees = issue.get("assignees", [])
    return {
        "id": str(event.get("id", "")),
        "title": issue.get("title", "No Title"),
        "url": issue.get("html_url", ""),
        "event_type": event["event"],
        "description": issue.get("body") or "",
        "tags": [l["name"] for l in issue.get("labels", [])],
        "assignee": assignees[0]["login"] if assignees else None,
        "release_time_message": _format_time_message(event.get("created_at", "")),
        "state": issue.get("state", "open"),
        "number": issue.get("number"),
    }


def format_webhook_issue(payload: Dict) -> Dict[str, Any]:
    """Convert a GitHub webhook ``issues`` payload into the shared notification shape."""
    action = payload.get("action", "opened")
    issue = payload.get("issue", {})
    assignees = issue.get("assignees", [])

    # reopened is treated as opened for display purposes
    event_type = "closed" if action == "closed" else "opened"

    return {
        "id": str(issue.get("id", "")),
        "title": issue.get("title", "No Title"),
        "url": issue.get("html_url", ""),
        "event_type": event_type,
        "description": issue.get("body") or "",
        "tags": [l["name"] for l in issue.get("labels", [])],
        "assignee": assignees[0]["login"] if assignees else None,
        "release_time_message": _format_time_message(issue.get("created_at", "")),
        "state": issue.get("state", "open"),
        "number": issue.get("number"),
    }


github_client: Optional[GitHubClient] = None


def get_github_client() -> Optional[GitHubClient]:
    return github_client


def initialize_github_client(token: str) -> GitHubClient:
    global github_client
    github_client = GitHubClient(token)
    return github_client
