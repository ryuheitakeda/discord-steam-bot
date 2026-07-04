"""stripe_webhook.py（Stripe Webhook受け口）のユニットテスト。

実Stripe APIへの通信は一切発生しない。`stripe.Webhook.construct_event` は
ローカルでのHMAC-SHA256署名検証とJSONパースのみを行うため、テスト用の
ペイロードとStripe公式の署名アルゴリズムに沿った署名ヘッダを自前で生成して検証する。

各テストは一時sqliteファイルを使い、既存の bot.db には一切触れない
（tests/test_premium.py と同様のtemp_dbフィクスチャ）。
"""

import hashlib
import hmac
import json
import time

import pytest
import pytest_asyncio
from aiohttp.test_utils import TestClient, TestServer

import db
import stripe_webhook

WEBHOOK_SECRET = "whsec_test_secret_1234567890"
GUILD_ID = "guild-999"


@pytest.fixture(autouse=True)
def _reset_seen_events():
    """stripe_webhookのイベント重複排除はモジュールレベルの状態を持つため、
    テストごとにリセットして「別テストの既定event_idと衝突→誤ってduplicate扱い」を防ぐ。
    """
    stripe_webhook._seen_event_ids.clear()
    stripe_webhook._seen_event_id_set.clear()
    yield


@pytest_asyncio.fixture
async def temp_db(tmp_path, monkeypatch):
    """テスト専用の一時DBファイルでdbモジュールを初期化するフィクスチャ。"""
    db_file = tmp_path / "test_bot.db"
    monkeypatch.setattr(db, "DB_PATH", str(db_file))
    await db.init_db()
    try:
        yield db
    finally:
        await db.close_db()


def _sign(payload: bytes, secret: str = WEBHOOK_SECRET, timestamp: int = None) -> str:
    """Stripe公式のWebhook署名アルゴリズムに沿ったStripe-Signatureヘッダ値を生成する。

    signed_payload = "{timestamp}.{payload}" をHMAC-SHA256(secret)で署名し、
    "t={timestamp},v1={signature}" の形式で返す（stripe._webhook.WebhookSignatureと同じ手順）。
    """
    ts = timestamp if timestamp is not None else int(time.time())
    signed_payload = f"{ts}.{payload.decode('utf-8')}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={signature}"


def _make_event_payload(event_type: str, data_object: dict, event_id: str = "evt_test_1") -> bytes:
    # 実際のStripeイベントは object="event" を持つ（stripe.Webhook.construct_event が
    # v2イベントとの判別にevent.objectを参照するため、テスト用ペイロードにも含める）。
    return json.dumps(
        {
            "id": event_id,
            "object": "event",
            "type": event_type,
            "data": {"object": data_object},
        }
    ).encode("utf-8")


async def _post_event(payload: bytes, sig_header: str):
    app = stripe_webhook.create_app(WEBHOOK_SECRET)
    async with TestClient(TestServer(app)) as client:
        resp = await client.post(
            stripe_webhook.WEBHOOK_PATH,
            data=payload,
            headers={"Stripe-Signature": sig_header, "Content-Type": "application/json"},
        )
        status = resp.status
        text = await resp.text()
    return status, text


# ---------- 署名検証 ----------

async def test_valid_signature_is_accepted(temp_db):
    payload = _make_event_payload("checkout.session.completed", {"client_reference_id": GUILD_ID})
    status, _ = await _post_event(payload, _sign(payload))
    assert status == 200


async def test_invalid_signature_is_rejected(temp_db):
    payload = _make_event_payload("checkout.session.completed", {"client_reference_id": GUILD_ID})
    bad_header = _sign(payload, secret="whsec_wrong_secret")
    status, _ = await _post_event(payload, bad_header)
    assert status == 400


async def test_missing_signature_header_is_rejected(temp_db):
    payload = _make_event_payload("checkout.session.completed", {"client_reference_id": GUILD_ID})
    status, _ = await _post_event(payload, "")
    assert status == 400


async def test_tampered_payload_is_rejected(temp_db):
    """署名生成後にペイロードを改ざんすると検証に失敗すること。"""
    payload = _make_event_payload("checkout.session.completed", {"client_reference_id": GUILD_ID})
    sig_header = _sign(payload)
    tampered = payload.replace(GUILD_ID.encode(), b"guild-attacker")
    status, _ = await _post_event(tampered, sig_header)
    assert status == 400


# ---------- checkout.session.completed ----------

async def test_checkout_completed_grants_entitlement_and_maps_subscription(temp_db):
    payload = _make_event_payload(
        "checkout.session.completed",
        {
            "client_reference_id": GUILD_ID,
            "subscription": "sub_abc123",
            "customer": "cus_xyz789",
        },
    )
    status, _ = await _post_event(payload, _sign(payload))
    assert status == 200

    entitlement = await db.get_active_entitlement("guild", GUILD_ID)
    assert entitlement is not None
    assert entitlement["plan"] == "premium"
    assert entitlement["source"] == "stripe"
    assert entitlement["expires_at"] is None

    mapped_guild = await db.get_guild_by_subscription("sub_abc123")
    assert mapped_guild == GUILD_ID


async def test_checkout_completed_without_client_reference_id_is_ignored(temp_db):
    payload = _make_event_payload(
        "checkout.session.completed",
        {"subscription": "sub_no_guild", "customer": "cus_xyz789"},
    )
    status, _ = await _post_event(payload, _sign(payload))
    assert status == 200  # イベント自体は受理するが、entitlementは作られない

    mapped_guild = await db.get_guild_by_subscription("sub_no_guild")
    assert mapped_guild is None


# ---------- customer.subscription.deleted ----------

async def test_subscription_deleted_revokes_entitlement(temp_db):
    # 事前にentitlementとsub↔guild対応を用意する
    await db.upsert_entitlement("guild", GUILD_ID, "premium", "stripe", None)
    await db.upsert_stripe_subscription("sub_abc123", GUILD_ID, "cus_xyz789", "active")

    payload = _make_event_payload(
        "customer.subscription.deleted",
        {"id": "sub_abc123", "customer": "cus_xyz789", "status": "canceled"},
    )
    status, _ = await _post_event(payload, _sign(payload))
    assert status == 200

    entitlement = await db.get_active_entitlement("guild", GUILD_ID)
    assert entitlement is None


async def test_subscription_deleted_for_unknown_subscription_is_noop(temp_db):
    payload = _make_event_payload(
        "customer.subscription.deleted",
        {"id": "sub_unknown", "customer": "cus_xyz789", "status": "canceled"},
    )
    status, _ = await _post_event(payload, _sign(payload))
    assert status == 200  # 未知のsubでもエラーにはならない


# ---------- customer.subscription.updated ----------

async def test_subscription_updated_to_inactive_revokes_entitlement(temp_db):
    await db.upsert_entitlement("guild", GUILD_ID, "premium", "stripe", None)
    await db.upsert_stripe_subscription("sub_abc123", GUILD_ID, "cus_xyz789", "active")

    payload = _make_event_payload(
        "customer.subscription.updated",
        {"id": "sub_abc123", "customer": "cus_xyz789", "status": "unpaid"},
    )
    status, _ = await _post_event(payload, _sign(payload))
    assert status == 200

    entitlement = await db.get_active_entitlement("guild", GUILD_ID)
    assert entitlement is None


async def test_subscription_updated_back_to_active_restores_entitlement(temp_db):
    await db.upsert_stripe_subscription("sub_abc123", GUILD_ID, "cus_xyz789", "past_due")

    payload = _make_event_payload(
        "customer.subscription.updated",
        {"id": "sub_abc123", "customer": "cus_xyz789", "status": "active"},
    )
    status, _ = await _post_event(payload, _sign(payload))
    assert status == 200

    entitlement = await db.get_active_entitlement("guild", GUILD_ID)
    assert entitlement is not None
    assert entitlement["source"] == "stripe"


async def test_subscription_updated_with_period_end_sets_expires_at(temp_db):
    await db.upsert_stripe_subscription("sub_abc123", GUILD_ID, "cus_xyz789", "trialing")
    period_end = int(time.time()) + 86400 * 5

    payload = _make_event_payload(
        "customer.subscription.updated",
        {
            "id": "sub_abc123",
            "customer": "cus_xyz789",
            "status": "trialing",
            "current_period_end": period_end,
        },
    )
    status, _ = await _post_event(payload, _sign(payload))
    assert status == 200

    entitlement = await db.get_active_entitlement("guild", GUILD_ID)
    assert entitlement is not None
    assert entitlement["expires_at"] == float(period_end)


# ---------- 未対応イベント・冪等性 ----------

async def test_unhandled_event_type_returns_200(temp_db):
    payload = _make_event_payload("invoice.payment_failed", {"id": "in_123"})
    status, _ = await _post_event(payload, _sign(payload))
    assert status == 200


async def test_duplicate_event_id_is_processed_once(temp_db):
    """同一event.idを複数回受け取っても、2回目以降はスキップされる（重複排除）。"""
    payload = _make_event_payload(
        "checkout.session.completed",
        {
            "client_reference_id": GUILD_ID,
            "subscription": "sub_dup",
            "customer": "cus_dup",
        },
        event_id="evt_duplicate_1",
    )
    sig_header = _sign(payload)

    app = stripe_webhook.create_app(WEBHOOK_SECRET)
    async with TestClient(TestServer(app)) as client:
        resp1 = await client.post(
            stripe_webhook.WEBHOOK_PATH,
            data=payload,
            headers={"Stripe-Signature": sig_header, "Content-Type": "application/json"},
        )
        text1 = await resp1.text()
        resp2 = await client.post(
            stripe_webhook.WEBHOOK_PATH,
            data=payload,
            headers={"Stripe-Signature": sig_header, "Content-Type": "application/json"},
        )
        text2 = await resp2.text()

    assert resp1.status == 200
    assert resp2.status == 200
    assert "duplicate" in text2
    assert "duplicate" not in text1
