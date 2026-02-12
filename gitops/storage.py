# gitops/storage.py
# SQLite хранилище для отслеживания созданных Pull Requests

import os
import sqlite3
from datetime import datetime


class GitOpsPRStore:
    """SQLite хранилище для PR tracking."""

    def __init__(self, db_path: str = "data/gitops_prs.db"):
        self.db_path = db_path
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pull_requests (
                    pr_id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    policy_id       TEXT NOT NULL,
                    branch_name     TEXT NOT NULL,
                    pr_number       INTEGER NOT NULL,
                    pr_url          TEXT NOT NULL,
                    status          TEXT NOT NULL DEFAULT 'open',
                    provider        TEXT NOT NULL,
                    created_at      TEXT NOT NULL,
                    updated_at      TEXT,
                    UNIQUE(policy_id, provider)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_pr_policy 
                ON pull_requests(policy_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_pr_status 
                ON pull_requests(status)
            """)

    def save_pr(
        self,
        policy_id: str,
        branch_name: str,
        pr_number: int,
        pr_url: str,
        provider: str = "github",
    ) -> int:
        """Сохраняет информацию о созданном PR.

        Returns:
            pr_id автоинкрементный ID
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT OR REPLACE INTO pull_requests 
                   (policy_id, branch_name, pr_number, pr_url, provider, status, created_at)
                   VALUES (?, ?, ?, ?, ?, 'open', ?)""",
                (
                    policy_id,
                    branch_name,
                    pr_number,
                    pr_url,
                    provider,
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_pr_by_policy(self, policy_id: str) -> dict | None:
        """Получает PR информацию по policy_id."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM pull_requests WHERE policy_id = ?",
                (policy_id,),
            ).fetchone()

        if not row:
            return None

        return {
            "pr_id": row[0],
            "policy_id": row[1],
            "branch_name": row[2],
            "pr_number": row[3],
            "pr_url": row[4],
            "status": row[5],
            "provider": row[6],
            "created_at": row[7],
            "updated_at": row[8],
        }

    def list_prs(self, status: str = None) -> list[dict]:
        """Возвращает список всех PRs.

        Args:
            status: фильтр по статусу ('open', 'merged', 'closed')
        """
        with sqlite3.connect(self.db_path) as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM pull_requests WHERE status = ? ORDER BY created_at DESC",
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM pull_requests ORDER BY created_at DESC"
                ).fetchall()

        return [
            {
                "pr_id": r[0],
                "policy_id": r[1],
                "branch_name": r[2],
                "pr_number": r[3],
                "pr_url": r[4],
                "status": r[5],
                "provider": r[6],
                "created_at": r[7],
                "updated_at": r[8],
            }
            for r in rows
        ]

    def update_pr_status(self, pr_id: int, status: str) -> bool:
        """Обновляет статус PR.

        Returns:
            True если обновлено
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE pull_requests SET status = ?, updated_at = ? WHERE pr_id = ?",
                (status, datetime.utcnow().isoformat(), pr_id),
            )
            conn.commit()
            return cursor.rowcount > 0
