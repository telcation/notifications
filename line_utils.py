"""LINE Messaging API へのプッシュ送信ユーティリティ"""
import json
import urllib.request
import urllib.error
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"{CONFIG_PATH} が見つかりません。config.json.example をコピーして"
            "channel_access_token と user_id を設定してください。"
        )
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def send_line_message(message: str) -> None:
    """LINE Messaging API でプッシュメッセージを送信する。

    失敗時は例外を送出する(呼び出し側でログに残す想定)。
    """
    config = load_config()
    token = config["channel_access_token"]
    user_id = config["user_id"]

    body = {
        "to": user_id,
        "messages": [{"type": "text", "text": message}],
    }

    req = urllib.request.Request(
        LINE_PUSH_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            res.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"LINE送信失敗 status={e.code} detail={detail}") from e
