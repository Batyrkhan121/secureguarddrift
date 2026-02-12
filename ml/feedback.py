# ml/feedback.py
"""Feedback loop для обучения на user feedback."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional


@dataclass
class FeedbackRecord:
    """Запись user feedback."""

    feedback_id: Optional[int]
    event_id: str
    edge_key: tuple[str, str]
    event_type: str
    verdict: Literal["true_positive", "false_positive", "expected"]
    comment: Optional[str]
    created_at: datetime
    user: Optional[str] = None


class FeedbackStore:
    """SQLite хранилище для feedback."""

    def __init__(self, db_path: str = "data/drift.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Создает таблицу feedback если не существует."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback (
                feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                source TEXT NOT NULL,
                destination TEXT NOT NULL,
                event_type TEXT NOT NULL,
                verdict TEXT NOT NULL,
                comment TEXT,
                user TEXT,
                created_at TIMESTAMP NOT NULL
            )
        """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_edge ON feedback(source, destination)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_verdict ON feedback(verdict)")
        conn.commit()
        conn.close()

    def save_feedback(self, feedback: FeedbackRecord) -> int:
        """Сохраняет feedback record.

        Returns:
            feedback_id
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            """
            INSERT INTO feedback (event_id, source, destination, event_type, verdict, comment, user, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                feedback.event_id,
                feedback.edge_key[0],
                feedback.edge_key[1],
                feedback.event_type,
                feedback.verdict,
                feedback.comment,
                feedback.user,
                feedback.created_at.isoformat(),
            ),
        )
        feedback_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return feedback_id

    def get_feedback_for_edge(
        self, edge_key: tuple[str, str], event_type: Optional[str] = None
    ) -> list[FeedbackRecord]:
        """Получает все feedback для edge.

        Args:
            edge_key: (source, destination)
            event_type: фильтр по event_type (опционально)

        Returns:
            Список FeedbackRecord
        """
        conn = sqlite3.connect(self.db_path)
        if event_type:
            query = "SELECT * FROM feedback WHERE source = ? AND destination = ? AND event_type = ? ORDER BY created_at DESC"
            rows = conn.execute(query, (edge_key[0], edge_key[1], event_type)).fetchall()
        else:
            query = "SELECT * FROM feedback WHERE source = ? AND destination = ? ORDER BY created_at DESC"
            rows = conn.execute(query, (edge_key[0], edge_key[1])).fetchall()

        conn.close()

        records = []
        for row in rows:
            records.append(
                FeedbackRecord(
                    feedback_id=row[0],
                    event_id=row[1],
                    edge_key=(row[2], row[3]),
                    event_type=row[4],
                    verdict=row[5],
                    comment=row[6],
                    user=row[7],
                    created_at=datetime.fromisoformat(row[8]),
                )
            )
        return records

    def get_false_positive_pattern(self, event_type: str) -> float:
        """Вычисляет процент false positives для event_type.

        Args:
            event_type: тип события

        Returns:
            Доля false positives (0.0 - 1.0)
        """
        conn = sqlite3.connect(self.db_path)
        total = conn.execute("SELECT COUNT(*) FROM feedback WHERE event_type = ?", (event_type,)).fetchone()[0]
        if total == 0:
            conn.close()
            return 0.0

        fp_count = conn.execute(
            "SELECT COUNT(*) FROM feedback WHERE event_type = ? AND verdict = 'false_positive'", (event_type,)
        ).fetchone()[0]
        conn.close()

        return fp_count / total


def calculate_feedback_modifier(
    edge_key: tuple[str, str], event_type: str, feedback_store: FeedbackStore
) -> int:
    """Вычисляет модификатор на основе feedback history.

    Args:
        edge_key: (source, destination)
        event_type: тип события
        feedback_store: хранилище feedback

    Returns:
        Модификатор для score (-40 до 0)
    """
    feedbacks = feedback_store.get_feedback_for_edge(edge_key, event_type)

    if not feedbacks:
        return 0

    # Берем последний feedback
    latest = feedbacks[0]

    if latest.verdict == "false_positive":
        return -40  # Сильно снижаем score
    elif latest.verdict == "expected":
        return -30  # Снижаем score
    else:  # true_positive
        return 0  # Не меняем


if __name__ == "__main__":
    store = FeedbackStore("data/test_feedback.db")

    # Создаем тестовый feedback
    feedback = FeedbackRecord(
        feedback_id=None,
        event_id="test-123",
        edge_key=("svc-a", "svc-b"),
        event_type="new_edge",
        verdict="false_positive",
        comment="This is expected deployment",
        created_at=datetime.utcnow(),
    )

    feedback_id = store.save_feedback(feedback)
    print(f"Saved feedback: {feedback_id}")

    # Получаем feedback
    feedbacks = store.get_feedback_for_edge(("svc-a", "svc-b"))
    print(f"Found {len(feedbacks)} feedbacks for edge")

    # Вычисляем модификатор
    modifier = calculate_feedback_modifier(("svc-a", "svc-b"), "new_edge", store)
    print(f"Feedback modifier: {modifier}")
