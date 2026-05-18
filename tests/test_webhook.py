"""
Tests for the webhook module — GitHub signature verification and event processing.
"""

import hashlib
import hmac
from unittest.mock import AsyncMock, patch

import pytest

from src.webhook import verify_github_signature

# ---------------------------------------------------------------------------
# GitHub signature verification
# ---------------------------------------------------------------------------


class TestGitHubSignatureVerification:
    """Tests for verify_github_signature."""

    def _sign(self, body: bytes, secret: str) -> str:
        """Create a valid HMAC-SHA256 signature."""
        digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return f"sha256={digest}"

    @patch("src.webhook.WEBHOOK_SECRET", "test-secret")
    def test_valid_signature(self):
        body = b'{"action": "opened"}'
        sig = self._sign(body, "test-secret")
        assert verify_github_signature(body, sig) is True

    @patch("src.webhook.WEBHOOK_SECRET", "test-secret")
    def test_invalid_signature(self):
        body = b'{"action": "opened"}'
        assert verify_github_signature(body, "sha256=bad") is False

    @patch("src.webhook.WEBHOOK_SECRET", "test-secret")
    def test_missing_signature(self):
        body = b'{"action": "opened"}'
        assert verify_github_signature(body, None) is False

    @patch("src.webhook.WEBHOOK_SECRET", "")
    def test_empty_secret(self):
        body = b'{"action": "opened"}'
        assert verify_github_signature(body, "sha256=anything") is False


# ---------------------------------------------------------------------------
# Webhook issue formatting
# ---------------------------------------------------------------------------


class TestFormatWebhookIssue:
    """Tests for format_webhook_issue."""

    def test_opened_issue(self):
        from src.github import format_webhook_issue

        payload = {
            "action": "opened",
            "issue": {
                "id": 12345,
                "title": "Bug in login",
                "html_url": "https://github.com/owner/repo/issues/1",
                "body": "Login is broken",
                "state": "open",
                "number": 1,
                "created_at": "2026-01-01T00:00:00Z",
                "labels": [{"name": "bug"}],
                "assignees": [{"login": "dev1"}],
            },
        }
        result = format_webhook_issue(payload)

        assert result["id"] == "12345"
        assert result["title"] == "Bug in login"
        assert result["event_type"] == "opened"
        assert result["tags"] == ["bug"]
        assert result["assignee"] == "dev1"
        assert result["number"] == 1

    def test_closed_issue(self):
        from src.github import format_webhook_issue

        payload = {
            "action": "closed",
            "issue": {
                "id": 99,
                "title": "Fixed",
                "html_url": "https://github.com/o/r/issues/2",
                "body": "",
                "state": "closed",
                "number": 2,
                "created_at": "2026-01-01T00:00:00Z",
                "labels": [],
                "assignees": [],
            },
        }
        result = format_webhook_issue(payload)

        assert result["event_type"] == "closed"
        assert result["assignee"] is None

    def test_reopened_maps_to_opened(self):
        from src.github import format_webhook_issue

        payload = {
            "action": "reopened",
            "issue": {
                "id": 50,
                "title": "Reopened",
                "html_url": "",
                "body": None,
                "state": "open",
                "number": 3,
                "created_at": "2026-01-01T00:00:00Z",
                "labels": [],
                "assignees": [],
            },
        }
        result = format_webhook_issue(payload)
        assert result["event_type"] == "opened"


# ---------------------------------------------------------------------------
# Webhook event processing
# ---------------------------------------------------------------------------


class TestProcessGitHubWebhookEvent:
    """Tests for process_github_webhook_event."""

    @pytest.fixture
    def mock_bot(self):
        bot = AsyncMock()
        bot.send_message = AsyncMock()
        return bot

    @pytest.fixture
    def sample_payload(self):
        return {
            "action": "opened",
            "repository": {
                "name": "test-repo",
                "owner": {"login": "test-owner"},
            },
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

        payload = {"action": "labeled", "repository": {}, "issue": {}}
        await process_github_webhook_event(payload, mock_bot)

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
            "subscribers": [
                {"user_id": 100, "keywords": "unrelated-keyword"},
            ],
        }
        mock_db.is_issue_tracked.return_value = False

        await process_github_webhook_event(sample_payload, mock_bot)
        mock_bot.send_message.assert_not_called()
