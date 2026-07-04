"""毎朝8:00にcronで実行し、本日のGoogleカレンダー予定をLINE通知する。

既存の calendar_print_sa.py と同じサービスアカウント(service_account.json)、
カレンダーIDをそのまま流用する。印刷は行わず、LINEへのテキスト通知のみ行う。

crontab 例(毎朝8:00):
  0 8 * * * cd /path/to/notifications && /path/to/venv/bin/python calendar_notify.py >> calendar_notify.log 2>&1
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build

from line_utils import send_line_message

CONFIG_PATH = Path(__file__).parent / "calendar_config.json"
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
JST = timezone(timedelta(hours=9))
WEEKDAY_NAMES = ["月", "火", "水", "木", "金", "土", "日"]


def load_calendar_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"{CONFIG_PATH} が見つかりません。calendar_config.json.example をコピーし、"
            "service_account_file・カレンダーIDを設定してください。"
        )
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_service(service_account_file: str):
    # service_account.json はこのファイルからの相対パス、または絶対パスで指定する
    sa_path = Path(__file__).parent / service_account_file
    if not sa_path.exists():
        sa_path = Path(service_account_file)
    creds = service_account.Credentials.from_service_account_file(
        str(sa_path), scopes=SCOPES
    )
    return build("calendar", "v3", credentials=creds)


def fetch_today_events(service, calendar_id: str, day_start: datetime, day_end: datetime) -> list:
    result = service.events().list(
        calendarId=calendar_id,
        timeMin=day_start.isoformat(),
        timeMax=day_end.isoformat(),
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    return result.get("items", [])


def format_event_line(event: dict) -> str:
    start = event.get("start", {})
    if "dateTime" in start:
        dt = datetime.fromisoformat(start["dateTime"])
        time_str = dt.astimezone(JST).strftime("%H:%M")
    else:
        time_str = "終日"
    summary = event.get("summary", "(タイトルなし)")
    return f"　{time_str}  {summary}"


def build_message(sections: list) -> str:
    today = datetime.now(JST)
    weekday = WEEKDAY_NAMES[today.weekday()]
    lines = [f"\U0001F4C5 {today.month}月{today.day}日({weekday})の予定"]

    for label, events in sections:
        lines.append("")
        lines.append(f"【{label}】")
        if not events:
            lines.append("　予定なし")
        else:
            for ev in events:
                lines.append(format_event_line(ev))

    return "\n".join(lines)


def main() -> None:
    config = load_calendar_config()
    service = get_service(config["service_account_file"])

    today_start = datetime.now(JST).replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    sections = []
    for label, key in [("自分", "my_calendar_id"), ("妻", "wife_calendar_id")]:
        calendar_id = config.get(key)
        if not calendar_id:
            continue
        events = fetch_today_events(service, calendar_id, today_start, today_end)
        sections.append((label, events))

    message = build_message(sections)
    now_str = datetime.now(JST).isoformat(timespec="seconds")

    try:
        send_line_message(message)
        print(f"[{now_str}] 送信成功")
    except Exception as e:
        print(f"[{now_str}] 送信失敗: {e}")


if __name__ == "__main__":
    main()
