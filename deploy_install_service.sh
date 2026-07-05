#!/bin/bash
# reminder-web.service を systemd に反映し、再起動するためのスクリプト。
# root権限が必要な操作(コピー・daemon-reload・restart)をこの1本にまとめることで、
# sudoers側は「このスクリプトの実行のみ」を許可すればよくなる(individual systemctl/cpの
# ワイルドカード許可より権限範囲を絞れる)。
#
# 呼び出し元(deploy.yml)からは `sudo /home/ksk/notifications/deploy_install_service.sh` として実行される。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_SRC="${SCRIPT_DIR}/reminder-web.service"
SERVICE_DST="/etc/systemd/system/reminder-web.service"

if [ ! -f "${SERVICE_SRC}" ]; then
  echo "エラー: ${SERVICE_SRC} が見つかりません。" >&2
  exit 1
fi

# 内容が変わっている場合のみ反映(無変更ならdaemon-reloadを省略)
if ! cmp -s "${SERVICE_SRC}" "${SERVICE_DST}" 2>/dev/null; then
  cp "${SERVICE_SRC}" "${SERVICE_DST}"
  systemctl daemon-reload
  echo "reminder-web.service を更新しました。"
fi

systemctl restart reminder-web.service
echo "reminder-web.service を再起動しました。"
