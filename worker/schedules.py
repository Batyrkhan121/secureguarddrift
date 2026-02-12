# worker/schedules.py
# Celery Beat periodic task schedules

from celery.schedules import crontab

from worker.app import celery_app

celery_app.conf.beat_schedule = {
    "build-hourly-snapshot": {
        "task": "worker.tasks.snapshot.build_snapshot_task",
        "schedule": crontab(minute=0),
        "args": ("default", "/var/log/secureguard/access.log"),
    },
    "cleanup-old-data": {
        "task": "worker.tasks.snapshot.build_snapshot_task",
        "schedule": crontab(hour=3, minute=0),
        "args": ("default", "cleanup"),
        "options": {"queue": "maintenance"},
    },
    "update-baselines": {
        "task": "worker.tasks.drift.detect_drift_task",
        "schedule": crontab(minute="*/30"),
        "args": ("default", "latest"),
    },
}
