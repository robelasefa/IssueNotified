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
        url = full_url if full_url else f"{self.base_url}/{endpoint}"
        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    if response.status == 404:
                        logger.warning("GitHub 404: %s", url)
                    elif response.status == 403:
                        logger.error("GitHub 403 (rate limit or forbidden): %s", url)
                    elif response.status == 422:
                        logger.warning("GitHub 422 (unprocessable): %s", url)
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
        self, owner: str, repo: str, tracked_issue_ids: set
    ) -> List[Dict]:
        events = await self.get_repository_issues_events(owner, repo)
        new_issues = []
        for event in events:
            issue_id = str(event.get("id", ""))
            if issue_id and issue_id not in tracked_issue_ids:
                info = _parse_issue_event(event)
                if info:
                    new_issues.append(info)
        return new_issues


def _parse_issue_event(event: Dict) -> Dict[str, Any]:
    if not event or "issue" not in event:
        return {}
    if event.get("event") not in ("open", "closed", "reopened"):
        return {}

    issue = event["issue"]
    assignees = issue.get("assignees", [])

    return {
        "id": str(event.get("id", "")),
        "title": issue.get("title", "No Title"),
        "url": issue.get("html_url", ""),
        "event_type": event["event"],
        "description": issue.get("body") or "",
        "tags": [label["name"] for label in issue.get("labels", [])],
        "assignee": assignees[0]["login"] if assignees else None,
        "release_time_message": _format_time_message(event.get("created_at", "")),
        "state": issue.get("state", "open"),
        "number": issue.get("number"),
    }


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


github_client: Optional[GitHubClient] = None


def get_github_client() -> Optional[GitHubClient]:
    return github_client


def initialize_github_client(token: str) -> GitHubClient:
    global github_client
    github_client = GitHubClient(token)
    return github_client
