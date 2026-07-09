# TODO — 残タスクリスト

最終更新: 2026-07-09（Stripeメール設定確認）

## 現状（完了済み）

- Bot本体＋フリーミアム＋i18n（ja/en）＋Stripe直販統合のコードは完成、テスト30件全パス
- Raspberry Pi上でsystemd 24時間稼働中（2026-07-04移行、`discord-steam-bot.service`）
- LP・法的4ページ（利用規約/プライバシー/特商法/返金）は `ryuteklabo.com` で本番公開済み、
  `support@ryuteklabo.com` のメール転送も動作確認済み
- Stripe Live mode切替完了（2026-07-06）＝実課金が有効な状態。
  実カードでのE2E（購入→付与→解約→剥奪→返金）も2026-07-06に成功済み（詳細は下記1.）

---

## 1. 課金の実地最終確認 — 最優先

- [x] **実カードでの少額E2E**（2026-07-06実施）：¥380決済 → プレミアム付与 → 解約 → 剥奪 → 返金の
      一連の流れを実カードで確認。以下の重要な発見・対応あり：
      - **本番バグを発見・修正**：Stripe Webhookエンドポイントが`customer.subscription.deleted`を
        購読しておらず（`checkout.session.completed`と`customer.subscription.updated`のみだった）、
        解約してもBotの剥奪処理が永久に走らない状態だった。ダッシュボードでイベント購読を追加して解消。
        `deploy/cloudflare-tunnel.md`には元々正しく3イベントとも記載されていたため、初回設定時の
        設定漏れだった可能性が高い（今後エンドポイントを作り直す際は同ドキュメントの記載を再確認すること）
      - Customer Portal経由の解約はデフォルトで「期間終了時解約」（`cancel_at_period_end`）であり、
        即時には剥奪されない仕様と判明（Stripeの標準挙動。バグではない）。剥奪の実地確認は
        Stripeダッシュボードから「今すぐキャンセル」を実行して検証した
      - 剥奪後、`entitlements`テーブルの該当行が削除され、Discord上の`/premium`も無料枠表示に戻ることを確認
      - 返金（¥380）もダッシュボード操作で正常に処理された
- [x] **Stripeの顧客向けメール設定の確認**（2026-07-09実施）：
      明細表記（statement descriptor）は`RYUTEKLABO.COM`で正しく設定済みだったが、以下は未設定/意図しない状態だったため修正：
      - 領収書の自動送信（決済成功時・返金時のメール）が**OFF**になっていたため両方ON化
      - メール送信のデフォルト言語が「英語」になっていたため「日本語」に変更
      - サポートメールの返信先が未設定で個人Gmail（ryutek0821@gmail.com）にフォールバックしていたため`support@ryuteklabo.com`に設定
      - ついでにCheckout/Payment Linksで顧客に表示される法的URL（プライバシーポリシー・利用規約・特定商取引法表記）も未入力だったため、
        `https://ryuteklabo.com/privacy` `/terms` `/tokushoho` を設定
- [x] **初売上が発生した際のWebhookログ監視の習慣づけ**（2026-07-09実施）：
      `deploy/monitoring.md`に「Stripe Webhookログの監視」セクションを追加。
      成功/異常系それぞれの正確なログ文言（`stripe_webhook.py`のログ出力から抽出）と、
      `journalctl -u discord-steam-bot`でのgrepコマンド、確認頻度の目安（軌道に乗るまでは決済都度、
      定常運用後は週1回）を明文化した

## 2. バックアップ・監視の実導入（Pi側）

- [x] **Litestream + Cloudflare R2 の実導入**（2026-07-06実施）
      R2バケット`discord-steam-bot-backup`を作成、R2 APIトークン（バケットスコープのRead/Write）を発行し
      `deploy/litestream.env`（Pi上のみ、`chmod 600`・git管理外）に格納。`litestream.yml`は
      `${R2_ACCESS_KEY_ID}`等の環境変数展開方式に変更（秘密情報を直書きしない）。
      Pi(aarch64/Debian trixie)にLitestream 0.5.13を導入し、`litestream.service`を常駐化・稼働確認済み
- [x] リストア訓練（README記載の手順で復元 → `PRAGMA integrity_check` = ok、`users`/`entitlements`等の
      テーブル存在を確認。2026-07-06に初回実施成功。以後は定期実施すること）
- [x] **死活監視の導入**（2026-07-06実施、案A）
      healthchecks.ioアカウント作成（マジックリンク方式、ryutek0821@gmail.com）→Check「discord-steam-bot heartbeat」
      作成（Period/Grace 10分）。`discord-steam-bot-heartbeat.timer`（5分おきにis-active確認してping）と
      `discord-steam-bot-notify-failure.service`（OnFailure経由でクラッシュ時に`/fail`通知）をPiに導入し稼働確認済み
      （Last Ping更新・`/fail`手動テスト共に成功）。通知は現状メールのみ有効化済み、Discord Webhook追加は保留
      （運営者が任意タイミングでhealthchecks.io「Integrations」から追加予定）

## 3. コード資産の保全

- [x] **gitリモートの設定**：GitHubプライベートリポジトリ `ryutek0821/discord-steam-bot` を作成しpush済み
      （`.env` / `bot.db` はignore済みで含まれていないことを確認）
- [x] `.gitignore` に `.claude/` `.serena/` を追加（現在untrackedのまま）

## 4. ドキュメントの実態合わせ

- [x] README.md / README.en.md の更新：
      タイトルを正式名称「今日なんのゲームする？Bot」に変更。
      `/premium`コマンド・フリーミアム制限（3回/日・60回/月）・`/grant` `/revoke`・i18n対応を追記
- [x] systemdユニット名の不一致解消：
      Pi実機の`discord-steam-bot.service`に統一（`deploy/steambot.service`を`deploy/discord-steam-bot.service`にリネームし、README・monitoring.md内の参照も追従）

## 5. 公開・集客

- [ ] Discord Developer PortalでPublic Bot設定と招待URL権限（`permissions=19456`）が
      LP記載のURLと一致しているか最終確認（`deploy/cloudflare-pages.md` のチェックリスト残項目）
- [ ] 集客チャネルの着手：top.gg等のBotリストサイト掲載、Discord App Directory申請の検討
- [ ] （中期）サーバー数が増えたら100サーバー到達前にBot Verification申請（本人確認が必要）
- [ ] `support@ryuteklabo.com` 宛て問い合わせの応答フロー決め（受信確認は済み、返信運用のみ）

## 6. 事業・税務

- [ ] 開業届（屋号RyuTekLabo）・青色申告承認申請の検討（売上が立ち始める前に方針を決めておく）
- [ ] Stripe売上・手数料のfreee記帳フロー整備（freee連携は接続済み、勘定科目のルール決めから）
