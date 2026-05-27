from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from src.github import GitHubClient, _parse_issue, build_notification_payload


@pytest.fixture
def client():
    return GitHubClient("fake_token")


@pytest.mark.asyncio
async def test_get_repository_info_success(client):
    mock_response = AsyncMock(spec=aiohttp.ClientResponse)
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"id": 123})
    mock_get = MagicMock()
    mock_get.__aenter__.return_value = mock_response
    with patch("aiohttp.ClientSession.get", return_value=mock_get):
        info = await client.get_repository_info("owner", "repo")
        assert info == {"id": 123}


@pytest.mark.asyncio
async def test_get_repository_info_not_found(client):
    mock_response = AsyncMock(spec=aiohttp.ClientResponse)
    mock_response.status = 404
    mock_get = MagicMock()
    mock_get.__aenter__.return_value = mock_response
    with patch("aiohttp.ClientSession.get", return_value=mock_get):
        info = await client.get_repository_info("owner", "repo")
        assert info is None


@pytest.mark.asyncio
async def test_get_issues(client):
    issues_data = [
        {"id": 1, "number": 1, "title": "New Issue", "html_url": "url"},
        {"id": 2, "number": 2, "title": "PR", "html_url": "url", "pull_request": {}},
    ]
    mock_response = AsyncMock(spec=aiohttp.ClientResponse)
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=issues_data)
    mock_get = MagicMock()
    mock_get.__aenter__.return_value = mock_response
    with patch("aiohttp.ClientSession.get", return_value=mock_get):
        issues = await client.get_issues("owner", "repo")
        # PR should be filtered out
        assert len(issues) == 1
        assert issues[0]["id"] == 1


def test_parse_issue():
    raw_issue = {
        "id": 101,
        "number": 42,
        "title": "Bug Report",
        "html_url": "http://github/issue/42",
        "body": "Something is broken",
        "state": "open",
        "labels": [{"name": "bug"}, {"name": "high"}],
        "assignees": [{"login": "merti"}],
        "created_at": "2026-05-20T10:00:00Z",
        "updated_at": "2026-05-20T11:00:00Z",
    }
    parsed = _parse_issue(raw_issue)
    assert parsed["id"] == "101"
    assert parsed["number"] == 42
    assert parsed["title"] == "Bug Report"
    assert parsed["tags"] == ["bug", "high"]
    assert parsed["assignee"] == "merti"
    assert parsed["state"] == "open"


def test_build_notification_payload():
    parsed_issue = {
        "id": "101",
        "created_at": "2026-05-20T10:00:00Z",
        "updated_at": "2026-05-20T11:00:00Z",
    }

    with patch("src.github._format_time_message", return_value="just now"):
        payload = build_notification_payload(parsed_issue, "opened")
        assert payload["event_type"] == "opened"
        assert payload["release_time_message"] == "just now"
