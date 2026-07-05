# Cloudflare Pages（LP・法的表示ページ公開用）

`site/`ディレクトリ（LPと`terms/` `privacy/` `tokushoho/` `refund/`の各法的ページ）を
Cloudflare Pagesで静的サイトとして公開する手順。Stripe Webhook用の
Cloudflare Tunnel（`pay.ryuteklabo.com`、`deploy/cloudflare-tunnel.md`参照）とは
別サービス（Pages vs Tunnel）・別ホスト名なので、共存に問題はない。

## 公開前チェックリスト（必須）

- [ ] `legal/tokushoho.md`および`site/tokushoho/index.html`の「運営責任者」欄が
      `準備中` のままになっている。**特定商取引法上、実際の運営者名の記載が必要な項目のため、
      本番公開前に必ず実名を記入すること。**
- [ ] `support@ryuteklabo.com`宛のメールが実際に受信できるよう、ドメイン側（Cloudflareの
      Email Routing等）で転送設定を行っておく。
- [ ] Discord Developer PortalでOAuth2スコープ・権限（招待URLの`permissions=19456`
      = View Channels + Send Messages + Embed Links）が実際のBotの必要権限と一致しているか確認する。
      権限を追加した場合は`site/index.html`・`site/en/index.html`内の招待URLも更新する。

## 1. wranglerのインストール・ログイン

```bash
npm install -g wrangler
wrangler login
# ブラウザが開くので、Cloudflareアカウント（ryuteklabo.comを管理しているアカウント）で認可する
```

## 2. Pagesプロジェクトの作成・デプロイ

リポジトリルートで実行する（`site/`をそのまま公開ディレクトリとして指定）。

```bash
cd /path/to/DISCORD-STEAM-BOT
wrangler pages deploy site --project-name=discord-steam-bot-lp
```

初回はプロジェクト名の確認を聞かれるので、上記`--project-name`をそのまま使う。
成功すると`https://discord-steam-bot-lp.pages.dev`のようなデフォルトURLが発行され、
すでにこのURLで`/` `/terms` `/privacy` `/tokushoho` `/refund` `/en/`が閲覧できる状態になる。

## 3. カスタムドメインの割り当て（ryuteklabo.comルート）

Cloudflareダッシュボード → Workers & Pages → 対象プロジェクト → Custom domains から
`ryuteklabo.com`（ルートドメイン）を追加する。

- `pay.ryuteklabo.com`はStripe Webhook用のTunnelで別途使用中のため、ここでは追加しない。
- ルートドメインをPagesに向けると、Cloudflareが自動的にDNSレコード（CNAME/フラット化）を
  設定する。既存の`pay`サブドメインのCNAMEレコードには影響しない。
- `www.ryuteklabo.com`も使う場合は、Pages側の設定でwww→ルート（またはその逆）へのリダイレクトを
  有効にできる。

反映後、`https://ryuteklabo.com`でLPが、`https://ryuteklabo.com/terms`等で各法的ページが
閲覧できることを確認する。

## 4. 更新時の再デプロイ

`site/`配下のHTML/CSSを編集したら、同じコマンドで再デプロイする。

```bash
wrangler pages deploy site --project-name=discord-steam-bot-lp
```

## 5. Discord招待URLの反映

Discord Developer Portal → 対象アプリケーション → OAuth2 → URL Generator で
Client ID（`1522688278589866164`）・scope（`bot` `applications.commands`）・
必要な権限を選択し、生成されたURLが`site/index.html`・`site/en/index.html`内の
招待ボタンと一致していることを確認する。権限を変更した場合は両ファイルの
`https://discord.com/oauth2/authorize?...`のリンクを更新して再デプロイする。
