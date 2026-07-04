"""Stripe Webhookの受け口（aiohttp.webによる軽量HTTPサーバー）。

Stripe直販サブスクリプションの決済完了・解約・状態変更イベントを受け取り、
`db.entitlements`（source="stripe"）と `db.stripe_subscriptions`（sub↔guild対応）
を更新する。bot.py の setup_hook から `start_webhook_server` で起動し、
close時に AppRunner.cleanup() で停止する想定（Cloudflare Tunnel等でこの
ローカルポートに外部からのWebhookをつなぐ）。

署名検証は必須。`Stripe-Signature` ヘッダを `stripe.Webhook.construct_event`
で検証し、失敗したリクエストは全て400を返す（実Stripe APIへの通信は発生しない。
construct_eventはローカルでのHMAC検証とJSONパースのみ）。
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import stripe
from aiohttp import web

import db

logger = logging.getLogger("discord-steam-bot.stripe_webhook")

WEBHOOK_PATH = "/stripe/webhook"

PLAN_PREMIUM = "premium"
SOURCE_STRIPE = "stripe"

# 有効（entitlementを持たせるべき）とみなすsubscriptionステータス
ACTIVE_STATUSES = {"active", "trialing"}

# 直近処理済みイベントIDの簡易的な重複排除（プロセス内メモリのみ。再起動でクリアされるが、
# Stripeの再送は短時間に集中するため実用上十分）。
_MAX_SEEN_EVENTS = 1000
_seen_event_ids: list[str] = []
_seen_event_id_set: set[str] = set()


def _mark_event_seen(event_id: Optional[str]) -> bool:
    """イベントIDを処理済みとして記録する。既に処理済みならFalse（=スキップすべき）を返す。"""
    if not event_id:
        return True  # IDが取れない場合は常に処理する
    if event_id in _seen_event_id_set:
        return False
    _seen_event_id_set.add(event_id)
    _seen_event_ids.append(event_id)
    if len(_seen_event_ids) > _MAX_SEEN_EVENTS:
        oldest = _seen_event_ids.pop(0)
        _seen_event_id_set.discard(oldest)
    return True


async def _handle_checkout_completed(data_object: dict[str, Any]) -> None:
    """checkout.session.completed: 決済完了時にentitlementを付与する。

    client_reference_id（/premium発行時にguild_idを埋め込んでいる）でギルドを特定する。
    """
    guild_id = data_object.get("client_reference_id")
    subscription_id = data_object.get("subscription")
    customer_id = data_object.get("customer")

    if not guild_id:
        logger.warning(
            "checkout.session.completed: client_reference_id(guild_id)が無いイベントを無視します"
        )
        return

    guild_id = str(guild_id)
    await db.upsert_entitlement("guild", guild_id, PLAN_PREMIUM, SOURCE_STRIPE, None)

    if subscription_id:
        await db.upsert_stripe_subscription(
            str(subscription_id),
            guild_id,
            str(customer_id) if customer_id else None,
            "active",
        )

    logger.info(
        "Stripe決済完了によりプレミアムを付与しました: guild_id=%s subscription_id=%s",
        guild_id,
        subscription_id,
    )


async def _handle_subscription_deleted(data_object: dict[str, Any]) -> None:
    """customer.subscription.deleted: 解約時にentitlementを剥奪する。"""
    subscription_id = data_object.get("id")
    if not subscription_id:
        return
    subscription_id = str(subscription_id)

    guild_id = await db.get_guild_by_subscription(subscription_id)
    if guild_id is None:
        logger.warning(
            "customer.subscription.deleted: 対応するguildが見つかりません (subscription_id=%s)",
            subscription_id,
        )
        return

    await db.delete_entitlement("guild", guild_id, SOURCE_STRIPE)
    customer_id = data_object.get("customer")
    await db.upsert_stripe_subscription(
        subscription_id, guild_id, str(customer_id) if customer_id else None, "canceled"
    )

    logger.info(
        "Stripeサブスク解約によりプレミアムを剥奪しました: guild_id=%s subscription_id=%s",
        guild_id,
        subscription_id,
    )


async def _handle_subscription_updated(data_object: dict[str, Any]) -> None:
    """customer.subscription.updated: ステータス変化に応じてentitlementを付与/剥奪する。"""
    subscription_id = data_object.get("id")
    if not subscription_id:
        return
    subscription_id = str(subscription_id)

    guild_id = await db.get_guild_by_subscription(subscription_id)
    if guild_id is None:
        logger.warning(
            "customer.subscription.updated: 対応するguildが見つかりません (subscription_id=%s)",
            subscription_id,
        )
        return

    status = data_object.get("status")
    customer_id = data_object.get("customer")
    current_period_end = data_object.get("current_period_end")

    await db.upsert_stripe_subscription(
        subscription_id,
        guild_id,
        str(customer_id) if customer_id else None,
        str(status) if status else None,
    )

    if status in ACTIVE_STATUSES:
        expires_at = float(current_period_end) if current_period_end else None
        await db.upsert_entitlement("guild", guild_id, PLAN_PREMIUM, SOURCE_STRIPE, expires_at)
    else:
        await db.delete_entitlement("guild", guild_id, SOURCE_STRIPE)

    logger.info(
        "Stripeサブスク更新を反映しました: guild_id=%s subscription_id=%s status=%s",
        guild_id,
        subscription_id,
        status,
    )


EVENT_HANDLERS = {
    "checkout.session.completed": _handle_checkout_completed,
    "customer.subscription.deleted": _handle_subscription_deleted,
    "customer.subscription.updated": _handle_subscription_updated,
}


def create_app(webhook_secret: str) -> web.Application:
    """Stripe Webhook用のaiohttp.web.Applicationを構築する。"""

    async def handle_webhook(request: web.Request) -> web.Response:
        payload = await request.read()
        sig_header = request.headers.get("Stripe-Signature", "")

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except (ValueError, stripe.SignatureVerificationError) as exc:
            logger.warning("Stripe Webhookの署名検証に失敗しました: %s", exc)
            return web.Response(status=400, text="invalid signature")

        event_dict = event.to_dict()
        event_id = event_dict.get("id")

        if not _mark_event_seen(event_id):
            logger.info("Stripeイベントの重複を検知しスキップします: event_id=%s", event_id)
            return web.Response(status=200, text="ok (duplicate)")

        event_type = event_dict.get("type")
        data_object = (event_dict.get("data") or {}).get("object") or {}

        handler = EVENT_HANDLERS.get(event_type)
        if handler is not None:
            try:
                await handler(data_object)
            except Exception:
                logger.exception(
                    "Stripeイベント処理中にエラーが発生しました: event_type=%s", event_type
                )
                # Stripe側の自動リトライに任せるため5xxを返す
                return web.Response(status=500, text="internal error")
        else:
            logger.info("未対応のStripeイベントを無視します: %s", event_type)

        return web.Response(status=200, text="ok")

    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, handle_webhook)
    return app


async def start_webhook_server(
    webhook_secret: str, port: int, host: str = "127.0.0.1"
) -> web.AppRunner:
    """Webhookサーバーを起動し、AppRunnerを返す（呼び出し側がcleanup()で停止すること）。"""
    app = create_app(webhook_secret)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    return runner
