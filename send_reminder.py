"""cron から毎分実行し、通知日時・繰り返し種別が一致する有効なリマインダーをLINEへ送信する。

reminders.json のスキーマ:
{
  "id": "abc12345",
  "message": "件名",
  "notify_datetime": "2026-08-01T09:00",   # 通知の基準日時(初回・繰り返しの起点)
  "repeat": "none" | "daily" | "monthly" | "yearly",
  "enabled": true,
  "last_sent_period": null   # 直近送信した「期間キー」。同一期間内の重複送信を防止する
}

repeatごとの期間キーと一致条件:
- none    : 期間キー=YYYY-MM-DD。notify_datetimeの日付と一致する日のみ送信し、送信後enabled=falseにする
- daily   : 期間キー=YYYY-MM-DD。notify_datetimeの日付以降、毎日その時刻に送信
- monthly : 期間キー=YYYY-MM。notify_datetimeの「日」と一致する日に送信(存在しない月はスキップ)
- yearly  : 期間キー=YYYY。notify_datetimeの「月日」と一致する日に送信

crontab 例(毎分実行):
  * * * * * cd /path/to/notifications && venv/bin/python send_reminder.py >> send_reminder.log 2>&1
"""
import sys
from datetime import datetime

from line_utils import send_line_message
from reminders_store import load_reminders, save_reminders


def compute_match(now: datetime, notify_dt: datetime, repeat: str):
    """(一致するか, 期間キー) を返す"""
    if now.strftime("%H:%M") != notify_dt.strftime("%H:%M"):
        return False, None
    if now.date() < notify_dt.date():
        return False, None

    if repeat == "none":
        period_key = notify_dt.date().isoformat()
        return now.date() == notify_dt.date(), period_key

    if repeat == "daily":
        period_key = now.date().isoformat()
        return True, period_key

    if repeat == "monthly":
        period_key = now.strftime("%Y-%m")
        return now.day == notify_dt.day, period_key

    if repeat == "yearly":
        period_key = str(now.year)
        return (now.month == notify_dt.month and now.day == notify_dt.day), period_key

    return False, None


def main() -> None:
    now = datetime.now()
    reminders = load_reminders()
    changed = False

    for r in reminders:
        if not r.get("enabled"):
            continue

        try:
            notify_dt = datetime.fromisoformat(r["notify_datetime"])
        except (KeyError, ValueError):
            print(f"[{now.isoformat(timespec='seconds')}] notify_datetime不正のためスキップ: id={r.get('id')}", file=sys.stderr)
            continue

        repeat = r.get("repeat", "none")
        matched, period_key = compute_match(now, notify_dt, repeat)
        if not matched:
            continue
        if period_key is not None and r.get("last_sent_period") == period_key:
            # 同一期間内の重複実行(cronの多重起動等)対策
            continue

        try:
            send_line_message(r["message"])
            r["last_sent_period"] = period_key
            if repeat == "none":
                r["enabled"] = False  # 1回のみの通知は送信後に自動でOFF
            changed = True
            print(f"[{now.isoformat(timespec='seconds')}] 送信成功: id={r['id']} message={r['message']}")
        except Exception as e:
            print(f"[{now.isoformat(timespec='seconds')}] 送信失敗: id={r['id']} error={e}", file=sys.stderr)

    if changed:
        save_reminders(reminders)


if __name__ == "__main__":
    main()
