from unittest.mock import AsyncMock, patch

import pytest

from src.notifier import _matches_keywords


def test_matches_keywords_no_keywords():
    issue = {"title": "Hello World", "description": "This is a test", "tags": ["bug"]}
    assert _matches_keywords(issue, "") is True
    assert _matches_keywords(issue, None) is True


def test_matches_keywords_in_title():
    issue = {"title": "CRITICAL: Database down", "description": "...", "tags": []}
    assert _matches_keywords(issue, "critical") is True
    assert _matches_keywords(issue, "safe") is False


def test_matches_keywords_in_body():
    issue = {
        "title": "Error",
        "description": "This is a security vulnerability",
        "tags": [],
    }
    assert _matches_keywords(issue, "security") is True


def test_matches_keywords_in_tags():
    issue = {"title": "Update", "description": "...", "tags": ["feature", "ui"]}
    assert _matches_keywords(issue, "ui") is True
    assert _matches_keywords(issue, "ux") is False


def test_matches_keywords_comma_separated():
    issue = {"title": "Small bug", "description": "...", "tags": ["minor"]}
    assert _matches_keywords(issue, "critical,bug,emergency") is True


def test_matches_keywords_case_insensitive():
    issue = {"title": "BUG FOUND", "description": "...", "tags": []}
    assert _matches_keywords(issue, "bug") is True


class TestProcessGitHubWebhookEvent:
    @pytest.fixture
    def mock_bot(self):
        bot = AsyncMock()
        bot.send_message = AsyncMock()
        return bot

    @pytest.fixture
    def sample_payload(self):
        return {
            "action": "opened",
            "repository": {"name": "test-repo", "owner": {"login": "test-owner"}},
            "issue": {
                "id": 777,
                "title": "Test Issue",
                "html_url": "https://github.com/test-owner/test-repo/issues/1",
                "body": "This is a test issue body",
                "state": "open",
                "number": 1,
                "created_at": "2026-01-01T00:00:00Z",
                "labels": [],
                "assignees": [],
            },
        }

    @patch("src.notifier.db")
    @pytest.mark.asyncio
    async def test_skips_irrelevant_actions(self, mock_db, mock_bot):
        from src.notifier import process_github_webhook_event

        await process_github_webhook_event(
            {"action": "labeled", "repository": {}, "issue": {}}, mock_bot
        )
        mock_db.get_repository_with_subscribers.assert_not_called()
        mock_bot.send_message.assert_not_called()

    @patch("src.notifier.db")
    @pytest.mark.asyncio
    async def test_skips_untracked_repo(self, mock_db, mock_bot, sample_payload):
        from src.notifier import process_github_webhook_event

        mock_db.get_repository_with_subscribers.return_value = None
        await process_github_webhook_event(sample_payload, mock_bot)
        mock_bot.send_message.assert_not_called()

    @patch("src.notifier.db")
    @pytest.mark.asyncio
    async def test_notifies_subscribers(self, mock_db, mock_bot, sample_payload):
        from src.notifier import process_github_webhook_event

        mock_db.get_repository_with_subscribers.return_value = {
            "repo_id": 1,
            "subscribers": [
                {"user_id": 100, "keywords": ""},
                {"user_id": 200, "keywords": ""},
            ],
        }
        mock_db.is_issue_tracked.return_value = False

        await process_github_webhook_event(sample_payload, mock_bot)
        assert mock_bot.send_message.call_count == 2
        mock_db.add_tracked_issue.assert_called_once()

    @patch("src.notifier.db")
    @pytest.mark.asyncio
    async def test_skips_already_tracked_issue(self, mock_db, mock_bot, sample_payload):
        from src.notifier import process_github_webhook_event

        mock_db.get_repository_with_subscribers.return_value = {
            "repo_id": 1,
            "subscribers": [{"user_id": 100, "keywords": ""}],
        }
        mock_db.is_issue_tracked.return_value = True

        await process_github_webhook_event(sample_payload, mock_bot)
        mock_bot.send_message.assert_not_called()

    @patch("src.notifier.db")
    @pytest.mark.asyncio
    async def test_keyword_filtering(self, mock_db, mock_bot, sample_payload):
        from src.notifier import process_github_webhook_event

        mock_db.get_repository_with_subscribers.return_value = {
            "repo_id": 1,
            "subscribers": [{"user_id": 100, "keywords": "unrelated-keyword"}],
        }
        mock_db.is_issue_tracked.return_value = False

        await process_github_webhook_event(sample_payload, mock_bot)
        mock_bot.send_message.assert_not_called()
