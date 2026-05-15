"""
GitHub API client with rate limiting.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp

import ratelimit

logger = logging.getLogger(__name__)


class GitHubClient:
    """Async GitHub API client with rate limiting."""

    def __init__(self, token: str):
        self.token = token
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
        """
        Make a rate-limited GET request to the GitHub API.

        Pass ``full_url`` to bypass the base-URL prefix (used by the search
        endpoint which lives at /search/repositories rather than /repos/…).
        """
        await self.rate_limiter.wait_if_needed("github")

        url = full_url if full_url else f"{self.base_url}/{endpoint}"

        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 404:
                        logger.warning(f"GitHub API 404: {url}")
                        return None
                    elif response.status == 403:
                        logger.error(f"GitHub API rate limit / forbidden: {url}")
                        return None
                    elif response.status == 422:
                        logger.warning(f"GitHub API unprocessable entity: {url}")
                        return None
                    else:
                        logger.error(f"GitHub API error {response.status}: {url}")
                        return None
        except aiohttp.ClientError as e:
            logger.error(f"Network error for {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error for {url}: {e}")
            return None

    # ------------------------------------------------------------------
    # Repository helpers
    # ------------------------------------------------------------------

    async def validate_repository(self, owner: str, repo: str) -> bool:
        """Check whether a repository exists and is accessible."""
        data = await self._make_request(f"repos/{owner}/{repo}")
        return data is not None

    async def get_repository_info(self, owner: str, repo: str) -> Optional[Dict]:
        """Return raw repository metadata from the GitHub API."""
        return await self._make_request(f"repos/{owner}/{repo}")

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search_repositories(
        self,
        query: str,
        per_page: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search GitHub repositories using the Search API.

        ``query`` may be a bare repo name (searched across all of GitHub) or
        an ``owner/repo`` string (qualified with the ``user:`` qualifier so
        results are scoped to that owner).

        Returns a list of dicts with keys:
            owner, name, description, stars, language, url
        """
        # Build a qualified search string when the caller passes owner/repo
        if "/" in query:
            parts = query.split("/", 1)
            owner_q, name_q = parts[0].strip(), parts[1].strip()
            # GitHub search qualifier: user:owner + repo name fragment
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

    # ------------------------------------------------------------------
    # Issue events
    # ------------------------------------------------------------------

    async def get_repository_issues_events(self, owner: str, repo: str) -> List[Dict]:
        """Fetch the latest issue events for a repository."""
        data = await self._make_request(f"repos/{owner}/{repo}/issues/events")
        if data is None:
            return []
        return data if isinstance(data, list) else []

    def format_issue_info(self, issue_event: Dict) -> Dict[str, Any]:
        """Normalise an issue-event payload into a flat dict for notifications."""
        if not issue_event or "issue" not in issue_event:
            return {}

        event_type = issue_event.get("event")
        if event_type not in ["opened", "closed"]:
            return {}

        issue = issue_event["issue"]
        created_at = issue_event.get("created_at", "")

        # Use UTC throughout to avoid local-timezone drift
        try:
            release_time = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
            now = datetime.now(timezone.utc)
            time_diff = now - release_time
            total_seconds = int(time_diff.total_seconds())

            if time_diff.days >= 1:
                time_str = (
                    f"{time_diff.days} day{'s' if time_diff.days > 1 else ''} ago"
                )
            elif total_seconds >= 3600:
                hours = total_seconds // 3600
                time_str = f"{hours} hour{'s' if hours > 1 else ''} ago"
            elif total_seconds >= 60:
                minutes = total_seconds // 60
                time_str = f"{minutes} minute{'s' if minutes > 1 else ''} ago"
            else:
                time_str = "just now"

            release_time_str = release_time.strftime("%Y-%m-%d %H:%M UTC")
            time_message = f"\n🕐 {release_time_str} ({time_str})\n"
        except ValueError:
            time_message = "\n🕐 Time released: Unknown\n"

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


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

github_client: Optional[GitHubClient] = None


def get_github_client() -> Optional[GitHubClient]:
    """Return the global GitHub client, or None if not yet initialised."""
    return github_client


def initialize_github_client(token: str) -> GitHubClient:
    """Create and store the global GitHub client."""
    global github_client
    github_client = GitHubClient(token)
    return github_client
