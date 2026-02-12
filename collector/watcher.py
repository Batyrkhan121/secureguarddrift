# collector/watcher.py
# Мониторинг директории с логами и обработка новых файлов

import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class LogFileHandler(FileSystemEventHandler):
    """Обработчик событий файловой системы для лог-файлов."""

    def __init__(self, callback):
        """
        Args:
            callback: функция, вызываемая при появлении нового файла.
                      Сигнатура: callback(filepath: str) -> None
        """
        self.callback = callback
        self.processed_files = set()

    def on_created(self, event):
        """Вызывается при создании нового файла."""
        if event.is_directory:
            return

        filepath = event.src_path
        if filepath.endswith((".log", ".csv", ".json")):
            if filepath not in self.processed_files:
                self.processed_files.add(filepath)
                self.callback(filepath)

    def on_modified(self, event):
        """Вызывается при изменении файла (для tail-режима)."""
        if event.is_directory:
            return

        filepath = event.src_path
        if filepath.endswith((".log", ".csv", ".json")):
            # Для растущих файлов можно добавить tail-логику
            # Пока просто игнорируем
            pass


class LogWatcher:
    """Наблюдатель за директорией с логами."""

    def __init__(self, watch_dir: str, callback):
        """
        Args:
            watch_dir: путь к директории для мониторинга
            callback: функция обработки нового файла
        """
        self.watch_dir = watch_dir
        self.callback = callback
        self.observer = None
        self.handler = LogFileHandler(callback)

    def start(self):
        """Запускает мониторинг директории."""
        if not os.path.exists(self.watch_dir):
            os.makedirs(self.watch_dir, exist_ok=True)

        self.observer = Observer()
        self.observer.schedule(self.handler, self.watch_dir, recursive=False)
        self.observer.start()
        print(f"🔍 Watching directory: {self.watch_dir}")

    def stop(self):
        """Останавливает мониторинг."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            print("🛑 Watcher stopped")

    def process_existing_files(self):
        """Обрабатывает существующие файлы в директории."""
        for filename in os.listdir(self.watch_dir):
            if filename.endswith((".log", ".csv", ".json")):
                filepath = os.path.join(self.watch_dir, filename)
                if filepath not in self.handler.processed_files:
                    self.handler.processed_files.add(filepath)
                    self.callback(filepath)


def tail_file(filepath: str, callback, poll_interval: float = 1.0):
    """Следит за растущим файлом (tail -f режим).

    Args:
        filepath: путь к файлу
        callback: функция для обработки новых строк, сигнатура: callback(line: str) -> None
        poll_interval: интервал опроса в секундах
    """
    with open(filepath, "r", encoding="utf-8") as f:
        # Переходим в конец файла
        f.seek(0, os.SEEK_END)

        while True:
            line = f.readline()
            if line:
                callback(line.strip())
            else:
                # Нет новых строк, ждем
                time.sleep(poll_interval)


if __name__ == "__main__":
    # Тест watcher
    import tempfile
    import shutil

    test_dir = tempfile.mkdtemp()
    print(f"Test directory: {test_dir}")

    processed_files = []

    def test_callback(filepath: str):
        print(f"✅ New file detected: {filepath}")
        processed_files.append(filepath)

    watcher = LogWatcher(test_dir, test_callback)
    watcher.start()

    # Создаем тестовый файл
    time.sleep(1)
    test_file = os.path.join(test_dir, "test.log")
    with open(test_file, "w") as f:
        f.write("test log line\n")

    # Ждем обработки
    time.sleep(2)
    watcher.stop()

    # Проверка
    if len(processed_files) > 0:
        print(f"✅ Watcher test passed: {len(processed_files)} file(s) processed")
    else:
        print("❌ Watcher test failed")

    # Очистка
    shutil.rmtree(test_dir)
