# 死活監視

Bot（`discord-steam-bot.service`）が落ちたこと・再起動を繰り返していることに気づけるように、
[healthchecks.io](https://healthchecks.io/)（無料枠）へのハートビートPingを軸にした監視を導入している（案Aを採用、2026-07-06）。

## 導入済みの構成

- healthchecks.ioにCheck「discord-steam-bot heartbeat」を作成（Period 10分 / Grace 10分）
- `deploy/discord-steam-bot-heartbeat.service` + `.timer`：5分おきに`systemctl is-active`を確認し、
  activeならhealthchecks.ioへping（プロセスの外形的な生存監視）
- `deploy/discord-steam-bot-notify-failure.service`：`discord-steam-bot.service`が失敗した際に
  `OnFailure=`経由で起動され、healthchecks.ioへ`/fail`通知（クラッシュ・Restart上限到達の即時検知）
- 通知先: healthchecks.io側の設定でメール（`ryutek0821@gmail.com`）を有効化済み。
  Discord Webhook連携は「Integrations」から任意タイミングで追加可能（未設定の場合はメールのみ）

以下は各案の設計メモ（導入時の判断材料として残す）。

healthchecks.ioでの準備:

1. アカウント作成 → 「Checks」→「Add Check」で新規チェックを作成
2. 「Period」（想定Ping間隔）と「Grace」（遅延許容時間）を設定
   （例: 案Aなら5分ごとの起動監視相当、案Bなら「Bot内の送信間隔＋α」）
3. 発行されるPing URL（`{{HEALTHCHECK_URL}}`、形式は `https://hc-ping.com/<uuid>`）を控える
4. 「Integrations」からDiscord Webhook等の通知先を追加しておくと、Ping途絶時に自動でアラートが飛ぶ

## 案A: systemdのOnFailureでcurl通知

`discord-steam-bot.service`が失敗（クラッシュしRestart上限に達した、等）した際に、systemdのOnFailure機構で
別ユニットを起動し、そこからcurlでPing（またはDiscord Webhook）を送る方式。Bot本体のコード変更が不要。

`/etc/systemd/system/discord-steam-bot-notify-failure.service` の例:

```ini
[Unit]
Description=Notify on discord-steam-bot.service failure

[Service]
Type=oneshot
ExecStart=/usr/bin/curl -fsS -m 10 --retry 3 https://hc-ping.com/{{HEALTHCHECK_URL}}/fail
```

`discord-steam-bot.service` の `[Service]` セクションに以下を追記して紐づける:

```ini
OnFailure=discord-steam-bot-notify-failure.service
```

これは「落ちたときだけ通知する」設計であり、healthchecks.io側の定期Pingとは別に
Discord Webhookへ直接POSTする通知（下記参照）と組み合わせるのが分かりやすい。

補足: 「起動していること」自体を定期的に確認したい場合は、Pi側にcron/systemd timerで
`systemctl is-active --quiet discord-steam-bot.service && curl -fsS -m 10 https://hc-ping.com/{{HEALTHCHECK_URL}}`
を数分おきに実行するタイマーユニットを別途組むことでも案Aと同等の効果が得られる
（Bot自体の生存だけでなくプロセスの死活を外形的に見る形）。

## 案B: Bot内で定期的にcurl {{HEALTHCHECK_URL}}

Bot（`bot.py`のイベントループ）内から、discord.pyの`tasks.loop`等で定期的に
`{{HEALTHCHECK_URL}}` へGET/POSTするタスクを追加する方式。Botプロセス自体が
（Discordゲートウェイに接続できているか等も含めて）生きていることをより直接的に確認できる
反面、Bot本体へのコード変更が必要（今回のタスクでは実装しない。実装する場合の方針のみ提示）。

イメージ（実装例。今回は追加しない）:

```python
from discord.ext import tasks

@tasks.loop(minutes=5)
async def heartbeat():
    async with bot.http_session.get("{{HEALTHCHECK_URL}}") as resp:
        pass  # ステータスは気にせずベストエフォートで送るだけでよい
```

`on_ready`や`setup_hook`内で`heartbeat.start()`を呼ぶ形になる。案Aと違い、
「プロセスは生きているがDiscordから切断されたまま」のような状態も検知しやすい
（heartbeatタスク自体をゲートウェイ接続後のみ動かす設計にする場合）。

## Discord Webhook通知の例

healthchecks.ioの「Integrations」からDiscordを選び、通知先のWebhook URLを登録すれば、
Ping途絶時に自動でDiscordチャンネルへアラートが飛ぶ（healthchecks.io側の機能なので追加実装不要）。

自前でDiscord Webhookに直接通知したい場合（例: 案Aのfail通知を直接Discordにも飛ばす）は、
`discord-steam-bot-notify-failure.service`のExecStartを以下のように並べるか、シェルスクリプトにまとめる:

```bash
curl -fsS -m 10 --retry 3 https://hc-ping.com/{{HEALTHCHECK_URL}}/fail
curl -fsS -m 10 -H "Content-Type: application/json" \
  -d '{"content": "⚠️ discord-steam-bot.service が失敗しました（Pi）"}' \
  {{DISCORD_WEBHOOK_URL}}
```

`{{DISCORD_WEBHOOK_URL}}`はDiscordのチャンネル設定「連携サービス→Webhook」で発行できるURL。

## まとめ（比較）

| | 案A（systemd OnFailure） | 案B（Bot内定期curl） |
|---|---|---|
| 実装箇所 | systemdユニットのみ（Bot本体は無改修） | `bot.py`等にタスク追加が必要 |
| 検知できる範囲 | プロセスのクラッシュ／Restart上限到達 | プロセス生存＋（設計次第で）Discord接続状態 |
| 導入の手軽さ | 高い（今すぐ導入可能） | Bot改修のレビュー・デプロイが必要 |
| 推奨 | まずは案Aで導入し、必要になれば案Bを追加 | — |
