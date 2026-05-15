"""
Database module for IssueNotified bot using SQLite.
"""

import logging
import sqlite3
from typing import Any, Dict, List, Optional, Set

import config

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages SQLite database operations for bot."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self.db_path = db_path
        else:
            self.db_path = config.DATA_DIR / "issuenotified.db"
            config.DATA_DIR.mkdir(exist_ok=True)

        self.init_database()

    def _connect(self) -> sqlite3.Connection:
        """Open a connection with WAL mode and foreign key enforcement."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def init_database(self):
        """Initialize database tables."""

        with self._connect() as conn:
            cursor = conn.cursor()

            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Repositories table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS repositories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner TEXT NOT NULL,
                    name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_checked_at TIMESTAMP,
                    UNIQUE(owner, name)
                )
            """)

            # User repositories table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_repositories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    repository_id INTEGER NOT NULL,
                    keywords TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, repository_id),
                    FOREIGN KEY(user_id) REFERENCES users(user_id),
                    FOREIGN KEY(repository_id) REFERENCES repositories(id)
                )
            """)

            # Tracked issues table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tracked_issues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    issue_id TEXT NOT NULL UNIQUE,
                    repository_id INTEGER NOT NULL,
                    title TEXT,
                    url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(repository_id) REFERENCES repositories(id)
                )
            """)

            conn.commit()

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    def add_user(
        self, user_id: int, username: str = None, first_name: str = None
    ) -> bool:
        """Add a new user to database."""
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                    (user_id, username, first_name),
                )
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"Error adding user: {e}")
            return False

    def delete_user(self, user_id: int) -> bool:
        """Remove a user and all their repository links from the database."""
        try:
            with self._connect() as conn:
                conn.execute(
                    "DELETE FROM user_repositories WHERE user_id = ?", (user_id,)
                )
                conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"Error deleting user {user_id}: {e}")
            return False

    # ------------------------------------------------------------------
    # Repositories
    # ------------------------------------------------------------------

    def add_repository(self, owner: str, name: str) -> Optional[int]:
        """Insert a repository if not present and return its ID."""
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO repositories (owner, name) VALUES (?, ?)",
                    (owner, name),
                )
                row = conn.execute(
                    "SELECT id FROM repositories WHERE owner = ? AND name = ?",
                    (owner, name),
                ).fetchone()
                conn.commit()
                return row[0] if row else None
        except sqlite3.Error as e:
            logger.error(f"Error adding repository {owner}/{name}: {e}")
            return None

    def get_repository_id(self, owner: str, name: str) -> Optional[int]:
        """Return the DB id for a repository, or None if not found."""
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT id FROM repositories WHERE owner = ? AND name = ?",
                    (owner, name),
                ).fetchone()
                return row[0] if row else None
        except sqlite3.Error as e:
            logger.error(f"Error fetching repository id for {owner}/{name}: {e}")
            return None

    def link_user_repository(
        self, user_id: int, repository_id: int, keywords: Optional[str] = None
    ) -> bool:
        """Link a user to a repository with optional keyword filters."""
        try:
            with self._connect() as conn:
                # Ensure the user exists in the users table first (Foreign Key requirement)
                conn.execute(
                    "INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,)
                )

                conn.execute(
                    """
                    INSERT OR IGNORE INTO user_repositories (user_id, repository_id, keywords)
                    VALUES (?, ?, ?)
                    """,
                    (user_id, repository_id, keywords),
                )
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"Error linking user {user_id} to repo {repository_id}: {e}")
            return False

    def get_user_repositories(self, user_id: int) -> List[Dict[str, Any]]:
        """Return all repositories tracked by a user."""
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT r.owner, r.name, ur.keywords
                    FROM repositories r
                    JOIN user_repositories ur ON r.id = ur.repository_id
                    WHERE ur.user_id = ?
                    ORDER BY r.owner, r.name
                    """,
                    (user_id,),
                ).fetchall()
                return [
                    {"owner": row[0], "name": row[1], "keywords": row[2]}
                    for row in rows
                ]
        except sqlite3.Error as e:
            logger.error(f"Error getting repositories for user {user_id}: {e}")
            return []

    def count_user_repositories(self, user_id: int) -> int:
        """Return how many repositories a user is currently tracking."""
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) FROM user_repositories WHERE user_id = ?",
                    (user_id,),
                ).fetchone()
                return row[0] if row else 0
        except sqlite3.Error as e:
            logger.error(f"Error counting repositories for user {user_id}: {e}")
            return 0

    def is_user_tracking_repository(self, user_id: int, owner: str, name: str) -> bool:
        """Check if user is already tracking a specific repository."""
        try:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT 1
                    FROM repositories r
                    JOIN user_repositories ur ON r.id = ur.repository_id
                    WHERE ur.user_id = ? AND r.owner = ? AND r.name = ?
                    """,
                    (user_id, owner, name),
                ).fetchone()
                return row is not None
        except sqlite3.Error as e:
            logger.error(f"Error checking tracking status for user {user_id}: {e}")
            return False

    def remove_user_repository(self, user_id: int, owner: str, name: str) -> bool:
        """Remove a single repository from a user's tracking list."""
        try:
            with self._connect() as conn:
                result = conn.execute(
                    """
                    DELETE FROM user_repositories
                    WHERE user_id = ? AND repository_id IN (
                        SELECT id FROM repositories WHERE owner = ? AND name = ?
                    )
                    """,
                    (user_id, owner, name),
                )
                conn.commit()

                if result.rowcount > 0:
                    # Clean up the repository if it has no more subscribers
                    self.cleanup_unused_repositories()

                return result.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Error removing {owner}/{name} for user {user_id}: {e}")
            return False

    def remove_all_user_repositories(self, user_id: int) -> bool:
        """Remove all repositories for a user."""
        try:
            with self._connect() as conn:
                conn.execute(
                    "DELETE FROM user_repositories WHERE user_id = ?", (user_id,)
                )
                conn.commit()
                self.cleanup_unused_repositories()
                return True
        except sqlite3.Error as e:
            logger.error(f"Error removing all repositories for user {user_id}: {e}")
            return False

    # ------------------------------------------------------------------
    # Issue tracking
    # ------------------------------------------------------------------

    def is_issue_tracked(self, issue_id: str) -> bool:
        """Check if an issue event has already been notified."""
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT 1 FROM tracked_issues WHERE issue_id = ?", (issue_id,)
                ).fetchone()
                return row is not None
        except sqlite3.Error as e:
            logger.error(f"Error checking tracked issue {issue_id}: {e}")
            return False

    def add_tracked_issue(
        self, issue_id: str, repository_id: int, title: str, url: str
    ) -> bool:
        """Record that an issue event has been notified."""
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO tracked_issues (issue_id, repository_id, title, url) VALUES (?, ?, ?, ?)",
                    (issue_id, repository_id, title, url),
                )
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"Error adding tracked issue {issue_id}: {e}")
            return False

    def get_tracked_issue_ids_for_repo(self, repository_id: int) -> Set[str]:
        """Return the set of already-notified issue IDs for a repository."""
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT issue_id FROM tracked_issues WHERE repository_id = ?",
                    (repository_id,),
                ).fetchall()
                return {row[0] for row in rows}
        except sqlite3.Error as e:
            logger.error(
                f"Error fetching tracked issue ids for repo {repository_id}: {e}"
            )
            return set()

    def get_all_tracked_repositories(self) -> List[Dict[str, Any]]:
        """
        Return every unique (owner, name, repo_id) plus the list of user_ids
        subscribed to it, so the notification loop avoids redundant API calls.
        """
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT 
                        r.id, 
                        r.owner, 
                        r.name, 
                        GROUP_CONCAT(u.user_id || ':' || IFNULL(ur.keywords, '')), 
                        r.last_checked_at
                    FROM repositories r
                    JOIN user_repositories ur ON r.id = ur.repository_id
                    JOIN users u ON ur.user_id = u.user_id
                    GROUP BY r.id, r.owner, r.name
                    """
                ).fetchall()
                return [
                    {
                        "repo_id": row[0],
                        "owner": row[1],
                        "name": row[2],
                        "subscribers": [
                            {
                                "user_id": int(s.split(":")[0]),
                                "keywords": s.split(":")[1],
                            }
                            for s in row[3].split(",")
                        ],
                        "last_checked_at": row[4],
                    }
                    for row in rows
                ]
        except sqlite3.Error as e:
            logger.error(f"Error getting all tracked repositories: {e}")
            return []

    def update_repository_last_checked(self, repo_id: int) -> bool:
        """Update the last_checked_at timestamp for a repository."""
        try:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE repositories SET last_checked_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (repo_id,),
                )
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"Error updating last_checked_at for repo {repo_id}: {e}")
            return False

    def get_all_user_ids(self) -> List[int]:
        """Return all unique user IDs in the database."""
        try:
            with self._connect() as conn:
                rows = conn.execute("SELECT user_id FROM users").fetchall()
                return [row[0] for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Error getting all user IDs: {e}")
            return []

    def get_system_stats(self) -> Dict[str, int]:
        """Return high-level system statistics."""
        try:
            with self._connect() as conn:
                user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
                repo_count = conn.execute(
                    "SELECT COUNT(*) FROM repositories"
                ).fetchone()[0]
                issue_count = conn.execute(
                    "SELECT COUNT(*) FROM tracked_issues"
                ).fetchone()[0]
                return {
                    "users": user_count,
                    "repositories": repo_count,
                    "tracked_issues": issue_count,
                }
        except sqlite3.Error as e:
            logger.error(f"Error getting system stats: {e}")
            return {"users": 0, "repositories": 0, "tracked_issues": 0}

    def get_top_repositories(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Return the most tracked repositories."""
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT r.owner, r.name, COUNT(ur.user_id) as sub_count
                    FROM repositories r
                    JOIN user_repositories ur ON r.id = ur.repository_id
                    GROUP BY r.id
                    ORDER BY sub_count DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
                return [
                    {"owner": row[0], "name": row[1], "subscribers": row[2]}
                    for row in rows
                ]
        except sqlite3.Error as e:
            logger.error(f"Error getting top repositories: {e}")
            return []

    def cleanup_unused_repositories(self):
        """
        Delete repositories that no longer have any subscribers.
        Also removes their associated tracked issues to free up space.
        """
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    DELETE FROM repositories 
                    WHERE id NOT IN (SELECT DISTINCT repository_id FROM user_repositories)
                    """
                )
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Error during repository cleanup: {e}")


# Global database instance
db = DatabaseManager()
