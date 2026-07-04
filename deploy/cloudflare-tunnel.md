# Cloudflare Tunnel（Stripe Webhook公開用）

Bot（`bot.py`のPhase 2実装）は、`STRIPE_WEBHOOK_SECRET`が設定されている場合に
`127.0.0.1:{{STRIPE_WEBHOOK_PORT}}`（既定8080）でStripe Webhook受け口（`stripe_webhook.py`、
パス`/stripe/webhook`）を起動する。これはlocalhostのみでLISTENするため、Stripe側から
実際にPOSTを受け取るには外部公開が必要。Raspberry Pi上でCloudflare Tunnelを常駐させ、
グローバルIP開放やポート開放（ルーターのポートフォワーディング）なしに
公開ホスト名（例: `pay.ryuteklabo.com`）を`http://127.0.0.1:8080`へトンネルする。

## 1. cloudflaredのインストール（Raspberry Pi / ARM）

```bash
# 公式リポジトリからARM64版（Raspberry Pi OS 64bit想定。32bitの場合はarmhf版）を取得
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64 \
  -o cloudflared
chmod +x cloudflared
sudo mv cloudflared /usr/local/bin/cloudflared
cloudflared --version
```

## 2. Cloudflareへのログイン・Tunnel作成

対象ドメインがCloudflareのDNSで管理されていることが前提。

```bash
cloudflared tunnel login
# ブラウザが開くので、対象ドメイン（例: ryuteklabo.com）を選んで認可する

cloudflared tunnel create {{TUNNEL_NAME}}
# 例: cloudflared tunnel create discord-steam-bot-stripe
# 実行するとTunnel ID（{{TUNNEL_ID}}）と、認証情報ファイル
# ~/.cloudflared/{{TUNNEL_ID}}.json が生成される
```

## 3. Tunnel設定ファイル（config.yml）

`~/.cloudflared/config.yml`（もしくは任意のパス）の例:

```yaml
tunnel: {{TUNNEL_ID}}
credentials-file: /home/ryu/.cloudflared/{{TUNNEL_ID}}.json

ingress:
  # StripeからのWebhookを受けるホスト名。bot.pyがLISTENするポートに向ける
  - hostname: {{PUBLIC_HOSTNAME}}
    service: http://127.0.0.1:{{STRIPE_WEBHOOK_PORT}}
  # 上記以外へのアクセスは404にする（catch-all、必ず最後に置く）
  - service: http_status:404
```

`{{PUBLIC_HOSTNAME}}`の例: `pay.ryuteklabo.com`
`{{STRIPE_WEBHOOK_PORT}}`は`.env`の`STRIPE_WEBHOOK_PORT`と一致させる（既定`8080`）。

## 4. DNSレコードの割り当て

```bash
cloudflared tunnel route dns {{TUNNEL_NAME}} {{PUBLIC_HOSTNAME}}
# 例: cloudflared tunnel route dns discord-steam-bot-stripe pay.ryuteklabo.com
```

CloudflareのDNSに`{{PUBLIC_HOSTNAME}}`のCNAMEが自動追加される（プロキシ経由=オレンジ雲）。

## 5. 動作確認（systemd化する前に一度手動起動）

```bash
cloudflared tunnel --config ~/.cloudflared/config.yml run {{TUNNEL_NAME}}
```

別端末から `curl -i https://{{PUBLIC_HOSTNAME}}/stripe/webhook` を実行し、
Bot側（`stripe_webhook.py`）まで到達して400（署名不正、想定通り）が返ってくることを確認する。
200番台の応答やCloudflare側のエラーページが返る場合は設定を見直す。

## 6. systemd化

`/etc/systemd/system/cloudflared.service` の例:

```ini
[Unit]
Description=Cloudflare Tunnel (Stripe Webhook)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ryu
ExecStart=/usr/local/bin/cloudflared tunnel --config /home/ryu/.cloudflared/config.yml run {{TUNNEL_NAME}}
Restart=always
RestartSec=5

StandardOutput=journal
StandardError=journal
SyslogIdentifier=cloudflared

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now cloudflared.service
journalctl -u cloudflared -f   # ログ確認
```

## 7. Stripeダッシュボード側の設定

Stripeダッシュボード → 開発者 → Webhook → エンドポイントを追加:

- URL: `https://{{PUBLIC_HOSTNAME}}/stripe/webhook`
- 送信するイベント: `checkout.session.completed` / `customer.subscription.deleted` /
  `customer.subscription.updated`（`stripe_webhook.py`の`EVENT_HANDLERS`が対応するイベント）

作成後に発行される署名シークレット（`whsec_...`）を`.env`の`STRIPE_WEBHOOK_SECRET`に設定し、
Botを再起動する。

## 補足: cloudflaredのアップデート

```bash
cloudflared update
sudo systemctl restart cloudflared
```
