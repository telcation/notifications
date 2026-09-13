# LINE リマインダーアプリ

指定した日時にLINEへリマインダーを送信するツールです。繰り返し(n日ごと/nヶ月ごと/n年ごと/1回のみ)を
指定でき、`disable`(スヌーズ停止)にするまで繰り返します。CLIとWeb GUIの両方で操作できます。

通知の実送信は、このリポジトリでは行わず、共通通知基盤 **NotificationAPI**
(`https://telcation.com/notification/`)へHTTPS経由で委譲します。LINEのChannel Access Token等の
秘密情報はこのリポジトリ・backup-server双方に置かず、NotificationAPI側のVPSにのみ保持します。

## 構成

| ファイル | 役割 |
|---|---|
| `.env` | NotificationAPI接続用の `NOTIFICATION_BASE_URL` / `NOTIFICATION_API_KEY`(Git管理外にすること) |
| `notification_client.py` | NotificationAPIへ通知要求を送る共通クライアント(NotificationAPIリポジトリからコピー) |
| `reminders.json` | 登録済みリマインダーの一覧・状態(自動更新される) |
| `reminders_store.py` | reminders.jsonの読み書き共通処理(CLI/cron/GUIで共有) |
| `reminder_manager.py` | リマインダーの追加・一覧・ON/OFF・削除を行うCLI |
| `reminder_web.py` | ブラウザから編集できるWeb GUI(Flask) |
| `send_reminder.py` | cronから毎分呼ばれ、条件が一致したリマインダーを送信する |
| `calendar_config.json` | Googleサービスアカウント・カレンダーID・プリンター名・フォントパス(Git管理外) |
| `calendar_config_store.py` | calendar_config.jsonの読み込み共通処理 |
| `calendar_notify.py` | 毎朝8:00に本日の予定をLINE通知する |
| `calendar_print_sa.py` | 毎月1・10・20日にA4カレンダーを印刷する |

## 1. セットアップ

```bash
cd notifications
cp .env.example .env
```

`.env` を編集し、以下を設定してください。

```
NOTIFICATION_BASE_URL=https://telcation.com/notification
NOTIFICATION_API_KEY=このアプリ用に発行したAPIキー
```

※ `NOTIFICATION_API_KEY` はNotificationAPI側で `generate_api_key.py` を実行して発行し、
VPSの `API_KEYS_JSON` に「キー: notifications」のように登録したうえで、
`notification-api` サービスを再起動しておく必要があります(NotificationAPI側の手順)。
LINEのChannel Access Token・User/Group IDはこのリポジトリ側では一切保持しません。

## 2. リマインダーの登録(CLIの場合)

Web GUI(10.参照)を使わずSSH経由で素早く操作したい場合はこちら。

```bash
# 例: 2026-08-01 09:00から毎年その日に通知(1年ごと)
python reminder_manager.py add --message "健康診断" --datetime "2026-08-01T09:00" --repeat-unit year --repeat-interval 1

# 例: 3日ごとに通知
python reminder_manager.py add --message "水やり" --datetime "2026-07-05T18:00" --repeat-unit day --repeat-interval 3

# 例: 1回だけ通知(スヌーズ停止すると、次の周期が無いのでそのまま停止する)
python reminder_manager.py add --message "書類提出締切" --datetime "2026-07-10T17:00" --repeat-unit none

# 一覧確認
python reminder_manager.py list

# OFFにする(スヌーズ停止。以降送信されなくなる)
python reminder_manager.py disable <id>

# 再度ONにする
python reminder_manager.py enable <id>

# 削除
python reminder_manager.py remove <id>
```

`add` 実行時に `id` を省略すると8文字のランダムIDが自動採番されます。
`--repeat-unit` は `none`(1回のみ) / `day`(n日ごと) / `month`(nヶ月ごと) / `year`(n年ごと) から選択し、
`--repeat-interval` でn(間隔)を指定します(省略時は1)。

## 3. 動作確認(手動テスト)

`send_reminder.py` は「現在時刻と `notify_datetime` の時刻・繰り返し条件が一致した場合のみ」送信するため、
即座に動作確認したい場合は、テスト用リマインダーの時刻を1〜2分後に設定して`add`してから、
下記を手動実行して確認してください。

```bash
python send_reminder.py
```

送信に成功すると `reminders.json` の該当リマインダーの `last_sent_at` が更新されます。
毎日繰り返し送信される仕様のため(下記「スヌーズの仕様」参照)、同一時刻の重複実行(cronの
多重起動等)は`enabled`/`cycle_start`の状態変化が無い限り再送されません。

## 4. cron登録(backup-server常時稼働・毎分チェック)

`~/notifications`(backup-server上)で以下を実行:

```bash
crontab -e
```

以下を追記(パスは実際の配置場所に置き換えてください):

```
* * * * * cd /home/ksk/notifications && /home/ksk/notifications-venv/bin/python send_reminder.py >> send_reminder.log 2>&1
```

backup-serverはNextcloud/Samba/Time Machine用に常時稼働している前提のため、
Mac Miniのようなスリープによる実行漏れの心配はありません。

## 5. カレンダー連携の共通設定(calendar_config.json)

`calendar_notify.py`(毎朝8:00の予定通知)と`calendar_print_sa.py`(1・10・20日の印刷)は
どちらもこの1つの設定ファイルを共有します。

```bash
cp calendar_config.json.example calendar_config.json
```

`calendar_config.json` を編集:

```json
{
  "service_account_file": "service_account.json",
  "my_calendar_id": "自分のカレンダーID(通常はGmailアドレス)",
  "wife_calendar_id": "妻のカレンダーID",
  "printer_name": "CUPSに登録したプリンター名",
  "font_path": "/usr/share/fonts/opentype/ipaexfont-gothic/ipaexg.ttf"
}
```

`service_account.json` はMac Miniで使っているものをコピーして配置してください
(権限は既に自分・妻のカレンダーへ共有済みのはずです)。

日本語フォントは以下でインストールできます(Ubuntu):
```bash
sudo apt install fonts-ipaexfont
```
インストール後のパスは通常 `/usr/share/fonts/opentype/ipaexfont-gothic/ipaexg.ttf` です
(`fc-list | grep -i ipaex` で実際のパスを確認できます)。

プリンターはCUPSにネットワークプリンターとして登録してください
(`http://localhost:631` の管理画面、または `lpadmin` コマンド)。
登録した名前を `printer_name` に設定し、`lpr -P <名前>` で印刷できることを確認してから進めてください。

依存パッケージのインストール(venv内で):
```bash
pip install -r requirements.txt   # google-api-python-client, google-auth, reportlab
```

## 6. 毎朝8:00の予定通知(calendar_notify.py)

印刷は行わず、LINEへテキスト通知のみ行うスクリプトです。

手動テスト:
```bash
python calendar_notify.py
```

送信例:
```
📅 7月4日(土)の予定

【自分】
　09:00  1限:Java基礎
　13:00  職員会議

【妻】
　予定なし
```

cron登録(毎朝8:00):
```
0 8 * * * cd ~/notifications && ~/notifications-venv/bin/python calendar_notify.py >> calendar_notify.log 2>&1
```

## 7. カレンダー印刷(calendar_print_sa.py)

Mac Mini版から移植したスクリプトです。カレンダー描画ロジック(月間/5週表示、
自分=青・妻=緑、今日はオレンジ表示など)はMac Mini版から変更していません。
LINE通知は独自実装をやめ、`notification_client.notify`(NotificationAPI経由)に統一しています。

手動テスト:
```bash
python calendar_print_sa.py
```

成功すると `calendar_output.pdf`(プロジェクトディレクトリ内、Git管理外)が生成され、
`printer_name`で指定したプリンターに印刷ジョブが送信されます。印刷成功・失敗どちらの場合も
LINEに結果が通知されます。

cron登録(毎月1・10・20日 朝7時):
```
0 7 1,10,20 * * cd ~/notifications && ~/notifications-venv/bin/python calendar_print_sa.py >> calendar_print.log 2>&1
```

## 8. backup-server上のcron一覧(まとめ)

```
* * * * *        cd ~/notifications && ~/notifications-venv/bin/python send_reminder.py >> send_reminder.log 2>&1
0 8 * * *        cd ~/notifications && ~/notifications-venv/bin/python calendar_notify.py >> calendar_notify.log 2>&1
0 7 1,10,20 * *  cd ~/notifications && ~/notifications-venv/bin/python calendar_print_sa.py >> calendar_print.log 2>&1
```

学生向けNextcloud/Samba用ユーザーとは別に、個人用の実行ユーザー(またはディレクトリの
パーミッション)を分けておくと、認証情報の管理上すっきりします。

## 9. GitHub Actionsによる自動デプロイ(CI/CD)

このプロジェクトをGitリポジトリ化し、PyCharmからpushするだけで
backup-serverへ自動デプロイされる構成にできます。

**方式**: backup-server自身にセルフホストランナーを常駐させ、
GitHub側からのアウトバウンドではなく、backup-server側からGitHubへポーリングする方式です。
自宅LAN内のプライベートIPしか持たないマシンでも、ポート開放やSSH公開なしで実現できます。
セットアップ手順は `SELF_HOSTED_RUNNER_SETUP.md` を参照してください。

**デプロイの流れ** (`.github/workflows/deploy.yml`):
1. `main`ブランチへのpushをトリガーに、backup-server上のランナーがジョブを実行
2. `.py`ファイルの構文チェック(`py_compile`)
3. venvへ依存パッケージをインストール
4. `rsync`でコードを同期(`.env` / `calendar_config.json` / `service_account.json` /
   `reminders.json` は**除外**され、サーバー上の実データ・認証情報は上書きされない)
5. デプロイ完了をNotificationAPI経由でLINEに通知

**PyCharm側の作業**は通常のGit運用と同じです(コミット→push)。
ワークフロー自体を意識する必要はなく、Actionsタブで結果を確認できます。

**認証情報・状態ファイルはGit管理外**です(`.gitignore`参照)。
初回のみ手動で `.env` 等をbackup-server上に配置してください
(`SELF_HOSTED_RUNNER_SETUP.md` の手順4)。cronの登録もデプロイでは行われないため、
初回セットアップ時に別途設定してください。

## 10. Web GUI(reminder_web.py)によるリマインダー管理

CLI(`reminder_manager.py`)に代えて、ブラウザから件名・通知日時・繰り返し
(1回のみ/n日ごと/nヶ月ごと/n年ごと)・有効/無効(スヌーズ停止)を編集できるWeb GUIです。
データは同じ `reminders.json` を共有するため、CLIと併用しても矛盾は起きません。

### 依存パッケージ

```bash
pip install -r requirements.txt   # flask が追加されています
```

### 常駐化(systemd)

```bash
sudo cp reminder-web.service /etc/systemd/system/reminder-web.service
sudo systemctl daemon-reload
sudo systemctl enable --now reminder-web.service
sudo systemctl status reminder-web.service
```

起動後、同一LAN内の端末(Mac Mini/Windows PCのブラウザ)から
`http://192.168.3.201:5001/` でアクセスできます。

### デプロイ時の自動反映・再起動権限(sudoers)

`deploy.yml`はコード更新後に `deploy_install_service.sh` を実行し、
`reminder-web.service`定義ファイルを`/etc/systemd/system/`へ反映(内容が変わっていれば
`daemon-reload`も実行)したうえでサービスを再起動します。
セルフホストランナーは`ksk`ユーザーで動くため、**このスクリプトの実行だけ**をパスワードなしで
許可してください(`systemctl`や`cp`個別のワイルドカード許可は権限が広がりすぎるため避けます)。

```bash
sudo visudo -f /etc/sudoers.d/reminder-web-deploy
```

以下の1行を追加:
```
ksk ALL=(ALL) NOPASSWD: /home/ksk/notifications/deploy_install_service.sh
```

これにより、`reminder-web.service`ファイルの中身(ポート番号やWorkingDirectory等)を
変更してpushした場合も、次回デプロイで自動的にsystemdへ反映されます。

### リマインダーのスキーマ(reminders.json)

```json
{
  "id": "abc12345",
  "message": "件名",
  "notify_datetime": "2026-08-01T09:00",
  "repeat_unit": "none",
  "repeat_interval": 1,
  "enabled": true,
  "cycle_start": null,
  "last_sent_at": null
}
```

- `repeat_unit`: `none`(1回のみ)/ `day`(n日ごと)/ `month`(nヶ月ごと、同じ「日」)/ `year`(n年ごと、同じ「月日」)
- `repeat_interval`: 間隔n(整数)。`repeat_unit`が`none`の場合は無視される
- `enabled`: 「スヌーズ停止」ボタンで切り替わる。trueの間は**毎日**同時刻に通知し続ける
- `cycle_start`: 現在の周期の開始日。周期の切り替わり(自動再開)の検出に使う内部状態
- `last_sent_at`: 直近送信日時(表示用の記録。送信判定には使わない)
- `month`単位で31日など存在しない月がある場合、その月は周期が切り替わらずスキップされます
- 編集すると`enabled=true`・`cycle_start=null`にリセットされ、次回の該当日時に必ず送信されます
- 旧スキーマ(`repeat: "none"/"daily"/"monthly"/"yearly"`)のデータは、読み込み時に自動的に
  `repeat_unit`/`repeat_interval`へ変換されます(手動でのデータ移行は不要です)

### スヌーズの仕様

指定日時になると通知を開始し、**「スヌーズ停止」を押すまで毎日同時刻に通知し続けます**
(間隔nの値に関わらず、1回鳴らして終わり、ではありません)。

| repeat_unit | スヌーズ停止した場合 |
|---|---|
| `day`(interval=1、旧・毎日相当) | 停止したらそのまま止まる(自動再開は無い) |
| `day`(interval>1、n日ごと) | 停止してもその周期は止まるが、**n日後の境界日に自動的に再開**する |
| `none`(1回のみ) | 停止したらそのまま止まる(次の周期が存在しないため) |
| `month`(nヶ月ごと) | 停止してもその周期は止まるが、**nヶ月後の指定日に自動的に再開**する |
| `year`(n年ごと) | 停止してもその周期は止まるが、**n年後の指定日に自動的に再開**する |

例:「1ヶ月ごと・20日に駐車場代金振り込み」を7/20に有効化 → 7/20〜7/31まで毎日通知 →
7/25にスヌーズ停止(振込完了)→ 8/20になると自動的にまた有効化され、8/20〜8/31まで
毎日通知が再開する、という動きになります。

## 補足・制約事項

- **同時刻に複数リマインダーがある場合**もそれぞれ独立して送信されます。
- **時刻の一致判定は分単位**です。cronが1分ごとに実行される前提のため、秒単位の指定はできません。
- **backup-serverが停止・再起動中の時刻**はcron自体が動かないため送信されません
 (これはcron方式の一般的な制約です)。backup-serverはNextcloud/Samba用に常時稼働している
 前提のため、通常は問題になりません。
- 複数のLINE宛先(例: 家族それぞれ)へ送りたい場合、NotificationAPI側は `line_targets`
 (`personal` / `group`)で個人・グループ別のMessaging APIチャネルに対応しています。
 現状このリポジトリの呼び出しはすべて `notify(message, line=True, email=False)` で
 VPS側の既定宛先(`LINE_DEFAULT_TARGETS`)に送る形のみですが、リマインダーごとに
 `line_targets` を持たせる拡張も可能です(必要であればお申し付けください)。
