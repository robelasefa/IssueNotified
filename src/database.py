import logging
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

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

    @contextmanager
    def _get_conn(self):
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            try:
                yield conn
                conn.commit()
            except sqlite3.Error as e:
                conn.rollback()
                raise e
            finally:
                conn.close()

    def _execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        try:
            with self._get_conn() as conn:
                return conn.execute(sql, params)
        except sqlite3.Error as e:
            logger.error("Execute error (%s): %s", sql, e)
            return None

    def _query(self, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
        try:
            with self._get_conn() as conn:
                return conn.execute(sql, params).fetchall()
        except sqlite3.Error as e:
            logger.error("Query error (%s): %s", sql, e)
            return []

    def _query_one(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        try:
            with self._get_conn() as conn:
                return conn.execute(sql, params).fetchone()
        except sqlite3.Error as e:
            logger.error("Query one error (%s): %s", sql, e)
            return None

    def _init_schema(self) -> None:
        try:
            with self._get_conn() as conn:
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
                        last_checked_at TEXT,
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
                        state         TEXT NOT NULL DEFAULT 'open',
                        created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(repository_id) REFERENCES repositories(id)
                    );
                """)
        except sqlite3.Error as e:
            logger.error("Schema init error: %s", e)
        self._migrate()

    def _migrate(self) -> None:
        """Add columns introduced after the initial schema without wiping data."""
        try:
            with self._get_conn() as conn:
                existing = {
                    row["name"]
                    for row in conn.execute(
                        "PRAGMA table_info(tracked_issues)"
                    ).fetchall()
                }
                if "state" not in existing:
                    conn.execute(
                        "ALTER TABLE tracked_issues ADD COLUMN state TEXT NOT NULL DEFAULT 'open'"
                    )
                    logger.info("Migration: added `state` column to tracked_issues.")
        except sqlite3.Error as e:
            logger.error("Migration error: %s", e)

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    def add_user(
        self, user_id: int, username: str = None, first_name: str = None
    ) -> bool:
        return (
            self._execute(
                "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                (user_id, username, first_name),
            )
            is not None
        )

    def delete_user(self, user_id: int) -> bool:
        try:
            with self._get_conn() as conn:
                rows = conn.execute(
                    "SELECT repository_id FROM user_repositories WHERE user_id = ?",
                    (user_id,),
                ).fetchall()
                repo_ids = [r["repository_id"] for r in rows]
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
        rows = self._query("SELECT user_id FROM users")
        return [r["user_id"] for r in rows]

    # ------------------------------------------------------------------
    # Repositories
    # ------------------------------------------------------------------

    def add_repository(self, owner: str, name: str) -> Optional[int]:
        self._execute(
            "INSERT OR IGNORE INTO repositories (owner, name) VALUES (?, ?)",
            (owner, name),
        )
        row = self._query_one(
            "SELECT id FROM repositories WHERE owner = ? AND name = ?",
            (owner, name),
        )
        return row["id"] if row else None

    def get_repository_id(self, owner: str, name: str) -> Optional[int]:
        row = self._query_one(
            "SELECT id FROM repositories WHERE owner = ? AND name = ?",
            (owner, name),
        )
        return row["id"] if row else None

    def get_repository_with_subscribers(
        self, owner: str, name: str
    ) -> Optional[Dict[str, Any]]:
        rows = self._query(
            """
            SELECT r.id, u.user_id, ur.keywords
            FROM repositories r
            JOIN user_repositories ur ON r.id = ur.repository_id
            JOIN users u ON ur.user_id = u.user_id
            WHERE r.owner = ? AND r.name = ?
            """,
            (owner, name),
        )

        if not rows:
            repo_id = self.get_repository_id(owner, name)
            return {"repo_id": repo_id, "subscribers": []} if repo_id else None

        return {
            "repo_id": rows[0]["id"],
            "subscribers": [
                {"user_id": r["user_id"], "keywords": r["keywords"]} for r in rows
            ],
        }

    def link_user_repository(
        self, user_id: int, repository_id: int, keywords: str = None
    ) -> bool:
        try:
            with self._get_conn() as conn:
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
        rows = self._query(
            """
            SELECT r.owner, r.name, ur.keywords
            FROM repositories r
            JOIN user_repositories ur ON r.id = ur.repository_id
            WHERE ur.user_id = ?
            ORDER BY r.owner, r.name
            """,
            (user_id,),
        )
        return [
            {"owner": r["owner"], "name": r["name"], "keywords": r["keywords"]}
            for r in rows
        ]

    def count_user_repositories(self, user_id: int) -> int:
        row = self._query_one(
            "SELECT COUNT(*) as count FROM user_repositories WHERE user_id = ?",
            (user_id,),
        )
        return row["count"] if row else 0

    def is_user_tracking_repository(self, user_id: int, owner: str, name: str) -> bool:
        row = self._query_one(
            """
            SELECT 1 FROM repositories r
            JOIN user_repositories ur ON r.id = ur.repository_id
            WHERE ur.user_id = ? AND r.owner = ? AND r.name = ?
            """,
            (user_id, owner, name),
        )
        return row is not None

    def remove_user_repository(self, user_id: int, owner: str, name: str) -> bool:
        repo_id = self.get_repository_id(owner, name)
        if not repo_id:
            return False

        try:
            with self._get_conn() as conn:
                result = conn.execute(
                    "DELETE FROM user_repositories WHERE user_id = ? AND repository_id = ?",
                    (user_id, repo_id),
                )
                success = result.rowcount > 0

            if success:
                self.cleanup_repository_if_unused(repo_id)
            return success
        except sqlite3.Error as e:
            logger.error(
                "Error removing %s/%s for user %s: %s", owner, name, user_id, e
            )
            return False

    def get_all_tracked_repositories(self) -> List[Dict[str, Any]]:
        rows = self._query("""
            SELECT r.id, r.owner, r.name, u.user_id, ur.keywords, r.last_checked_at
            FROM repositories r
            JOIN user_repositories ur ON r.id = ur.repository_id
            JOIN users u ON ur.user_id = u.user_id
        """)

        repos: Dict[int, Dict] = {}
        for r in rows:
            repo_id = r["id"]
            if repo_id not in repos:
                repos[repo_id] = {
                    "repo_id": repo_id,
                    "owner": r["owner"],
                    "name": r["name"],
                    "subscribers": [],
                    "last_checked_at": r["last_checked_at"],
                }
            repos[repo_id]["subscribers"].append(
                {"user_id": r["user_id"], "keywords": r["keywords"]}
            )
        return list(repos.values())

    def update_repository_last_checked(self, repo_id: int) -> None:
        self._execute(
            "UPDATE repositories SET last_checked_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?",
            (repo_id,),
        )

    # ------------------------------------------------------------------
    # Issue tracking
    # ------------------------------------------------------------------

    def get_tracked_issues_for_repo(self, repository_id: int) -> Dict[str, str]:
        rows = self._query(
            "SELECT issue_id, state FROM tracked_issues WHERE repository_id = ?",
            (repository_id,),
        )
        return {r["issue_id"]: r["state"] for r in rows}

    def add_tracked_issue(
        self,
        issue_id: str,
        repository_id: int,
        title: str,
        url: str,
        state: str = "open",
    ) -> bool:
        return (
            self._execute(
                "INSERT OR IGNORE INTO tracked_issues (issue_id, repository_id, title, url, state) VALUES (?, ?, ?, ?, ?)",
                (issue_id, repository_id, title, url, state),
            )
            is not None
        )

    def update_issue_state(self, issue_id: str, new_state: str) -> bool:
        return (
            self._execute(
                "UPDATE tracked_issues SET state = ? WHERE issue_id = ?",
                (new_state, issue_id),
            )
            is not None
        )

    # ------------------------------------------------------------------
    # Admin / stats
    # ------------------------------------------------------------------

    def get_system_stats(self) -> Dict[str, int]:
        users = self._query_one("SELECT COUNT(*) as c FROM users")
        repos = self._query_one("SELECT COUNT(*) as c FROM repositories")
        issues = self._query_one("SELECT COUNT(*) as c FROM tracked_issues")

        return {
            "users": users["c"] if users else 0,
            "repositories": repos["c"] if repos else 0,
            "tracked_issues": issues["c"] if issues else 0,
        }

    def get_top_repositories(self, limit: int = 5) -> List[Dict[str, Any]]:
        rows = self._query(
            """
            SELECT r.owner, r.name, COUNT(ur.user_id) AS sub_count
            FROM repositories r
            JOIN user_repositories ur ON r.id = ur.repository_id
            GROUP BY r.id
            ORDER BY sub_count DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [
            {"owner": r["owner"], "name": r["name"], "subscribers": r["sub_count"]}
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup_repository_if_unused(self, repository_id: int) -> None:
        try:
            with self._get_conn() as conn:
                count_row = conn.execute(
                    "SELECT COUNT(*) as c FROM user_repositories WHERE repository_id = ?",
                    (repository_id,),
                ).fetchone()

                if count_row and count_row["c"] == 0:
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
