import os
import tempfile

import pytest

from src.database import DatabaseManager


@pytest.fixture
def db():
    """Fixture to provide a temporary database for each test."""
    # ignore_cleanup_errors=True handles Windows permission errors with SQLite WAL files
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = os.path.join(tmpdir, "test_db.sqlite")
        manager = DatabaseManager(db_path=db_path)
        yield manager


def test_add_user(db):
    """Test adding a new user."""
    success = db.add_user(12345, "testuser", "Test")
    assert success is True

    # Verify user exists
    with db._connect() as conn:
        row = conn.execute(
            "SELECT username FROM users WHERE user_id = 12345"
        ).fetchone()
        assert row[0] == "testuser"


def test_link_user_repository(db):
    """Test linking a user to a repository."""
    # First add a repository
    repo_id = db.add_repository("owner", "repo")
    assert repo_id is not None

    # Link user (this also implicitly adds the user)
    success = db.link_user_repository(12345, repo_id, "bug,critical")
    assert success is True

    # Verify link and keywords
    repos = db.get_user_repositories(12345)
    assert len(repos) == 1
    assert repos[0]["owner"] == "owner"
    assert repos[0]["keywords"] == "bug,critical"


def test_delete_user(db):
    """Test user deletion and cascading links."""
    repo_id = db.add_repository("owner", "repo")
    db.link_user_repository(12345, repo_id)

    success = db.delete_user(12345)
    assert success is True

    # Verify user and links are gone
    assert len(db.get_user_repositories(12345)) == 0
    with db._connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = 12345").fetchone()
        assert row is None


def test_tracked_issues(db):
    """Test tracking and checking issues."""
    repo_id = db.add_repository("owner", "repo")

    db.add_tracked_issue("issue_1", repo_id, "Title", "http://url")

    # Check if already tracked
    assert db.is_issue_tracked("issue_1") is True
    assert db.is_issue_tracked("issue_2") is False

    # Get all ids for repo
    ids = db.get_tracked_issue_ids_for_repo(repo_id)
    assert "issue_1" in ids


def test_cleanup_unused_repositories(db):
    """Test that repositories without subscribers are removed."""
    repo_id = db.add_repository("owner", "repo")
    db.link_user_repository(12345, repo_id)

    # Verify it exists
    with db._connect() as conn:
        row = conn.execute(
            "SELECT id FROM repositories WHERE id = ?", (repo_id,)
        ).fetchone()
        assert row is not None

    # Untrack
    db.remove_user_repository(12345, "owner", "repo")

    # Verify repository is gone from the database entirely
    with db._connect() as conn:
        row = conn.execute(
            "SELECT id FROM repositories WHERE id = ?", (repo_id,)
        ).fetchone()
        assert row is None
