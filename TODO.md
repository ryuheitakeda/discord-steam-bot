# TODO — 残タスクリスト

最終更新: 2026-07-06（Stripe Live mode切替当日の棚卸し）

## 現状（完了済み）

- Bot本体＋フリーミアム＋i18n（ja/en）＋Stripe直販統合のコードは完成、テスト30件全パス
- Raspberry Pi上でsystemd 24時間稼働中（2026-07-04移行、`discord-steam-bot.service`）
- LP・法的4ページ（利用規約/プライバシー/特商法/返金）は `ryuteklabo.com` で本番公開済み、
  `support@ryuteklabo.com` のメール転送も動作確認済み
- Stripe Live mode切替完了（2026-07-06）＝実課金が有効な状態。
  テストモードのE2E（購入→付与→解約→剥奪）は成功済み

---

## 1. 課金の実地最終確認 — 最優先

- [ ] **実カードでの少額E2E**（¥380決済 → プレミアム付与 → Customer Portalで解約 → 剥奪 → Stripeから返金）
      ※現在「ユーザー判断で保留」。未実施のまま初の実顧客が来るとその人がテスター役になるため早めに推奨
- [ ] Stripeの顧客向けメール設定の確認（領収書の自動送信、明細に表示される事業者名「RyuTekLabo」）
- [ ] 初売上が発生した際のWebhookログ監視の習慣づけ（`journalctl -u discord-steam-bot`）

## 2. バックアップ・監視の実導入（Pi側）

- [ ] **Litestream + Cloudflare R2 の実導入**
      テンプレート（`deploy/litestream.yml` / `litestream.service`）は作成済みだが実導入の記録なし。
      R2バケット作成 → 設定の実値化 → 常駐化。課金開始後は `bot.db`（課金状態・ユーザー紐づけ）の消失が実害になる
- [ ] リストア訓練（README記載の手順で復元 → `PRAGMA integrity_check` 確認。定期実施）
- [ ] **死活監視の導入**
      `deploy/monitoring.md` は方式提示のみで未導入。まず案A
      （healthchecks.io + systemd OnFailure + is-activeタイマー、Discord通知連携）から
- ※ 上記2点は2026-07-06時点で「未導入」前提。Pi実機で導入済みと確認できたら消し込むこと

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
