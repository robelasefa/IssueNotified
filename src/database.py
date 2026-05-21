import logging
import sqlite3
import threading
from typing import Any, Dict, List, Optional, Set

import config

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self.db_path = db_path
        else:
            self.db_path = config.DATA_DIR / "issuenotified.db"
            config.DATA_DIR.mkdir(exist_ok=True)

        self._lock = threading.RLock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id    INTEGER PRIMARY KEY,
                    username   TEXT,
                    first_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS repositories (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner           TEXT NOT NULL,
                    name            TEXT NOT NULL,
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_checked_at TIMESTAMP,
                    UNIQUE(owner, name)
                );
                CREATE TABLE IF NOT EXISTS user_repositories (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id       INTEGER NOT NULL,
                    repository_id INTEGER NOT NULL,
                    keywords      TEXT,
                    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, repository_id),
                    FOREIGN KEY(user_id)       REFERENCES users(user_id),
                    FOREIGN KEY(repository_id) REFERENCES repositories(id)
                );
                CREATE TABLE IF NOT EXISTS tracked_issues (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    issue_id      TEXT NOT NULL UNIQUE,
                    repository_id INTEGER NOT NULL,
                    title         TEXT,
                    url           TEXT,
                    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(repository_id) REFERENCES repositories(id)
                );
            """)

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    def add_user(
        self, user_id: int, username: str = None, first_name: str = None
    ) -> bool:
        with self._lock:
            try:
                with self._connect() as conn:
                    conn.execute(
                        "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                        (user_id, username, first_name),
                    )
                    return True
            except sqlite3.Error as e:
                logger.error("Error adding user %s: %s", user_id, e)
                return False

    def delete_user(self, user_id: int) -> bool:
        with self._lock:
            try:
                with self._connect() as conn:
                    rows = conn.execute(
                        "SELECT repository_id FROM user_repositories WHERE user_id = ?",
                        (user_id,),
                    ).fetchall()
                    repo_ids = [r[0] for r in rows]
                    conn.execute(
                        "DELETE FROM user_repositories WHERE user_id = ?", (user_id,)
                    )
                    conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))

                for repo_id in repo_ids:
                    self.cleanup_repository_if_unused(repo_id)
                return True
            except sqlite3.Error as e:
                logger.error("Error deleting user %s: %s", user_id, e)
                return False

    def get_all_user_ids(self) -> List[int]:
        try:
            with self._connect() as conn:
                return [
                    r[0] for r in conn.execute("SELECT user_id FROM users").fetchall()
                ]
        except sqlite3.Error as e:
            logger.error("Error getting all user IDs: %s", e)
            return []

    # ------------------------------------------------------------------
    # Repositories
    # ------------------------------------------------------------------

    def add_repository(self, owner: str, name: str) -> Optional[int]:
        with self._lock:
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
                    return row[0] if row else None
            except sqlite3.Error as e:
                logger.error("Error adding repository %s/%s: %s", owner, name, e)
                return None

    def get_repository_id(self, owner: str, name: str) -> Optional[int]:
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT id FROM repositories WHERE owner = ? AND name = ?",
                    (owner, name),
                ).fetchone()
                return row[0] if row else None
        except sqlite3.Error as e:
            logger.error("Error fetching repository id for %s/%s: %s", owner, name, e)
            return None

    def get_repository_with_subscribers(
        self, owner: str, name: str
    ) -> Optional[Dict[str, Any]]:
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT r.id, u.user_id, ur.keywords
                    FROM repositories r
                    JOIN user_repositories ur ON r.id = ur.repository_id
                    JOIN users u ON ur.user_id = u.user_id
                    WHERE r.owner = ? AND r.name = ?
                    """,
                    (owner, name),
                ).fetchall()

                if not rows:
                    repo_id = self.get_repository_id(owner, name)
                    return {"repo_id": repo_id, "subscribers": []} if repo_id else None

                return {
                    "repo_id": rows[0][0],
                    "subscribers": [{"user_id": r[1], "keywords": r[2]} for r in rows],
                }
        except sqlite3.Error as e:
            logger.error(
                "Error fetching repository with subscribers %s/%s: %s", owner, name, e
            )
            return None

    def link_user_repository(
        self, user_id: int, repository_id: int, keywords: str = None
    ) -> bool:
        with self._lock:
            try:
                with self._connect() as conn:
                    conn.execute(
                        "INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,)
                    )
                    conn.execute(
                        "INSERT OR IGNORE INTO user_repositories (user_id, repository_id, keywords) VALUES (?, ?, ?)",
                        (user_id, repository_id, keywords),
                    )
                    return True
            except sqlite3.Error as e:
                logger.error(
                    "Error linking user %s to repo %s: %s", user_id, repository_id, e
                )
                return False

    def get_user_repositories(self, user_id: int) -> List[Dict[str, Any]]:
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
                return [{"owner": r[0], "name": r[1], "keywords": r[2]} for r in rows]
        except sqlite3.Error as e:
            logger.error("Error getting repositories for user %s: %s", user_id, e)
            return []

    def count_user_repositories(self, user_id: int) -> int:
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) FROM user_repositories WHERE user_id = ?",
                    (user_id,),
                ).fetchone()
                return row[0] if row else 0
        except sqlite3.Error as e:
            logger.error("Error counting repositories for user %s: %s", user_id, e)
            return 0

    def is_user_tracking_repository(self, user_id: int, owner: str, name: str) -> bool:
        try:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT 1 FROM repositories r
                    JOIN user_repositories ur ON r.id = ur.repository_id
                    WHERE ur.user_id = ? AND r.owner = ? AND r.name = ?
                    """,
                    (user_id, owner, name),
                ).fetchone()
                return row is not None
        except sqlite3.Error as e:
            logger.error("Error checking tracking status for user %s: %s", user_id, e)
            return False

    def remove_user_repository(self, user_id: int, owner: str, name: str) -> bool:
        with self._lock:
            try:
                repo_id = self.get_repository_id(owner, name)
                if not repo_id:
                    return False
                with self._connect() as conn:
                    result = conn.execute(
                        "DELETE FROM user_repositories WHERE user_id = ? AND repository_id = ?",
                        (user_id, repo_id),
                    )
                if result.rowcount > 0:
                    self.cleanup_repository_if_unused(repo_id)
                return result.rowcount > 0
            except sqlite3.Error as e:
                logger.error(
                    "Error removing %s/%s for user %s: %s", owner, name, user_id, e
                )
                return False

    def get_all_tracked_repositories(self) -> List[Dict[str, Any]]:
        try:
            with self._connect() as conn:
                rows = conn.execute("""
                    SELECT r.id, r.owner, r.name, u.user_id, ur.keywords, r.last_checked_at
                    FROM repositories r
                    JOIN user_repositories ur ON r.id = ur.repository_id
                    JOIN users u ON ur.user_id = u.user_id
                """).fetchall()

            repos: Dict[int, Dict] = {}
            for repo_id, owner, name, user_id, keywords, last_checked in rows:
                if repo_id not in repos:
                    repos[repo_id] = {
                        "repo_id": repo_id,
                        "owner": owner,
                        "name": name,
                        "subscribers": [],
                        "last_checked_at": last_checked,
                    }
                repos[repo_id]["subscribers"].append(
                    {"user_id": user_id, "keywords": keywords}
                )
            return list(repos.values())
        except sqlite3.Error as e:
            logger.error("Error getting all tracked repositories: %s", e)
            return []

    def update_repository_last_checked(self, repo_id: int) -> None:
        with self._lock:
            try:
                with self._connect() as conn:
                    conn.execute(
                        "UPDATE repositories SET last_checked_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (repo_id,),
                    )
            except sqlite3.Error as e:
                logger.error(
                    "Error updating last_checked_at for repo %s: %s", repo_id, e
                )

    # ------------------------------------------------------------------
    # Issue tracking
    # ------------------------------------------------------------------

    def is_issue_tracked(self, issue_id: str) -> bool:
        try:
            with self._connect() as conn:
                return (
                    conn.execute(
                        "SELECT 1 FROM tracked_issues WHERE issue_id = ?", (issue_id,)
                    ).fetchone()
                    is not None
                )
        except sqlite3.Error as e:
            logger.error("Error checking tracked issue %s: %s", issue_id, e)
            return False

    def add_tracked_issue(
        self, issue_id: str, repository_id: int, title: str, url: str
    ) -> bool:
        with self._lock:
            try:
                with self._connect() as conn:
                    conn.execute(
                        "INSERT OR IGNORE INTO tracked_issues (issue_id, repository_id, title, url) VALUES (?, ?, ?, ?)",
                        (issue_id, repository_id, title, url),
                    )
                    return True
            except sqlite3.Error as e:
                logger.error("Error adding tracked issue %s: %s", issue_id, e)
                return False

    def get_tracked_issue_ids_for_repo(self, repository_id: int) -> Set[str]:
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT issue_id FROM tracked_issues WHERE repository_id = ?",
                    (repository_id,),
                ).fetchall()
                return {r[0] for r in rows}
        except sqlite3.Error as e:
            logger.error(
                "Error fetching tracked issue ids for repo %s: %s", repository_id, e
            )
            return set()

    # ------------------------------------------------------------------
    # Admin / stats
    # ------------------------------------------------------------------

    def get_system_stats(self) -> Dict[str, int]:
        try:
            with self._connect() as conn:
                return {
                    "users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
                    "repositories": conn.execute(
                        "SELECT COUNT(*) FROM repositories"
                    ).fetchone()[0],
                    "tracked_issues": conn.execute(
                        "SELECT COUNT(*) FROM tracked_issues"
                    ).fetchone()[0],
                }
        except sqlite3.Error as e:
            logger.error("Error getting system stats: %s", e)
            return {"users": 0, "repositories": 0, "tracked_issues": 0}

    def get_top_repositories(self, limit: int = 5) -> List[Dict[str, Any]]:
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT r.owner, r.name, COUNT(ur.user_id) AS sub_count
                    FROM repositories r
                    JOIN user_repositories ur ON r.id = ur.repository_id
                    GROUP BY r.id
                    ORDER BY sub_count DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
                return [
                    {"owner": r[0], "name": r[1], "subscribers": r[2]} for r in rows
                ]
        except sqlite3.Error as e:
            logger.error("Error getting top repositories: %s", e)
            return []

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup_repository_if_unused(self, repository_id: int) -> None:
        with self._lock:
            try:
                with self._connect() as conn:
                    count = conn.execute(
                        "SELECT COUNT(*) FROM user_repositories WHERE repository_id = ?",
                        (repository_id,),
                    ).fetchone()[0]
                    if count == 0:
                        conn.execute(
                            "DELETE FROM tracked_issues WHERE repository_id = ?",
                            (repository_id,),
                        )
                        conn.execute(
                            "DELETE FROM repositories WHERE id = ?", (repository_id,)
                        )
                        logger.info("Cleaned up unused repository ID %s", repository_id)
            except sqlite3.Error as e:
                logger.error(
                    "Error during repository cleanup for repo %s: %s", repository_id, e
                )


db = DatabaseManager()
