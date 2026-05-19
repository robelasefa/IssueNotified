import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp

import ratelimit

logger = logging.getLogger(__name__)


class GitHubClient:
    """Async GitHub REST API client with per-key rate limiting."""

    def __init__(self, token: str):
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "IssueNotified-Bot",
        }
        self.rate_limiter = ratelimit.github_rate_limiter

    async def _make_request(
        self,
        endpoint: str,
        params: Dict = None,
        *,
        full_url: str = None,
    ) -> Optional[Any]:
        """Rate-limited GET to the GitHub API.

        Pass ``full_url`` to bypass the ``/repos/…`` prefix (e.g. the search endpoint).
        """
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

    async def validate_repository(self, owner: str, repo: str) -> bool:
        return await self._make_request(f"repos/{owner}/{repo}") is not None

    async def get_repository_info(self, owner: str, repo: str) -> Optional[Dict]:
        return await self._make_request(f"repos/{owner}/{repo}")

    async def search_repositories(
        self, query: str, per_page: int = 10
    ) -> List[Dict[str, Any]]:
        """Search GitHub repos.

        Accepts a bare name or ``owner/repo``,  the latter is rewritten to
        ``name user:owner`` so results are scoped to that owner.
        """
        if "/" in query:
            owner_q, name_q = [p.strip() for p in query.split("/", 1)]
            q = f"{name_q} user:{owner_q}"
        else:
            q = query.strip()

        data = await self._make_request(
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

        results = []
        for item in data["items"]:
            results.append(
                {
                    "owner": item["owner"]["login"],
                    "name": item["name"],
                    "description": item.get("description")
                    or "No description available",
                    "stars": item.get("stargazers_count", 0),
                    "language": item.get("language") or "Unknown",
                    "url": item.get("html_url", ""),
                }
            )
        return results

    async def get_repository_issues_events(self, owner: str, repo: str) -> List[Dict]:
        data = await self._make_request(f"repos/{owner}/{repo}/issues/events")
        if data is None:
            return []
        return data if isinstance(data, list) else []

    def format_issue_info(self, issue_event: Dict) -> Dict[str, Any]:
        """Normalise a polling issue-event payload into the shared notification shape."""
        if not issue_event or "issue" not in issue_event:
            return {}

        event_type = issue_event.get("event")
        if event_type not in ("opened", "closed"):
            return {}

        issue = issue_event["issue"]
        created_at = issue_event.get("created_at", "")

        time_message = _format_time_message(created_at)

        labels = issue.get("labels", [])
        tags = [label["name"] for label in labels] if labels else []

        assignees = issue.get("assignees", [])
        assignee = assignees[0]["login"] if assignees else None

        return {
            "id": str(issue_event.get("id", "")),
            "title": issue.get("title", "No Title"),
            "url": issue.get("html_url", ""),
            "event_type": event_type,
            "description": issue.get("body") or "",
            "tags": tags,
            "assignee": assignee,
            "release_time_message": time_message,
            "state": issue.get("state", "open"),
            "number": issue.get("number"),
        }

    async def get_new_issues(
        self, owner: str, repo: str, tracked_issue_ids: set
    ) -> List[Dict]:
        """Return issue events that have not been notified yet."""
        events = await self.get_repository_issues_events(owner, repo)
        new_issues = []

        for event in events:
            issue_id = str(event.get("id", ""))
            if issue_id and issue_id not in tracked_issue_ids:
                issue_info = self.format_issue_info(event)
                if issue_info:
                    new_issues.append(issue_info)

        return new_issues

    async def create_webhook(
        self, owner: str, repo: str, webhook_url: str, secret: str
    ) -> Optional[int]:
        """Register an ``issues`` webhook on a GitHub repository.

        Returns the GitHub hook ID, or ``None`` on failure (e.g. insufficient permissions).
        """
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
                url = f"{self.base_url}/repos/{owner}/{repo}/hooks"
                async with session.post(url, json=payload) as response:
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
                url = f"{self.base_url}/repos/{owner}/{repo}/hooks/{hook_id}"
                async with session.delete(url) as response:
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


def format_webhook_issue(payload: Dict) -> Dict[str, Any]:
    """Convert a GitHub webhook ``issues`` payload into the shared notification shape."""
    action = payload.get("action", "opened")
    issue = payload.get("issue", {})

    event_type = "closed" if action == "closed" else "opened"

    created_at = issue.get("created_at", "")
    time_message = _format_time_message(created_at)

    labels = issue.get("labels", [])
    tags = [label["name"] for label in labels] if labels else []

    assignees = issue.get("assignees", [])
    assignee = assignees[0]["login"] if assignees else None

    return {
        "id": str(issue.get("id", "")),
        "title": issue.get("title", "No Title"),
        "url": issue.get("html_url", ""),
        "event_type": event_type,
        "description": issue.get("body") or "",
        "tags": tags,
        "assignee": assignee,
        "release_time_message": time_message,
        "state": issue.get("state", "open"),
        "number": issue.get("number"),
    }


def _format_time_message(created_at: str) -> str:
    try:
        release_time = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        now = datetime.now(timezone.utc)
        diff = now - release_time
        total_secs = int(diff.total_seconds())

        if diff.days >= 1:
            relative = f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif total_secs >= 3600:
            h = total_secs // 3600
            relative = f"{h} hour{'s' if h > 1 else ''} ago"
        elif total_secs >= 60:
            m = total_secs // 60
            relative = f"{m} minute{'s' if m > 1 else ''} ago"
        else:
            relative = "just now"

        release_time_utc = release_time.astimezone(timezone.utc)
        formatted = release_time_utc.strftime("%Y-%m-%d %I:%M %p %Z")
        return f"🕐 {formatted} ({relative})\n"
    except ValueError:
        return "🕐 Time released: Unknown\n"


github_client: Optional[GitHubClient] = None


def get_github_client() -> Optional[GitHubClient]:
    return github_client


def initialize_github_client(token: str) -> GitHubClient:
    global github_client
    github_client = GitHubClient(token)
    return github_client
