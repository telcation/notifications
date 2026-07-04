"""reminders.json の読み書きを行う共通モジュール。

reminder_manager.py(CLI)、send_reminder.py(cron送信)、reminder_web.py(Web GUI)
すべてがこのモジュールを経由してデータを読み書きすることで、スキーマの不整合を防ぐ。
"""
import json
import uuid
from pathlib import Path

REMINDERS_PATH = Path(__file__).parent / "reminders.json"

REPEAT_CHOICES = ["none", "daily", "monthly", "yearly"]
REPEAT_LABELS = {"none": "1回のみ", "daily": "毎日", "monthly": "毎月", "yearly": "毎年"}


def load_reminders() -> list:
    if not REMINDERS_PATH.exists():
        return []
    with open(REMINDERS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_reminders(reminders: list) -> None:
    with open(REMINDERS_PATH, "w", encoding="utf-8") as f:
        json.dump(reminders, f, ensure_ascii=False, indent=2)


def new_id() -> str:
    return uuid.uuid4().hex[:8]


def find_reminder(reminders: list, reminder_id: str) -> dict | None:
    for r in reminders:
        if r["id"] == reminder_id:
            return r
    return None
