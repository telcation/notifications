"""cron から毎分実行し、条件が一致する有効なリマインダーをLINEへ送信する。

reminders.json のスキーマ:
{
  "id": "abc12345",
  "message": "件名",
  "notify_datetime": "2026-08-01T09:00",   # 通知の基準日時(初回・繰り返しの起点となる日時)
  "repeat_unit": "none" | "day" | "month" | "year",
  "repeat_interval": 1,      # n。repeat_unitが"none"の場合は無視される
  "enabled": true,           # 「スヌーズ停止」ボタンで切り替わる。trueの間は毎日通知する
  "cycle_start": null        # 現在の周期の開始日(YYYY-MM-DD)。周期の切り替わり検出に使う
}

【スヌーズの仕様】
- 指定日時になったら通知を開始し、以降は enabled が true である限り「毎日」同時刻に通知し続ける。
  周期の間隔(n)の値に関わらず、1回鳴らしたら黙る仕様ではない。
- 「スヌーズ停止」(enabled=false)にすると、その時点で通知が止まる。
- 次の周期の境界日(n日後・nヶ月後・n年後)が来ると、自動的に enabled が true に戻り、
  また毎日の通知が始まる(自動再開)。
  ただし repeat_unit="day" かつ repeat_interval=1(=旧仕様の「毎日」相当)の場合のみ例外で、
  自動再開しない(元々「無効にするまで鳴り続け、無効にしたらそのまま」という仕様のため)。
- repeat_unit="none"(1回のみ)は次の周期が存在しないため、無効にしたらそのまま。
- month/yearで、その月/年に該当する日が存在しない場合(例: 31日指定で2月)は、
  その周期の境界がスキップされる。

crontab 例(毎分実行):
  * * * * * cd /path/to/notifications && venv/bin/python send_reminder.py >> send_reminder.log 2>&1
"""
import sys
from datetime import date, datetime

from line_utils import send_line_message
from reminders_store import load_reminders, save_reminders


def compute_action(now: datetime, notify_dt: datetime, repeat_unit: str, repeat_interval: int,
                    enabled: bool, cycle_start_str: str | None):
    """この瞬間に送信すべきか判定し、更新後の enabled / cycle_start を返す。

    戻り値: (should_fire, new_enabled, new_cycle_start_str)
    """
    if now.strftime("%H:%M") != notify_dt.strftime("%H:%M"):
        return False, enabled, cycle_start_str
    if now.date() < notify_dt.date():
        return False, enabled, cycle_start_str

    cycle_start = date.fromisoformat(cycle_start_str) if cycle_start_str else None
    interval = max(1, repeat_interval or 1)

    if repeat_unit == "none":
        # 次の周期が存在しない。無効にしたらそのまま。
        if cycle_start is None:
            cycle_start = notify_dt.date()
        return enabled, enabled, cycle_start.isoformat()

    auto_rearm = True
    if repeat_unit == "day":
        days_since = (now.date() - notify_dt.date()).days
        is_new_cycle_today = (days_since % interval == 0)
        # 「1日ごと」(旧・毎日)は自動再開しない = 無効にしたらそのまま止まる
        auto_rearm = interval > 1
    elif repeat_unit == "month":
        diff_months = (now.year - notify_dt.year) * 12 + (now.month - notify_dt.month)
        is_new_cycle_today = (diff_months >= 0 and diff_months % interval == 0
                               and now.day == notify_dt.day)
    elif repeat_unit == "year":
        diff_years = now.year - notify_dt.year
        is_new_cycle_today = (diff_years >= 0 and diff_years % interval == 0
                               and now.month == notify_dt.month and now.day == notify_dt.day)
    else:
        return False, enabled, cycle_start_str

    new_enabled = enabled
    new_cycle_start = cycle_start

    if is_new_cycle_today and cycle_start != now.date():
        new_cycle_start = now.date()
        if auto_rearm:
            # 新しい周期の初日 → 過去にスヌーズ停止していても自動的に再有効化する
            new_enabled = True

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

        repeat_unit = r.get("repeat_unit", "none")
        repeat_interval = r.get("repeat_interval", 1)
        enabled = r.get("enabled", False)
        cycle_start_str = r.get("cycle_start")

        should_fire, new_enabled, new_cycle_start = compute_action(
            now, notify_dt, repeat_unit, repeat_interval, enabled, cycle_start_str
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
