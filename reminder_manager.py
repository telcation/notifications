"""リマインダー管理CLI(n日ごと/nヶ月ごと/n年ごと対応)

GUI(reminder_web.py)がメインの操作手段ですが、SSH経由で素早く操作したい場合用に
CLIも残しています。データは reminders.json を共有しているため、
どちらで操作しても矛盾なく反映されます。

使い方:
  python reminder_manager.py add --message "件名" --datetime "2026-08-01T09:00" --repeat-unit month --repeat-interval 2 [--id remind1]
  python reminder_manager.py list
  python reminder_manager.py enable <id>
  python reminder_manager.py disable <id>
  python reminder_manager.py remove <id>

--repeat-unit: none(1回のみ) / day(n日ごと) / month(nヶ月ごと) / year(n年ごと)
--repeat-interval: n(整数、--repeat-unitがnoneの場合は無視される。省略時は1)

【スヌーズの仕様】指定日時になったら通知を開始し、スヌーズ停止(disable)するまで
毎日同時刻に通知し続ける。month/yearはスヌーズ停止しても、次の周期(nヶ月後・n年後の
指定日)になると自動的に再開する。day(interval=1、旧・毎日)とnoneは自動再開せず、
停止したらそのまま止まる。dayでinterval>1の場合はmonth/yearと同様に自動再開する。
"""
import argparse
import sys
from datetime import datetime

from reminders_store import (
    load_reminders,
    save_reminders,
    new_id,
    find_reminder,
    format_repeat_label,
    REPEAT_UNIT_CHOICES,
)


def validate_datetime(value: str) -> str:
    try:
        datetime.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"日時は YYYY-MM-DDTHH:MM 形式で指定してください(例: 2026-08-01T09:00): {value}"
        )
    return value


def cmd_add(args: argparse.Namespace) -> None:
    reminders = load_reminders()
    reminder_id = args.id or new_id()

    if find_reminder(reminders, reminder_id):
        print(f"エラー: id '{reminder_id}' は既に使用されています。", file=sys.stderr)
        sys.exit(1)

    reminders.append({
        "id": reminder_id,
        "message": args.message,
        "notify_datetime": args.datetime,
        "repeat_unit": args.repeat_unit,
        "repeat_interval": args.repeat_interval,
        "enabled": True,
        "cycle_start": None,
    })
    save_reminders(reminders)
    label = format_repeat_label(args.repeat_unit, args.repeat_interval)
    print(f"追加しました: id={reminder_id} datetime={args.datetime} repeat={label}")


def cmd_list(args: argparse.Namespace) -> None:
    reminders = load_reminders()
    if not reminders:
        print("リマインダーは登録されていません。")
        return
    for r in reminders:
        status = "ON " if r["enabled"] else "OFF"
        repeat_label = format_repeat_label(r.get("repeat_unit", "none"), r.get("repeat_interval", 1))
        print(f"[{status}] id={r['id']:<10} {r['notify_datetime']} ({repeat_label})  "
              f"cycle_start={r.get('cycle_start')}  message={r['message']}")


def _find_or_exit(reminders: list, reminder_id: str) -> dict:
    r = find_reminder(reminders, reminder_id)
    if r is None:
        print(f"エラー: id '{reminder_id}' が見つかりません。", file=sys.stderr)
        sys.exit(1)
    return r


def cmd_enable(args: argparse.Namespace) -> None:
    reminders = load_reminders()
    r = _find_or_exit(reminders, args.id)
    r["enabled"] = True
    save_reminders(reminders)
    print(f"id={args.id} を有効化しました。")


def cmd_disable(args: argparse.Namespace) -> None:
    reminders = load_reminders()
    r = _find_or_exit(reminders, args.id)
    r["enabled"] = False
    save_reminders(reminders)
    print(f"id={args.id} を無効化しました。")


def cmd_remove(args: argparse.Namespace) -> None:
    reminders = load_reminders()
    _find_or_exit(reminders, args.id)
    reminders = [r for r in reminders if r["id"] != args.id]
    save_reminders(reminders)
    print(f"id={args.id} を削除しました。")


def main() -> None:
    parser = argparse.ArgumentParser(description="LINEリマインダー管理CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="リマインダーを追加")
    p_add.add_argument("--message", required=True, help="件名")
    p_add.add_argument("--datetime", required=True, type=validate_datetime,
                        help="通知日時 YYYY-MM-DDTHH:MM")
    p_add.add_argument("--repeat-unit", required=True, choices=REPEAT_UNIT_CHOICES,
                        help="繰り返し単位: none/day/month/year")
    p_add.add_argument("--repeat-interval", type=int, default=1,
                        help="繰り返し間隔n(--repeat-unitがnoneの場合は無視。省略時は1)")
    p_add.add_argument("--id", help="任意のID(省略時は自動採番)")
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="一覧表示")
    p_list.set_defaults(func=cmd_list)

    p_enable = sub.add_parser("enable", help="有効化")
    p_enable.add_argument("id")
    p_enable.set_defaults(func=cmd_enable)

    p_disable = sub.add_parser("disable", help="無効化(スヌーズ停止)")
    p_disable.add_argument("id")
    p_disable.set_defaults(func=cmd_disable)

    p_remove = sub.add_parser("remove", help="削除")
    p_remove.add_argument("id")
    p_remove.set_defaults(func=cmd_remove)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
