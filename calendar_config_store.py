"""calendar_config.json の読み込み共通処理。

calendar_notify.py(毎朝8:00の予定通知)と calendar_print_sa.py(1・10・20日の印刷)の
両方から読み込まれる、Googleカレンダー関連の設定をまとめたモジュール。
"""
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "calendar_config.json"


def load_calendar_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"{CONFIG_PATH} が見つかりません。calendar_config.json.example をコピーし、"
            "service_account_file・カレンダーID・printer_name・font_pathを設定してください。"
        )
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_service_account_path(service_account_file: str) -> Path:
    sa_path = BASE_DIR / service_account_file
    if sa_path.exists():
        return sa_path
    return Path(service_account_file)
