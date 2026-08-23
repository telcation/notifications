"""reminders.json の読み書きを行う共通モジュール。

reminder_manager.py(CLI)、send_reminder.py(cron送信)、reminder_web.py(Web GUI)
すべてがこのモジュールを経由してデータを読み書きすることで、スキーマの不整合を防ぐ。

【繰り返しの指定方法】
repeat_unit(単位)と repeat_interval(間隔)の組み合わせで指定する。
- repeat_unit: "none"(1回のみ) / "day"(n日ごと) / "month"(nヶ月ごと) / "year"(n年ごと)
- repeat_interval: 整数(n)。repeat_unit が "none" の場合は無視される。
例: 3日ごと → unit="day", interval=3 / 毎月(旧仕様の「毎月」相当) → unit="month", interval=1
"""
import json
import uuid
from pathlib import Path

REMINDERS_PATH = Path(__file__).parent / "reminders.json"

REPEAT_UNIT_CHOICES = ["none", "day", "month", "year"]
REPEAT_UNIT_LABELS = {"none": "1回のみ", "day": "日ごと", "month": "ヶ月ごと", "year": "年ごと"}

# 旧スキーマ(repeat: "none"/"daily"/"monthly"/"yearly")からの自動移行マップ
_LEGACY_REPEAT_MAP = {
    "none": ("none", 1),
    "daily": ("day", 1),
    "monthly": ("month", 1),
    "yearly": ("year", 1),
}


def format_repeat_label(repeat_unit: str, repeat_interval: int) -> str:
    """一覧表示用のラベルを生成する(例: '3日ごと', '1回のみ')"""
    if repeat_unit == "none":
        return "1回のみ"
    return f"{repeat_interval}{REPEAT_UNIT_LABELS.get(repeat_unit, repeat_unit)}"


def _migrate_reminder(r: dict) -> dict:
    """旧スキーマのリマインダーを新スキーマ(repeat_unit/repeat_interval)へ変換する。
    既に新スキーマの場合は何もしない。in-placeで変更しつつ、そのdictを返す。
    """
    if "repeat_unit" not in r:
        legacy_repeat = r.get("repeat", "none")
        unit, interval = _LEGACY_REPEAT_MAP.get(legacy_repeat, ("none", 1))
        r["repeat_unit"] = unit
        r["repeat_interval"] = interval
    r.setdefault("repeat_interval", 1)
    r.setdefault("enabled", True)
    r.setdefault("cycle_start", None)
    r.setdefault("active", True)
    return r


def load_reminders() -> list:
    if not REMINDERS_PATH.exists():
        return []
    with open(REMINDERS_PATH, "r", encoding="utf-8") as f:
        reminders = json.load(f)
    return [_migrate_reminder(r) for r in reminders]


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
