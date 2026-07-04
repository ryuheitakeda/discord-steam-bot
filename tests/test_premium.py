"""premium.py（クォータエンジン）のユニットテスト。

各テストは一時sqliteファイルを使い、既存の bot.db には一切触れない。
db.py はモジュールレベルのグローバル接続 (_db) を持つため、テストごとに
init_db / close_db でセットアップ・クリーンアップする。
"""

import time

import pytest_asyncio

import db
import premium

GUILD_ID = "guild-123"


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


async def _insert_usage_at(guild_id: str, used_at: float, count: int, command: str = "games") -> None:
    """指定時刻のusage_logレコードをcount件直接INSERTする（時刻境界テスト用）。"""
    conn = db._conn()
    for i in range(count):
        await conn.execute(
            "INSERT INTO usage_log (guild_id, user_id, command, used_at) VALUES (?, ?, ?, ?)",
            (guild_id, f"user-{i}", command, used_at),
        )
    await conn.commit()


async def test_daily_limit_blocks_after_three_uses(temp_db):
    """無料ギルドで3回利用後、4回目のcheck_quotaはallowed=Falseになる（日次上限）。"""
    for _ in range(3):
        await premium.record_use(GUILD_ID, "user-1", "games")

    result = await premium.check_quota(GUILD_ID)

    assert result.allowed is False
    assert result.is_premium is False


async def test_retry_after_is_positive(temp_db):
    """上限超過時のretry_afterは正の値を返す。"""
    for _ in range(3):
        await premium.record_use(GUILD_ID, "user-1", "games")

    result = await premium.check_quota(GUILD_ID)

    assert result.allowed is False
    assert result.retry_after is not None
    assert result.retry_after > 0


async def test_entitlement_grants_unlimited_access(temp_db):
    """entitlement付与後は上限に達していてもcheck_quotaがallowed=True, is_premium=Trueになる。"""
    for _ in range(3):
        await premium.record_use(GUILD_ID, "user-1", "games")

    # 付与前は制限されていることを確認
    blocked = await premium.check_quota(GUILD_ID)
    assert blocked.allowed is False

    await db.upsert_entitlement("guild", GUILD_ID, "premium", "manual", None)

    result = await premium.check_quota(GUILD_ID)

    assert result.allowed is True
    assert result.is_premium is True


async def test_daily_rolling_window_boundary(temp_db):
    """25時間前の利用は日次(24h)ウィンドウから外れ、再びallowed=Trueとなる。"""
    now = time.time()
    await _insert_usage_at(GUILD_ID, now - 90000, count=3)  # 25時間前 = 90000秒前

    result = await premium.check_quota(GUILD_ID)

    assert result.allowed is True
    assert result.is_premium is False


async def test_retry_after_matches_longer_window_when_both_exceeded(temp_db):
    """日次(3)と月次(60)を両方超過させた場合、retry_afterは月次側（より長い方）に一致する。"""
    now = time.time()
    # 全レコードを「たった今」記録すると、日次ウィンドウ・月次ウィンドウ両方が超過する。
    # 各ウィンドウのretry_afterは (最古行 + window - now) なので、同一時刻なら
    # 日次≈86400秒、月次≈2592000秒となり、max()が月次側を返すはず。
    await _insert_usage_at(GUILD_ID, now, count=60)

    result = await premium.check_quota(GUILD_ID)

    assert result.allowed is False
    assert result.retry_after is not None
    # 月次ウィンドウ(30日=2592000秒)側に一致（日次24h=86400秒より大きい）
    assert result.retry_after > 86400
    assert abs(result.retry_after - 86400 * 30) < 60


async def test_monthly_limit_boundary(temp_db):
    """日次ウィンドウ外だが月次(30日)ウィンドウ内に60回の利用があれば月次上限で拒否される。"""
    now = time.time()
    # 25時間前（日次ウィンドウの外）だが30日以内、月次上限60に到達させる
    await _insert_usage_at(GUILD_ID, now - 90000, count=60)

    result = await premium.check_quota(GUILD_ID)

    assert result.allowed is False
    assert result.is_premium is False
    assert result.retry_after is not None
    assert result.retry_after > 0
