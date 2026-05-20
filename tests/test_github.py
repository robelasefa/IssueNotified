from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from src.github import GitHubClient, _parse_issue_event


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
async def test_get_new_issues_filtering(client):
    events = [
        {"id": "1", "event": "opened", "issue": {"number": 1, "title": "New", "html_url": "url"}},
        {"id": "2", "event": "closed", "issue": {"number": 2, "title": "Closed", "html_url": "url"}},
        {"id": "3", "event": "labeled", "issue": {"number": 3, "title": "Ignored", "html_url": "url"}},
    ]
    mock_response = AsyncMock(spec=aiohttp.ClientResponse)
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=events)
    mock_get = MagicMock()
    mock_get.__aenter__.return_value = mock_response
    with patch("aiohttp.ClientSession.get", return_value=mock_get):
        new_issues = await client.get_new_issues("owner", "repo", {"1"})
        assert len(new_issues) == 1
        assert new_issues[0]["id"] == "2"
        assert new_issues[0]["event_type"] == "closed"


def test_parse_issue_event_mapping():
    event = {
        "id": "event_id",
        "event": "opened",
        "issue": {
            "number": 101,
            "title": "Bug Report",
            "html_url": "http://github/issue/101",
            "body": "Something is broken",
            "labels": [{"name": "bug"}, {"name": "high"}],
            "assignees": [{"login": "merti"}],
        },
    }
    info = _parse_issue_event(event)
    assert info["id"] == "event_id"
    assert info["title"] == "Bug Report"
    assert info["event_type"] == "opened"
    assert info["tags"] == ["bug", "high"]
    assert info["assignee"] == "merti"
