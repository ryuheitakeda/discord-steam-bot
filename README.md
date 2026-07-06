# 今日なんのゲームする？Bot

Discordのボイスチャンネルに集まったメンバーの共通所持Steamゲームから、「今日一緒にやれるゲーム」を提案するBotです（旧仮称: Discord × Steam VC Bot）。

## できること

- `/link <steam>` — 自分のSteamプロフィールURL（またはSteamID64 / カスタムURL名）を紐づけ
- `/unlink` — 紐づけ解除
- `/profile [user]` — 紐づけ状況の確認
- `/games [all]` — 今VCにいるメンバーの共通所持ゲームからマルチプレイ対応タイトルを上位10件表示（`all:True`で絞り込みなし）
- `/pick [all]` — 上記の中からランダムに1本を提案
- `/premium` — サーバーの契約状況（無料枠 / プレミアム）を確認し、プレミアムへのアップグレード導線を表示

`/link` は自分のSteamプロフィールURL/IDを貼ってもらう方式です。他人のURLを貼っても紐づく先はそのURLが指す（＝貼った本人ではない）Steamアカウントになるだけで、貼った本人には何のメリットもない（＝なりすましの動機がない）ため、Discord OAuth2連携のような外部ドメインを経由する仕組みは使わず、シンプルな自己申告方式にしています。

### フリーミアム制限

`/games` `/pick` はサーバー単位でローリングウィンドウ制限があります（3回/日 かつ 60回/月）。プレミアム（Stripe決済 ¥380/月）に加入したサーバーは無制限になります。上限到達時は自動でアップグレード導線（Stripe Payment Link）を表示します。

管理者向けにBotオーナー限定の `/grant` `/revoke`（プレミアムの手動付与・剥奪）コマンドもあります。

### 多言語対応（i18n）

コマンド応答はDiscordのユーザー言語設定に応じて日本語/英語を自動切り替えします（`locales/ja.json` / `locales/en.json`、`i18n.py` / `translator.py`）。

## セットアップ

### 1. Discord Bot作成

1. [Discord Developer Portal](https://discord.com/developers/applications) で新しいアプリケーションを作成
2. 「Bot」タブでBotを追加し、トークンを控える
3. 「Privileged Gateway Intents」の **SERVER MEMBERS INTENT** をONにする（VCメンバーの解決に必要。Message Content Intentは不要）
4. 「OAuth2 → URL Generator」で scopes に `bot` と `applications.commands` を選択、権限に「メッセージを送信」「埋め込みリンク」を選択して生成されたURLからサーバーに招待

### 2. Steam Web APIキー取得

[https://steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey) からAPIキーを取得します。

### 3. 利用者側の準備

各メンバーはSteamのプロフィール設定で「プライバシー設定 → ゲームの詳細」を **公開** にしておく必要があります（非公開のままだと所持ゲームを取得できません）。

### 4. 環境構築

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# .env を編集して DISCORD_TOKEN / STEAM_API_KEY を設定
# 開発中は GUILD_ID も設定するとスラッシュコマンドが即座に反映される
```

### 5. 起動

```bash
source .venv/bin/activate
python bot.py
```

起動ログにコマンド同期の結果が表示されれば準備完了です。

## 使い方の流れ

1. 各メンバーが `/link <自分のSteamプロフィールURL>` を実行（例: `https://steamcommunity.com/id/xxxx`）
2. 紐づけ済みメンバーが2人以上ボイスチャンネルに入る
3. `/games` または `/pick` を実行

## 注意事項

- 所持ゲームのキャッシュは1時間、マルチプレイ判定のキャッシュは30日で更新されます
- Steamストアの非公式API（appdetails）を使ってマルチプレイ判定を行うため、レート制限を避けて1コマンドあたり新規判定は最大30件までに抑えています。初回実行時は一部タイトルが「未判定」として除外されることがありますが、次回以降のキャッシュ蓄積で解消されます

## デプロイ（Raspberry Pi / systemd）

本番運用は当面Raspberry Pi上でのsystemd常駐を想定しています。テンプレート一式は`deploy/`ディレクトリにまとまっています。

1. Pi上の任意のディレクトリ（以下`{{BOT_DIR}}`）にBotのコード一式（`bot.db`と`.env`を含む）を配置し、仮想環境を作って依存をインストールする

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. `deploy/discord-steam-bot.service`の`{{BOT_DIR}}`を実際の絶対パス（例: `/home/ryu/discord-steam-bot`）に置換し、`/etc/systemd/system/discord-steam-bot.service`に配置する
3. 有効化・起動する

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now discord-steam-bot.service
   journalctl -u discord-steam-bot -f   # ログ確認（起動ログにコマンド同期の結果が出れば準備完了）
   ```

**注意:** Pi上で既に別のsystemdユニット名・別の起動方式でBotが稼働している可能性があります。その場合はいきなり置き換えず、既存ユニットの内容と`deploy/discord-steam-bot.service`を見比べて差分を適用してください。Botのトークンは同一のため、新旧ユニットが同時に起動した状態（二重接続）にならないよう、切り替え時は旧ユニットを停止してから新ユニットを起動してください。

Stripe Webhookを外部（Stripe）から受けられるようにするには`deploy/cloudflare-tunnel.md`の手順でCloudflare Tunnelを設定してください。

## バックアップ（Litestream + R2）とリストア手順

`bot.db`（SQLite）は[Litestream](https://litestream.io/)でCloudflare R2へ継続的にレプリケーションします。設定テンプレートは`deploy/litestream.yml`、常駐用のsystemdユニットは`deploy/litestream.service`です。

### 導入

1. [Litestreamをインストール](https://litestream.io/install/)（Raspberry Pi向けのARMビルドあり）
2. `deploy/litestream.yml`の`{{BOT_DIR}}` `{{R2_BUCKET}}` `{{R2_ENDPOINT}}`を実際の値に置換し、`{{BOT_DIR}}/deploy/litestream.yml`に配置する
   （`access-key-id` / `secret-access-key`は`${R2_ACCESS_KEY_ID}` / `${R2_SECRET_ACCESS_KEY}`のまま、環境変数展開に任せる）
3. `deploy/litestream.env.example`を`{{BOT_DIR}}/deploy/litestream.env`としてコピーし、R2 APIトークンの`R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY`を実値に置換したうえで`chmod 600`する（このファイルはgit管理下に置かない）
4. `deploy/litestream.service`の`{{BOT_DIR}}`を置換し、`/etc/systemd/system/litestream.service`に配置する
5. 初回レプリケーションを手動で確認してから常駐化する

   ```bash
   # 動作確認（Ctrl+Cで停止）
   litestream replicate -config {{BOT_DIR}}/deploy/litestream.yml

   # 問題なければ常駐化
   sudo systemctl daemon-reload
   sudo systemctl enable --now litestream.service
   ```

### リストア

Pi本体の故障・SDカード破損などでbot.dbを失った場合の復元:

```bash
litestream restore -config {{BOT_DIR}}/deploy/litestream.yml -o {{BOT_DIR}}/bot.db {{BOT_DIR}}/bot.db
# Botを起動する前に一度停止しておくこと（discord-steam-bot.serviceがbot.dbを開いたままだと復元先と競合する）
```

### リストア訓練（定期的に実施すること）

バックアップが「取れているつもり」で実際には壊れている、というのを避けるため、本番とは別のディレクトリに定期的に復元して整合性を確認する。

```bash
mkdir -p /tmp/discord-steam-bot-restore-drill
litestream restore -config {{BOT_DIR}}/deploy/litestream.yml -o /tmp/discord-steam-bot-restore-drill/bot.db {{BOT_DIR}}/bot.db

# SQLite自体の整合性チェック
sqlite3 /tmp/discord-steam-bot-restore-drill/bot.db "PRAGMA integrity_check;"
# "ok" が返ればOK

# 主要テーブルに想定通りレコードがあるか目視確認（テーブル名はdb.pyのスキーマを参照）
sqlite3 /tmp/discord-steam-bot-restore-drill/bot.db ".tables"

rm -rf /tmp/discord-steam-bot-restore-drill
```

## 監視

healthchecks.ioを使った死活監視を導入済みです（詳細は`deploy/monitoring.md`）。`discord-steam-bot-heartbeat.timer`が5分おきに生存Pingを送り、`discord-steam-bot-notify-failure.service`が`discord-steam-bot.service`のクラッシュ時にOnFailure経由で即時通知します。

## 別ホストへの移行手順

Raspberry Piから別のホスト（将来的なVPS移行など。候補: WebARENA Indigo、さくらのVPS等）へ移す場合、基本的にはBotディレクトリ（コード一式 + `bot.db` + `.env`）をまるごと`rsync`で移して、依存をインストールし、systemdを有効化するだけです。

```bash
# 旧ホストでBotを一度停止（bot.dbの整合性を保つため）
ssh old-host "sudo systemctl stop discord-steam-bot litestream"

# コード一式 + bot.db + .env を新ホストへ転送
rsync -avz --exclude '.venv' --exclude '__pycache__' \
  old-host:{{BOT_DIR}}/ new-host:{{BOT_DIR}}/

# 新ホスト側
ssh new-host "cd {{BOT_DIR}} && python -m venv .venv && \
  .venv/bin/pip install -r requirements.txt"

# deploy/discord-steam-bot.service・litestream.service・（必要ならcloudflared.service）を配置し直し
ssh new-host "sudo systemctl daemon-reload && \
  sudo systemctl enable --now litestream.service discord-steam-bot.service"

# 旧ホストのユニットは無効化しておく
ssh old-host "sudo systemctl disable --now discord-steam-bot litestream"
```

`bot.db`を直接rsyncする代わりに、新ホストで`litestream restore`から復元する形でも移行できます（`bot.db`のrsync時にBotが書き込み中だと不整合の恐れがあるため、Litestream運用が定着していればこちらの方が安全）。移行後は旧ホストのcloudflaredトンネル設定（該当する場合）も新ホストに付け替えることを忘れないこと。
