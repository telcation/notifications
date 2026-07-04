# LINE リマインダーアプリ

指定した日時にLINEへリマインダーを送信するツールです。繰り返し種別(1回のみ/毎日/毎月/毎年)を
指定でき、`disable`(スヌーズ停止)にするまで繰り返します。CLIとWeb GUIの両方で操作できます。

## 構成

| ファイル | 役割 |
|---|---|
| `config.json` | LINE Messaging APIのトークンとユーザーID(Git管理外にすること) |
| `reminders.json` | 登録済みリマインダーの一覧・状態(自動更新される) |
| `reminders_store.py` | reminders.jsonの読み書き共通処理(CLI/cron/GUIで共有) |
| `line_utils.py` | LINE Messaging API へのpush送信処理 |
| `reminder_manager.py` | リマインダーの追加・一覧・ON/OFF・削除を行うCLI |
| `reminder_web.py` | ブラウザから編集できるWeb GUI(Flask) |
| `send_reminder.py` | cronから毎分呼ばれ、条件が一致したリマインダーを送信する |

## 1. セットアップ

```bash
cd line_reminder
cp config.json.example config.json
```

`config.json` を編集し、以下を設定してください。

```json
{
  "channel_access_token": "LINE Developersコンソールで発行したチャネルアクセストークン",
  "user_id": "取得済みのLINEユーザーID"
}
```

※ チャネルアクセストークンは、以前 telcation/weather-warning や家族カレンダー印刷システムで
使われているLINE Messaging APIのチャネルと共用しても構いません(その場合はそのトークンを使用)。
別チャネルにする場合は LINE Developers コンソールで新規発行してください。

## 2. リマインダーの登録(CLIの場合)

Web GUI(8.参照)を使わずSSH経由で素早く操作したい場合はこちら。

```bash
# 例: 2026-08-01 09:00から毎年その日に通知
python reminder_manager.py add --message "健康診断" --datetime "2026-08-01T09:00" --repeat yearly

# 例: 毎日18:00に通知
python reminder_manager.py add --message "退勤報告を忘れずに" --datetime "2026-07-05T18:00" --repeat daily

# 例: 1回だけ通知(送信後は自動でOFFになる)
python reminder_manager.py add --message "書類提出締切" --datetime "2026-07-10T17:00" --repeat none

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
`--repeat` は `none`(1回のみ) / `daily`(毎日) / `monthly`(毎月) / `yearly`(毎年) から選択します。

## 3. 動作確認(手動テスト)

`send_reminder.py` は「現在時刻と `notify_datetime` の時刻・繰り返し条件が一致した場合のみ」送信するため、
即座に動作確認したい場合は、テスト用リマインダーの時刻を1〜2分後に設定して`add`してから、
下記を手動実行して確認してください。

```bash
python send_reminder.py
```

送信に成功すると `reminders.json` の該当リマインダーの `last_sent_period` が更新され、
同一期間内(daily=当日、monthly=当月、yearly=当年)は再送されません
(cronで毎分実行しても二重送信しない仕組みです)。

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

## 5. 毎朝8:00の予定通知(calendar_notify.py)

`calendar_print_sa.py` と同じサービスアカウント(`service_account.json`)・カレンダーIDを
そのまま使い、印刷はせずLINEへテキスト通知するスクリプトです。

```bash
cp calendar_config.json.example calendar_config.json
```

`calendar_config.json` を編集:

```json
{
  "service_account_file": "service_account.json",
  "my_calendar_id": "自分のカレンダーID(通常はGmailアドレス)",
  "wife_calendar_id": "妻のカレンダーID"
}
```

`service_account.json` は既存の `calendar_print_sa.py` で使っているものをコピーして
このディレクトリに配置してください(権限は既に共有済みのはずです)。

依存パッケージのインストール(venv内で):
```bash
pip install -r requirements.txt
```

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
0 8 * * * cd ~/notifications && /path/to/venv/bin/python calendar_notify.py >> calendar_notify.log 2>&1
```

## 6. Ubuntu backup-serverへの統合について

プリンターがネットワーク対応であれば、下記の移行で問題ありません。

1. `~/notifications/` ディレクトリを作成し、本プロジェクト一式と
   `calendar_print_sa.py`・`service_account.json`・IPAexフォントを配置
2. 日本語フォント: `sudo apt install fonts-ipaexfont`
   (手動配置する場合は `ipaexg.ttf` のパスを `calendar_print_sa.py` 側で調整)
3. プリンター: Ubuntu側でCUPSにネットワークプリンターを追加登録
   (`http://localhost:631` の管理画面、または `lpadmin` コマンド)し、
   `lpr -P <登録した名前>` で印刷できることを確認
4. `config.json`(LINEトークン/ユーザーID)を1つにまとめ、
   `send_reminder.py` / `calendar_notify.py` / `calendar_print_sa.py` すべてから
   同じ `line_utils.py` 経由で共有
5. crontabに3つのジョブを登録:
   ```
   * * * * *      send_reminder.py     (毎分)
   0 8 * * *      calendar_notify.py   (毎朝8:00 予定通知)
   0 7 1,10,20 * * calendar_print_sa.py (1・10・20日 印刷)
   ```
6. 学生向けNextcloud/Samba用ユーザーとは別に、個人用の実行ユーザー(またはディレクトリの
   パーミッション)を分けておくと、認証情報の管理上すっきりします。

## 7. GitHub Actionsによる自動デプロイ(CI/CD)

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
4. `rsync`でコードを同期(`config.json` / `calendar_config.json` / `service_account.json` /
   `reminders.json` は**除外**され、サーバー上の実データ・認証情報は上書きされない)
5. デプロイ完了をLINEに通知

**PyCharm側の作業**は通常のGit運用と同じです(コミット→push)。
ワークフロー自体を意識する必要はなく、Actionsタブで結果を確認できます。

**認証情報・状態ファイルはGit管理外**です(`.gitignore`参照)。
初回のみ手動で `config.json` 等をbackup-server上に配置してください
(`SELF_HOSTED_RUNNER_SETUP.md` の手順4)。cronの登録もデプロイでは行われないため、
初回セットアップ時に別途設定してください。

## 8. Web GUI(reminder_web.py)によるリマインダー管理

CLI(`reminder_manager.py`)に代えて、ブラウザから件名・通知日時・繰り返し
(1回のみ/毎日/毎月/毎年)・有効/無効(スヌーズ停止)を編集できるWeb GUIです。
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

### デプロイ時の自動再起動権限(sudoers)

`deploy.yml`はコード更新後に`sudo systemctl restart reminder-web.service`を実行します。
セルフホストランナーは`ksk`ユーザーで動くため、このコマンドだけをパスワードなしで
許可する設定を追加してください(`NOPASSWD: ALL`のような広い許可は避けます)。

```bash
sudo visudo -f /etc/sudoers.d/reminder-web-restart
```

以下の1行を追加:
```
ksk ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart reminder-web.service
```

### リマインダーのスキーマ(reminders.json)

```json
{
  "id": "abc12345",
  "message": "件名",
  "notify_datetime": "2026-08-01T09:00",
  "repeat": "none",
  "enabled": true,
  "last_sent_period": null
}
```

- `repeat`: `none`(1回のみ、送信後に自動でOFF)/ `daily`(毎日)/ `monthly`(毎月、同じ「日」)/ `yearly`(毎年、同じ「月日」)
- `monthly`で31日など存在しない月がある場合、その月はスキップされます(例: 31日指定で2月は発火しません)
- 編集すると`last_sent_period`が自動でリセットされ、次回の該当日時に必ず送信されます

## 補足・制約事項

- **同時刻に複数リマインダーがある場合**もそれぞれ独立して送信されます。
- **時刻の一致判定は分単位**です。cronが1分ごとに実行される前提のため、秒単位の指定はできません。
- **backup-serverが停止・再起動中の時刻**はcron自体が動かないため送信されません
 (これはcron方式の一般的な制約です)。backup-serverはNextcloud/Samba用に常時稼働している
 前提のため、通常は問題になりません。
- 複数のLINE宛先(例: 家族それぞれ)に送りたい場合は、現状 `config.json` の `user_id` は1件のみ対応です。
 複数宛先が必要でしたらリマインダーごとに宛先を持たせる拡張も可能です(必要であればお申し付けください)。
