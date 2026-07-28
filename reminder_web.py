"""リマインダー管理Web GUI(Flask)

backup-server上で常駐させ、同一LAN内のブラウザから
件名・通知日時・繰り返し(毎日/毎月/毎年/1回のみ)・有効/無効を編集する。
あわせて、カレンダー印刷(calendar_print_sa.py)をボタン1つで再実行する機能も提供する
(プリンターの電源が入っていなかった等の理由で失敗した際、SSHせずに再印刷できるようにするため)。

開発用の簡易起動:
  python reminder_web.py           # http://<backup-serverのIP>:5001 で待受

本番運用は systemd (reminder-web.service) 経由での常駐を推奨(README参照)。
"""
import contextlib
import io
from datetime import datetime

from flask import Flask, redirect, render_template, request, url_for

from reminders_store import (
    REPEAT_CHOICES,
    REPEAT_LABELS,
    find_reminder,
    load_reminders,
    new_id,
    save_reminders,
)
import calendar_print_sa

app = Flask(__name__)


@app.route("/")
def index():
    reminders = load_reminders()
    # 通知日時の昇順で表示
    reminders_sorted = sorted(reminders, key=lambda r: r.get("notify_datetime", ""))
    return render_template(
        "index.html",
        reminders=reminders_sorted,
        repeat_labels=REPEAT_LABELS,
    )


@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "GET":
        return render_template(
            "form.html",
            mode="add",
            reminder=None,
            repeat_choices=REPEAT_CHOICES,
            repeat_labels=REPEAT_LABELS,
            error=None,
        )

    message = request.form.get("message", "").strip()
    notify_datetime = request.form.get("notify_datetime", "").strip()
    repeat = request.form.get("repeat", "none")

    error = validate_input(message, notify_datetime, repeat)
    if error:
        return render_template(
            "form.html",
            mode="add",
            reminder={"message": message, "notify_datetime": notify_datetime, "repeat": repeat},
            repeat_choices=REPEAT_CHOICES,
            repeat_labels=REPEAT_LABELS,
            error=error,
        )

    reminders = load_reminders()
    reminders.append({
        "id": new_id(),
        "message": message,
        "notify_datetime": notify_datetime,
        "repeat": repeat,
        "enabled": True,
        "cycle_start": None,
    })
    save_reminders(reminders)
    return redirect(url_for("index"))


@app.route("/edit/<reminder_id>", methods=["GET", "POST"])
def edit(reminder_id):
    reminders = load_reminders()
    reminder = find_reminder(reminders, reminder_id)
    if reminder is None:
        return "指定されたリマインダーが見つかりません。", 404

    if request.method == "GET":
        return render_template(
            "form.html",
            mode="edit",
            reminder=reminder,
            repeat_choices=REPEAT_CHOICES,
            repeat_labels=REPEAT_LABELS,
            error=None,
        )

    message = request.form.get("message", "").strip()
    notify_datetime = request.form.get("notify_datetime", "").strip()
    repeat = request.form.get("repeat", "none")

    error = validate_input(message, notify_datetime, repeat)
    if error:
        return render_template(
            "form.html",
            mode="edit",
            reminder={
                "id": reminder_id,
                "message": message,
                "notify_datetime": notify_datetime,
                "repeat": repeat,
            },
            repeat_choices=REPEAT_CHOICES,
            repeat_labels=REPEAT_LABELS,
            error=error,
        )

    reminder["message"] = message
    reminder["notify_datetime"] = notify_datetime
    reminder["repeat"] = repeat
    # 内容を変更した場合、次の該当時刻に必ず送信されるよう周期状態をリセットする
    reminder["enabled"] = True
    reminder["cycle_start"] = None
    save_reminders(reminders)
    return redirect(url_for("index"))


@app.route("/toggle/<reminder_id>", methods=["POST"])
def toggle(reminder_id):
    reminders = load_reminders()
    reminder = find_reminder(reminders, reminder_id)
    if reminder is None:
        return "指定されたリマインダーが見つかりません。", 404
    reminder["enabled"] = not reminder.get("enabled", False)
    save_reminders(reminders)
    return redirect(url_for("index"))


@app.route("/delete/<reminder_id>", methods=["POST"])
def delete(reminder_id):
    reminders = load_reminders()
    reminders = [r for r in reminders if r["id"] != reminder_id]
    save_reminders(reminders)
    return redirect(url_for("index"))


@app.route("/calendar/reprint", methods=["GET", "POST"])
def calendar_reprint():
    if request.method == "GET":
        return render_template("calendar_reprint.html", result=None)

    # calendar_print_sa.main() は成功/失敗どちらの場合も内部でLINE通知まで行うため、
    # ここでは実行結果(標準出力)をそのまま画面にも表示するだけでよい。
    output = io.StringIO()
    try:
        with contextlib.redirect_stdout(output):
            calendar_print_sa.main()
    except Exception as e:
        print(f"予期しないエラー: {e}", file=output)

    return render_template("calendar_reprint.html", result=output.getvalue())


def validate_input(message: str, notify_datetime: str, repeat: str) -> str | None:
    if not message:
        return "件名を入力してください。"
    try:
        datetime.fromisoformat(notify_datetime)
    except ValueError:
        return "通知日時の形式が正しくありません。"
    if repeat not in REPEAT_CHOICES:
        return "繰り返しの指定が正しくありません。"
    return None


if __name__ == "__main__":
    # LAN内の他端末からアクセスできるよう 0.0.0.0 で待受
    app.run(host="0.0.0.0", port=5001, debug=False)
