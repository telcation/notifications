"""cron から毎分実行し、条件が一致する有効なリマインダーをLINEへ送信する。

reminders.json のスキーマ:
{
  "id": "abc12345",
  "message": "件名",
  "notify_datetime": "2026-08-01T09:00",   # 通知の基準日時(初回・繰り返しの起点となる日時)
  "repeat": "none" | "daily" | "monthly" | "yearly",
  "enabled": true,          # 「スヌーズ停止」ボタンで切り替わる。trueの間は毎日通知する
  "cycle_start": null       # 現在の周期の開始日(YYYY-MM-DD)。周期の切り替わり検出に使う
}

【スヌーズの仕様】
- 指定日時になったら通知を開始し、以降は enabled が true である限り「毎日」同時刻に通知し続ける。
  1回鳴らしたら黙る、という仕様ではない(スヌーズ停止を押すまで翌日以降も継続する)。
- 「スヌーズ停止」(enabled=false)にすると、その時点で通知が止まる。
- repeatが monthly / yearly の場合、次の周期(来月・来年の指定日)が来ると、
  過去にスヌーズ停止していても自動的に enabled が true に戻り、また毎日の通知が始まる
  (「無効にしても次周期には自動再開してほしい」という仕様のため)。
- repeatが daily / none の場合は自動再開の概念が無いため、スヌーズ停止したらそのまま止まる
  (dailyはそもそも周期の区切りが無く常時鳴り続ける仕様、noneは次の周期が存在しないため)。
- monthlyで31日など、その月に存在しない日を指定している場合、その月は周期の切り替わりが
  発生しない(スキップされる)。

crontab 例(毎分実行):
  * * * * * cd /path/to/notifications && venv/bin/python send_reminder.py >> send_reminder.log 2>&1
"""
import sys
from datetime import date, datetime

from line_utils import send_line_message
from reminders_store import load_reminders, save_reminders


def compute_action(now: datetime, notify_dt: datetime, repeat: str,
                    enabled: bool, cycle_start_str: str | None):
    """この瞬間に送信すべきか判定し、更新後の enabled / cycle_start を返す。

    戻り値: (should_fire, new_enabled, new_cycle_start_str)
    """
    if now.strftime("%H:%M") != notify_dt.strftime("%H:%M"):
        return False, enabled, cycle_start_str
    if now.date() < notify_dt.date():
        return False, enabled, cycle_start_str

    cycle_start = date.fromisoformat(cycle_start_str) if cycle_start_str else None

    if repeat == "none":
        # 次の周期が存在しない。無効にしたらそのまま。
        if cycle_start is None:
            cycle_start = notify_dt.date()
        should_fire = enabled
        return should_fire, enabled, cycle_start.isoformat()

    if repeat == "daily":
        # 常時鳴り続ける仕様(自動再開の概念は無い)。無効にしたらそのまま。
        return enabled, enabled, now.date().isoformat()

    if repeat == "monthly":
        is_new_cycle_today = (now.day == notify_dt.day)
    elif repeat == "yearly":
        is_new_cycle_today = (now.month == notify_dt.month and now.day == notify_dt.day)
    else:
        return False, enabled, cycle_start_str

    new_enabled = enabled
    new_cycle_start = cycle_start

    if is_new_cycle_today and cycle_start != now.date():
        # 新しい周期の初日 → 過去にスヌーズ停止していても自動的に再有効化する
        new_enabled = True
        new_cycle_start = now.date()

    return new_enabled, new_enabled, new_cycle_start.isoformat() if new_cycle_start else None


def main() -> None:
    now = datetime.now()
    reminders = load_reminders()
    changed = False

    for r in reminders:
        try:
            notify_dt = datetime.fromisoformat(r["notify_datetime"])
        except (KeyError, ValueError):
            print(f"[{now.isoformat(timespec='seconds')}] notify_datetime不正のためスキップ: id={r.get('id')}", file=sys.stderr)
            continue

        repeat = r.get("repeat", "none")
        enabled = r.get("enabled", False)
        cycle_start_str = r.get("cycle_start")

        should_fire, new_enabled, new_cycle_start = compute_action(
            now, notify_dt, repeat, enabled, cycle_start_str
        )

        if new_enabled != enabled or new_cycle_start != cycle_start_str:
            r["enabled"] = new_enabled
            r["cycle_start"] = new_cycle_start
            changed = True
            if new_enabled and not enabled:
                print(f"[{now.isoformat(timespec='seconds')}] 次周期の到来により自動再開: id={r['id']} message={r['message']}")

        if not should_fire:
            continue

        try:
            send_line_message(r["message"])
            r["last_sent_at"] = now.isoformat(timespec="seconds")
            changed = True
            print(f"[{now.isoformat(timespec='seconds')}] 送信成功: id={r['id']} message={r['message']}")
        except Exception as e:
            print(f"[{now.isoformat(timespec='seconds')}] 送信失敗: id={r['id']} error={e}", file=sys.stderr)

    if changed:
        save_reminders(reminders)


if __name__ == "__main__":
    main()
