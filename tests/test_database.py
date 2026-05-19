import os
import tempfile

import pytest

from src.database import DatabaseManager


@pytest.fixture
def db():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = os.path.join(tmpdir, "test_db.sqlite")
        manager = DatabaseManager(db_path=db_path)
        yield manager


def test_add_user(db):
    success = db.add_user(12345, "testuser", "Test")
    assert success is True

    with db._connect() as conn:
        row = conn.execute(
            "SELECT username FROM users WHERE user_id = 12345"
        ).fetchone()
        assert row[0] == "testuser"


def test_link_user_repository(db):
    repo_id = db.add_repository("owner", "repo")
    assert repo_id is not None

    success = db.link_user_repository(12345, repo_id, "bug,critical")
    assert success is True

    repos = db.get_user_repositories(12345)
    assert len(repos) == 1
    assert repos[0]["owner"] == "owner"
    assert repos[0]["keywords"] == "bug,critical"


def test_delete_user(db):
    repo_id = db.add_repository("owner", "repo")
    db.link_user_repository(12345, repo_id)

    success = db.delete_user(12345)
    assert success is True

    assert len(db.get_user_repositories(12345)) == 0
    with db._connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = 12345").fetchone()
        assert row is None


def test_tracked_issues(db):
    repo_id = db.add_repository("owner", "repo")
    db.add_tracked_issue("issue_1", repo_id, "Title", "http://url")

    assert db.is_issue_tracked("issue_1") is True
    assert db.is_issue_tracked("issue_2") is False

    ids = db.get_tracked_issue_ids_for_repo(repo_id)
    assert "issue_1" in ids


def test_cleanup_unused_repositories(db):
    repo_id = db.add_repository("owner", "repo")
    db.link_user_repository(12345, repo_id)

    with db._connect() as conn:
        row = conn.execute(
            "SELECT id FROM repositories WHERE id = ?", (repo_id,)
        ).fetchone()
        assert row is not None

    db.remove_user_repository(12345, "owner", "repo")

    with db._connect() as conn:
        row = conn.execute(
            "SELECT id FROM repositories WHERE id = ?", (repo_id,)
        ).fetchone()
        assert row is None
