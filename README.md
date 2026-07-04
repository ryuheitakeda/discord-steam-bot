# Discord × Steam VC Bot

Discordのボイスチャンネルに集まったメンバーの共通所持Steamゲームから、「今日一緒にやれるゲーム」を提案するBotです。

## できること

- `/link <steam>` — 自分のSteamプロフィールURL（またはSteamID64 / カスタムURL名）を紐づけ
- `/unlink` — 紐づけ解除
- `/profile [user]` — 紐づけ状況の確認
- `/games [all]` — 今VCにいるメンバーの共通所持ゲームからマルチプレイ対応タイトルを上位10件表示（`all:True`で絞り込みなし）
- `/pick [all]` — 上記の中からランダムに1本を提案

`/link` は自分のSteamプロフィールURL/IDを貼ってもらう方式です。他人のURLを貼っても紐づく先はそのURLが指す（＝貼った本人ではない）Steamアカウントになるだけで、貼った本人には何のメリットもない（＝なりすましの動機がない）ため、Discord OAuth2連携のような外部ドメインを経由する仕組みは使わず、シンプルな自己申告方式にしています。

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
