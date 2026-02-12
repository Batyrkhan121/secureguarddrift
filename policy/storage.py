# policy/storage.py
# SQLite хранилище для NetworkPolicy предложений

import os
import sqlite3
import json
from datetime import datetime, timezone
from policy.generator import PolicySuggestion


class PolicyStore:
    """SQLite хранилище для policy suggestions."""

    def __init__(self, db_path: str = "data/policies.db"):
        self.db_path = db_path
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS policies (
                    policy_id       TEXT PRIMARY KEY,
                    yaml_spec       TEXT NOT NULL,
                    reason          TEXT NOT NULL,
                    risk_score      INTEGER NOT NULL,
                    severity        TEXT NOT NULL,
                    source          TEXT NOT NULL,
                    destination     TEXT NOT NULL,
                    auto_apply_safe INTEGER NOT NULL,
                    status          TEXT NOT NULL DEFAULT 'pending',
                    created_at      TEXT NOT NULL,
                    updated_at      TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_policies_status 
                ON policies(status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_policies_severity 
                ON policies(severity)
            """)

    def save_policy(self, suggestion: PolicySuggestion) -> None:
        """Сохраняет policy suggestion в БД."""
        with sqlite3.connect(self.db_path) as conn:
            yaml_spec = json.dumps(suggestion.yaml_dict) if suggestion.yaml_dict else ""
            conn.execute(
                """INSERT OR REPLACE INTO policies 
                   (policy_id, yaml_spec, reason, risk_score, severity, source, destination,
                    auto_apply_safe, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
                (
                    suggestion.policy_id,
                    yaml_spec,
                    suggestion.reason,
                    suggestion.risk_score,
                    suggestion.severity,
                    suggestion.source,
                    suggestion.destination,
                    1 if suggestion.auto_apply_safe else 0,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def list_policies(self, status: str = None) -> list[dict]:
        """Возвращает список всех policies.

        Args:
            status: фильтр по статусу ('pending', 'approved', 'rejected')

        Returns:
            список словарей с данными policies
        """
        with sqlite3.connect(self.db_path) as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM policies WHERE status = ? ORDER BY created_at DESC",
                    (status,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM policies ORDER BY created_at DESC"
                ).fetchall()

        return [
            {
                "policy_id": r[0],
                "yaml_spec": json.loads(r[1]) if r[1] else {},
                "reason": r[2],
                "risk_score": r[3],
                "severity": r[4],
                "source": r[5],
                "destination": r[6],
                "auto_apply_safe": bool(r[7]),
                "status": r[8],
                "created_at": r[9],
                "updated_at": r[10],
            }
            for r in rows
        ]

    def get_policy(self, policy_id: str) -> dict | None:
        """Возвращает policy по ID."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM policies WHERE policy_id = ?", (policy_id,)
            ).fetchone()

        if not row:
            return None

        return {
            "policy_id": row[0],
            "yaml_spec": json.loads(row[1]) if row[1] else {},
            "reason": row[2],
            "risk_score": row[3],
            "severity": row[4],
            "source": row[5],
            "destination": row[6],
            "auto_apply_safe": bool(row[7]),
            "status": row[8],
            "created_at": row[9],
            "updated_at": row[10],
        }

    def update_status(self, policy_id: str, status: str) -> bool:
        """Обновляет статус policy.

        Args:
            policy_id: ID policy
            status: новый статус ('approved' или 'rejected')

        Returns:
            True если обновлено, False если policy не найдена
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE policies SET status = ?, updated_at = ? WHERE policy_id = ?",
                (status, datetime.now(timezone.utc).isoformat(), policy_id),
            )
            conn.commit()
            return cursor.rowcount > 0
