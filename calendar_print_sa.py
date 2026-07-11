#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""家族カレンダーをA4用紙に印刷する(backup-server/Ubuntu版)。

Mac Mini版からの変更点:
- SERVICE_ACCOUNT_FILE / PRINTER_NAME / カレンダーID / FONT_PATH のハードコードを廃止し、
  calendar_notify.pyと共有の calendar_config.json から読み込む
- 独自実装だったLINE通知(send_line_notify)を line_utils.send_line_message に統一
- 出力PDFのパスを ~/calendar_output.pdf からプロジェクトディレクトリ内に変更

カレンダー描画ロジック(get_date_range/get_events/draw_section)自体は
Mac Mini版から変更していません。

crontab 例(毎月1・10・20日 朝7時):
  0 7 1,10,20 * * cd /path/to/notifications && venv/bin/python calendar_print_sa.py >> calendar_print.log 2>&1
"""
import datetime
import subprocess
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from calendar_config_store import load_calendar_config, resolve_service_account_path
from line_utils import send_line_message

from google.oauth2 import service_account
from googleapiclient.discovery import build

BASE_DIR = Path(__file__).parent
OUTPUT_PDF = str(BASE_DIR / "calendar_output.pdf")

FONT_NAME = "IPAexGothic"
WEEKDAYS = ["日", "月", "火", "水", "木", "金", "土"]
COLOR_MY = colors.HexColor("#3A7BD5")
COLOR_WIFE = colors.HexColor("#2ECC71")
COLOR_SAT = colors.HexColor("#5B9BD5")
COLOR_SUN = colors.HexColor("#E74C3C")
COLOR_TODAY = colors.HexColor("#F39C12")

# フォントサイズ(文字を大きくしたい場合はここを調整する)
FONT_SIZE_PAGE_TITLE = 16      # ページ上部の「家族カレンダー ○月」
FONT_SIZE_SECTION_TITLE = 13   # 「自分のスケジュール」「妻のスケジュール」
FONT_SIZE_WEEKDAY = 11         # 曜日ヘッダー(日〜土)
FONT_SIZE_DATE_NUM = 11        # 各マスの日付数字
FONT_SIZE_EVENT = 8            # 予定のテキスト

# 1マスに表示する予定の最大件数。文字を大きくした分、3件のままだと
# マスからはみ出す恐れがあるため2件に減らしている。
MAX_EVENTS_PER_DAY = 2
EVENT_LINE_HEIGHT = 5.2 * mm
EVENT_TEXT_MAX_CHARS = 9


def get_service(service_account_file: str):
    sa_path = resolve_service_account_path(service_account_file)
    creds = service_account.Credentials.from_service_account_file(
        str(sa_path), scopes=["https://www.googleapis.com/auth/calendar.readonly"]
    )
    return build("calendar", "v3", credentials=creds)


def get_events(service, calendar_id, start_date, end_date):
    result = {}
    try:
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=start_date.strftime("%Y-%m-%dT00:00:00+09:00"),
            timeMax=end_date.strftime("%Y-%m-%dT23:59:59+09:00"),
            singleEvents=True,
            orderBy="startTime",
            maxResults=500,
        ).execute()
        for event in events_result.get("items", []):
            start = event["start"].get("date") or event["start"].get("dateTime", "")[:10]
            title = event.get("summary", "（無題）")
            result.setdefault(start, []).append(title)
    except Exception as e:
        print(f"イベント取得エラー ({calendar_id}): {e}")
    return result


def get_date_range():
    today = datetime.date.today()
    day = today.day
    if day == 1:
        start = today.replace(day=1)
        next_month = (start.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        end = next_month - datetime.timedelta(days=1)
        label = f"{today.year}年{today.month}月"
    else:
        start = today - datetime.timedelta(days=(today.weekday() + 1) % 7)
        end = start + datetime.timedelta(weeks=5) - datetime.timedelta(days=1)
        label = f"{start.month}/{start.day}〜{end.month}/{end.day}"
    return start, end, label


def draw_section(c, service, calendar_id, event_color, title,
                  start_date, end_date, sx, sy, sw, sh, font_name, today):
    events = get_events(service, calendar_id, start_date, end_date)
    c.setFillColor(event_color)
    c.rect(sx, sy + sh - 8 * mm, sw, 8 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont(font_name, FONT_SIZE_SECTION_TITLE)
    c.drawString(sx + 3 * mm, sy + sh - 6 * mm, title)
    grid_h = sh - 8 * mm
    grid_top = sy + grid_h
    weeks = []
    current = start_date - datetime.timedelta(days=(start_date.weekday() + 1) % 7)
    while current <= end_date:
        weeks.append([current + datetime.timedelta(days=i) for i in range(7)])
        current += datetime.timedelta(weeks=1)
    cell_w = sw / 7
    cell_h = grid_h / (len(weeks) + 1)
    for col, wd in enumerate(WEEKDAYS):
        cx = sx + col * cell_w
        cy = grid_top - cell_h
        bg = COLOR_SUN if col == 0 else (COLOR_SAT if col == 6 else colors.HexColor("#F0F0F0"))
        c.setFillColor(bg)
        c.rect(cx, cy, cell_w, cell_h, fill=1, stroke=1)
        c.setFillColor(colors.black)
        c.setFont(font_name, FONT_SIZE_WEEKDAY)
        c.drawCentredString(cx + cell_w / 2, cy + cell_h * 0.3, wd)
    for row, week in enumerate(weeks):
        for col, d in enumerate(week):
            cx = sx + col * cell_w
            cy = grid_top - cell_h * (row + 2)
            in_range = start_date <= d <= end_date
            is_today = (d == today)
            if is_today:
                c.setFillColor(COLOR_TODAY)
            elif not in_range:
                c.setFillColor(colors.HexColor("#EEEEEE"))
            elif col == 0:
                c.setFillColor(colors.HexColor("#FFF0F0"))
            elif col == 6:
                c.setFillColor(colors.HexColor("#EEF4FF"))
            else:
                c.setFillColor(colors.white)
            c.rect(cx, cy, cell_w, cell_h, fill=1, stroke=1)
            tc = COLOR_SUN if col == 0 else (COLOR_SAT if col == 6 else colors.black)
            c.setFillColor(tc)
            c.setFont(font_name, FONT_SIZE_DATE_NUM)
            c.drawString(cx + 1 * mm, cy + cell_h - 4 * mm, str(d.day))
            date_str = d.strftime("%Y-%m-%d")
            if in_range and date_str in events:
                c.setFillColor(event_color)
                c.setFont(font_name, FONT_SIZE_EVENT)
                for i, ev in enumerate(events[date_str][:MAX_EVENTS_PER_DAY]):
                    ey = cy + cell_h - 7 * mm - i * EVENT_LINE_HEIGHT
                    if ey > cy + 0.5 * mm:
                        ev_text = ev[:EVENT_TEXT_MAX_CHARS] + "…" if len(ev) > EVENT_TEXT_MAX_CHARS else ev
                        c.drawString(cx + 0.8 * mm, ey, ev_text)


def generate_pdf(output_path: str, config: dict) -> None:
    pdfmetrics.registerFont(TTFont(FONT_NAME, config["font_path"]))
    today = datetime.date.today()
    start_date, end_date, label = get_date_range()
    service = get_service(config["service_account_file"])
    page_w, page_h = A4
    margin = 10 * mm
    c = canvas.Canvas(output_path, pagesize=A4)
    c.setFillColor(colors.HexColor("#333333"))
    c.setFont(FONT_NAME, FONT_SIZE_PAGE_TITLE)
    c.drawCentredString(page_w / 2, page_h - margin - 5 * mm, f"家族カレンダー　{label}")
    avail_h = page_h - margin * 2 - 12 * mm
    section_h = avail_h / 2
    section_w = page_w - margin * 2
    draw_section(c, service, config["my_calendar_id"], COLOR_MY, "自分のスケジュール",
                 start_date, end_date, margin, margin + section_h, section_w, section_h, FONT_NAME, today)
    draw_section(c, service, config["wife_calendar_id"], COLOR_WIFE, "妻のスケジュール",
                 start_date, end_date, margin, margin, section_w, section_h, FONT_NAME, today)
    c.save()
    print(f"PDF生成完了: {output_path}")


def main() -> None:
    today = datetime.date.today()
    print(f"実行日: {today}")
    config = load_calendar_config()
    try:
        generate_pdf(OUTPUT_PDF, config)
        result = subprocess.run(
            ["lpr", "-P", config["printer_name"], OUTPUT_PDF],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            msg = f"【カレンダー印刷】{today}\n印刷失敗\n{result.stderr}"
            print(msg)
            send_line_message(msg)
        else:
            print("印刷ジョブ送信完了")
            msg = f"【カレンダー印刷】{today}\n印刷しました。確認してください。"
            send_line_message(msg)
    except Exception as e:
        msg = f"【カレンダー印刷】{today}\nエラー発生\n{str(e)}"
        print(msg)
        send_line_message(msg)


if __name__ == "__main__":
    main()
