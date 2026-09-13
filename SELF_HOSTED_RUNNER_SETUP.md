# backup-server(Ubuntu)へのセルフホストランナー導入手順

GitHubのホスト型ランナーは自宅LAN内(プライベートIP)のbackup-serverへ到達できないため、
backup-server自身にランナーを常駐させ、GitHubへアウトバウンドでジョブを取りに行かせる方式です。
ポート開放・SSH公開鍵の追加登録・sslh等の設定は一切不要です。

## 1. リポジトリ側の準備

GitHubリポジトリ(例: `notifications`)の
`Settings > Actions > Runners > New self-hosted runner` を開き、
表示される登録トークンを控えておく(トークンは短時間で失効するため、その場で使う)。

## 2. backup-server側の作業

```bash
ssh ksk@192.168.3.201

mkdir -p ~/actions-runner && cd ~/actions-runner

# GitHubの案内ページに表示される最新バージョンのURLに置き換えてください
curl -o actions-runner-linux-x64.tar.gz -L \
  https://github.com/actions/runner/releases/download/vX.XXX.X/actions-runner-linux-x64-X.XXX.X.tar.gz
tar xzf ./actions-runner-linux-x64.tar.gz

./config.sh --url https://github.com/<owner>/<repo> --token <発行されたトークン>
```

設定時の質問:
- runner group: 未使用なら Enter(デフォルト)
- runner name: `backup-server` などわかりやすい名前
- labels: 未使用なら Enter
- work folder: 未使用なら Enter(デフォルト `_work`)

## 3. systemdサービスとして常駐化

```bash
sudo ./svc.sh install
sudo ./svc.sh start
sudo ./svc.sh status
```

これで再起動後も自動的にランナーが起動し、GitHubへのポーリングを継続します。

## 4. 初回デプロイ前の手動セットアップ(1回だけ)

ランナーはリポジトリの内容を配置するだけなので、認証情報は別途手動で置く必要があります。

```bash
mkdir -p ~/notifications
cp ~/path/to/existing/service_account.json ~/notifications/service_account.json
cd ~/notifications
cp .env.example .env                                   # NOTIFICATION_BASE_URL / NOTIFICATION_API_KEY を編集
cp calendar_config.json.example calendar_config.json    # 値を編集
```

通知の送信は NotificationAPI(共通通知基盤)経由で行うため、LINEのChannel Access TokenやUser IDは
このリポジトリ側には置きません。`.env` にはNotificationAPI用のアプリ固有APIキーのみを設定してください
(APIキーの発行方法はNotificationAPI側のドキュメント参照)。

cronの登録もこのタイミングで行ってください(README.md の該当項目を参照)。
Actionsのワークフローはコード配置のみ担当し、cron自体はデプロイのたびに書き換えません。

## 5. 動作確認

PyCharmから通常どおりコミット・pushすると、Actionsタブでジョブが走り、
backup-server上の`~/notifications/`が同期されます。
デプロイ完了時にLINEへ通知が届けば成功です。

```bash
# backup-server側でランナーのログを直接確認したい場合
sudo journalctl -u actions.runner.* -f
```

## セキュリティ上の注意

セルフホストランナーは、リポジトリにpushされたワークフロー定義をそのまま実行します。
このリポジトリを**Privateのまま運用し、pushできる人を自分(または信頼できる家族)に限定**して
ください。Publicリポジトリや第三者のPull Requestを受け付ける運用では、任意コード実行の
リスクがあるため推奨しません。
