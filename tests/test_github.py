from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from src.github import GitHubClient


@pytest.fixture
def client():
    # We create a client with a fake token for testing
    return GitHubClient("fake_token")


@pytest.mark.asyncio
async def test_validate_repository_success(client):
    """Test successful repository validation by mocking the GitHub response."""
    mock_response = AsyncMock(spec=aiohttp.ClientResponse)
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"id": 123})

    # Mocking ClientSession.get context manager
    mock_get = MagicMock()
    mock_get.__aenter__.return_value = mock_response

    with patch("aiohttp.ClientSession.get", return_value=mock_get):
        is_valid = await client.validate_repository("owner", "repo")
        assert is_valid is True


@pytest.mark.asyncio
async def test_validate_repository_not_found(client):
    """Test repository validation when the repository does not exist."""
    mock_response = AsyncMock(spec=aiohttp.ClientResponse)
    mock_response.status = 404

    mock_get = MagicMock()
    mock_get.__aenter__.return_value = mock_response

    with patch("aiohttp.ClientSession.get", return_value=mock_get):
        is_valid = await client.validate_repository("owner", "repo")
        assert is_valid is False


@pytest.mark.asyncio
async def test_get_new_issues_filtering(client):
    """Test fetching issues while filtering out already tracked IDs and wrong events."""
    events = [
        {
            "id": "1",
            "event": "opened",
            "issue": {"number": 1, "title": "New", "html_url": "url"},
        },
        {
            "id": "2",
            "event": "closed",
            "issue": {"number": 2, "title": "Closed", "html_url": "url"},
        },
        {
            "id": "3",
            "event": "labeled",
            "issue": {"number": 3, "title": "Ignored", "html_url": "url"},
        },
    ]

    mock_response = AsyncMock(spec=aiohttp.ClientResponse)
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=events)

    mock_get = MagicMock()
    mock_get.__aenter__.return_value = mock_response

    with patch("aiohttp.ClientSession.get", return_value=mock_get):
        # "1" is already tracked, "2" is new (closed), "3" is ignored (wrong event type)
        new_issues = await client.get_new_issues("owner", "repo", {"1"})

        # Should only find the 'closed' event "2"
        assert len(new_issues) == 1
        assert new_issues[0]["id"] == "2"
        assert new_issues[0]["event_type"] == "closed"


def test_format_issue_info_mapping(client):
    """Test that format_issue_info correctly maps GitHub event data to our internal format."""
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

    info = client.format_issue_info(event)

    assert info["id"] == "event_id"
    assert info["title"] == "Bug Report"
    assert info["event_type"] == "opened"
    assert info["tags"] == ["bug", "high"]
    assert info["assignee"] == "merti"
