# collector/scheduler.py
# Фоновый процесс для автоматического создания снапшотов

import os
import time
import threading
from datetime import datetime, timezone, timedelta


class SnapshotScheduler:
    """Планировщик автоматических снапшотов."""

    def __init__(
        self,
        log_dir: str,
        storage,
        interval_hours: int = 1,
        max_snapshots: int = 168,  # 7 дней * 24 часа
    ):
        """
        Args:
            log_dir: директория с лог-файлами
            storage: экземпляр SnapshotStore для сохранения
            interval_hours: интервал создания снапшотов в часах
            max_snapshots: максимальное количество хранимых снапшотов
        """
        self.log_dir = log_dir
        self.storage = storage
        self.interval_hours = interval_hours
        self.max_snapshots = max_snapshots
        self.running = False
        self.thread = None

    def start(self):
        """Запускает фоновый процесс планировщика."""
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        print(f"📅 Scheduler started: snapshots every {self.interval_hours}h, max {self.max_snapshots}")

    def stop(self):
        """Останавливает фоновый процесс."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        print("🛑 Scheduler stopped")

    def _run_loop(self):
        """Основной цикл планировщика."""
        while self.running:
            try:
                self._create_snapshot()
                self._cleanup_old_snapshots()
            except Exception as e:
                print(f"❌ Scheduler error: {e}")

            # Ждем до следующего запуска
            time.sleep(self.interval_hours * 3600)

    def _create_snapshot(self):
        """Создает новый снапшот из логов за последний час."""
        from collector.auto_detect import parse_log_file
        from graph.builder import build_snapshot
        from collector.ingress_parser import filter_by_time_window

        print(f"📸 Creating snapshot at {datetime.now(timezone.utc)}")

        # Собираем все лог-файлы
        all_records = []
        for filename in os.listdir(self.log_dir):
            if filename.endswith((".log", ".csv", ".json")):
                filepath = os.path.join(self.log_dir, filename)
                try:
                    records = parse_log_file(filepath)
                    all_records.extend(records)
                except Exception as e:
                    print(f"⚠️  Failed to parse {filename}: {e}")

        if not all_records:
            print("⚠️  No records found, skipping snapshot")
            return

        # Определяем временное окно (последний час)
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=self.interval_hours)

        # Фильтруем записи по времени
        window_records = filter_by_time_window(all_records, start_time, end_time)

        if not window_records:
            print(f"⚠️  No records in time window {start_time} - {end_time}")
            return

        # Строим и сохраняем снапшот
        snapshot = build_snapshot(window_records, start_time, end_time)
        self.storage.save_snapshot(snapshot)

        print(f"✅ Snapshot created: {snapshot.snapshot_id[:12]}... "
              f"({len(snapshot.nodes)} nodes, {len(snapshot.edges)} edges)")

    def _cleanup_old_snapshots(self):
        """Удаляет старые снапшоты, оставляя только max_snapshots последних."""
        snapshots = self.storage.list_snapshots()

        if len(snapshots) <= self.max_snapshots:
            return

        # Сортируем по времени (старые первые)
        snapshots_sorted = sorted(snapshots, key=lambda s: s.get("timestamp_start", ""))

        # Удаляем старые
        to_delete = len(snapshots) - self.max_snapshots
        for i in range(to_delete):
            snapshot_id = snapshots_sorted[i]["snapshot_id"]
            try:
                self.storage.delete_snapshot(snapshot_id)
                print(f"🗑️  Deleted old snapshot: {snapshot_id[:12]}...")
            except Exception as e:
                print(f"⚠️  Failed to delete snapshot {snapshot_id}: {e}")


if __name__ == "__main__":
    # Тест scheduler
    import tempfile
    import shutil
    from graph.storage import SnapshotStore

    test_dir = tempfile.mkdtemp()
    test_db = os.path.join(test_dir, "test.db")

    # Создаем тестовые данные
    test_log = os.path.join(test_dir, "test.csv")
    with open(test_log, "w") as f:
        f.write("timestamp,source_service,destination_service,http_method,path,status_code,latency_ms\n")
        f.write(f"{datetime.now(timezone.utc).isoformat()}Z,api,user-svc,GET,/api,200,45.0\n")

    store = SnapshotStore(test_db)
    scheduler = SnapshotScheduler(test_dir, store, interval_hours=1, max_snapshots=5)

    # Создаем один снапшот вручную для теста
    scheduler._create_snapshot()

    snapshots = store.list_snapshots()
    if len(snapshots) > 0:
        print(f"✅ Scheduler test passed: {len(snapshots)} snapshot(s) created")
    else:
        print("❌ Scheduler test failed")

    # Очистка
    shutil.rmtree(test_dir)
