# ml/whitelist.py
"""Whitelist and suppress rules для reducing false positives."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class WhitelistEntry:
    """Whitelist entry для edge."""

    entry_id: Optional[int]
    source: str
    destination: str
    reason: str
    created_at: datetime
    created_by: Optional[str] = None


@dataclass
class SuppressRule:
    """Suppress rule для временного игнорирования событий."""

    rule_id: Optional[int]
    event_type: str
    service_pattern: str  # glob pattern для service name
    reason: str
    expires_at: datetime
    created_at: datetime
    created_by: Optional[str] = None


class WhitelistStore:
    """SQLite хранилище для whitelist и suppress rules."""

    def __init__(self, db_path: str = "data/drift.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Создает таблицы если не существуют."""
        conn = sqlite3.connect(self.db_path)

        # Whitelist таблица
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS whitelist (
                entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                destination TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_by TEXT,
                created_at TIMESTAMP NOT NULL,
                UNIQUE(source, destination)
            )
        """
        )

        # Suppress rules таблица
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS suppress_rules (
                rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                service_pattern TEXT NOT NULL,
                reason TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_by TEXT,
                created_at TIMESTAMP NOT NULL
            )
        """
        )

        conn.commit()
        conn.close()

    def add_to_whitelist(self, entry: WhitelistEntry) -> int:
        """Добавляет edge в whitelist.

        Returns:
            entry_id
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                """
                INSERT INTO whitelist (source, destination, reason, created_by, created_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                (entry.source, entry.destination, entry.reason, entry.created_by, entry.created_at.isoformat()),
            )
            entry_id = cursor.lastrowid
            conn.commit()
        except sqlite3.IntegrityError:
            # Уже существует
            entry_id = conn.execute(
                "SELECT entry_id FROM whitelist WHERE source = ? AND destination = ?",
                (entry.source, entry.destination),
            ).fetchone()[0]
        finally:
            conn.close()

        return entry_id

    def is_whitelisted(self, edge_key: tuple[str, str]) -> bool:
        """Проверяет есть ли edge в whitelist.

        Args:
            edge_key: (source, destination)

        Returns:
            True если whitelisted
        """
        conn = sqlite3.connect(self.db_path)
        count = conn.execute(
            "SELECT COUNT(*) FROM whitelist WHERE source = ? AND destination = ?", edge_key
        ).fetchone()[0]
        conn.close()
        return count > 0

    def remove_from_whitelist(self, edge_key: tuple[str, str]) -> bool:
        """Удаляет edge из whitelist.

        Returns:
            True если удалено
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("DELETE FROM whitelist WHERE source = ? AND destination = ?", edge_key)
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    def list_whitelist(self) -> list[WhitelistEntry]:
        """Возвращает весь whitelist."""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("SELECT * FROM whitelist ORDER BY created_at DESC").fetchall()
        conn.close()

        return [
            WhitelistEntry(
                entry_id=row[0],
                source=row[1],
                destination=row[2],
                reason=row[3],
                created_by=row[4],
                created_at=datetime.fromisoformat(row[5]),
            )
            for row in rows
        ]

    def add_suppress_rule(self, rule: SuppressRule) -> int:
        """Добавляет suppress rule."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            """
            INSERT INTO suppress_rules (event_type, service_pattern, reason, expires_at, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                rule.event_type,
                rule.service_pattern,
                rule.reason,
                rule.expires_at.isoformat(),
                rule.created_by,
                rule.created_at.isoformat(),
            ),
        )
        rule_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return rule_id


if __name__ == "__main__":
    store = WhitelistStore("data/test_whitelist.db")

    # Добавляем в whitelist
    entry = WhitelistEntry(
        entry_id=None,
        source="svc-a",
        destination="svc-b",
        reason="Known safe connection",
        created_at=datetime.utcnow(),
    )

    entry_id = store.add_to_whitelist(entry)
    print(f"Added to whitelist: {entry_id}")

    # Проверяем whitelist
    is_wl = store.is_whitelisted(("svc-a", "svc-b"))
    print(f"Is whitelisted: {is_wl}")

    # Список whitelist
    entries = store.list_whitelist()
    print(f"Whitelist entries: {len(entries)}")
