"""SQLiteスキーマ定義とデータアクセスヘルパー。"""

import time
from contextlib import asynccontextmanager
from typing import Optional

import aiosqlite

DB_PATH = "bot.db"

# キャッシュの有効期限（秒）
OWNED_GAMES_TTL = 60 * 60          # 1時間
APP_CATEGORY_TTL = 60 * 60 * 24 * 30  # 30日

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    discord_id TEXT PRIMARY KEY,
    steam_id TEXT NOT NULL,
    persona_name TEXT NOT NULL,
    linked_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS owned_games (
    steam_id TEXT NOT NULL,
    appid INTEGER NOT NULL,
    name TEXT NOT NULL,
    playtime_forever INTEGER NOT NULL DEFAULT 0,
    playtime_2weeks INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (steam_id, appid)
);

CREATE TABLE IF NOT EXISTS fetch_meta (
    steam_id TEXT PRIMARY KEY,
    fetched_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS app_categories (
    appid INTEGER PRIMARY KEY,
    name TEXT,
    is_multiplayer INTEGER,
    fetched_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS usage_log (
    guild_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    command TEXT NOT NULL,
    used_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_usage_guild_time ON usage_log (guild_id, used_at);

CREATE TABLE IF NOT EXISTS entitlements (
    subject_type TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    plan TEXT NOT NULL,
    source TEXT NOT NULL,
    expires_at REAL,
    PRIMARY KEY (subject_type, subject_id, source)
);

CREATE TABLE IF NOT EXISTS stripe_subscriptions (
    subscription_id TEXT PRIMARY KEY,
    guild_id TEXT NOT NULL,
    customer_id TEXT,
    status TEXT,
    updated_at REAL NOT NULL
);
"""

_db: Optional[aiosqlite.Connection] = None


async def init_db() -> None:
    """DB接続を開き、テーブルが無ければ作成する。"""
    global _db
    _db = await aiosqlite.connect(DB_PATH)
    await _db.executescript(SCHEMA)
    await _db.commit()


async def close_db() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None


def _conn() -> aiosqlite.Connection:
    if _db is None:
        raise RuntimeError("DBが初期化されていません。init_db()を先に呼んでください。")
    return _db


# ---------- users ----------

async def link_user(discord_id: str, steam_id: str, persona_name: str) -> None:
    await _conn().execute(
        """INSERT INTO users (discord_id, steam_id, persona_name, linked_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(discord_id) DO UPDATE SET
               steam_id=excluded.steam_id,
               persona_name=excluded.persona_name,
               linked_at=excluded.linked_at""",
        (discord_id, steam_id, persona_name, time.time()),
    )
    await _conn().commit()


async def unlink_user(discord_id: str) -> bool:
    cur = await _conn().execute("DELETE FROM users WHERE discord_id = ?", (discord_id,))
    await _conn().commit()
    return cur.rowcount > 0


async def get_user(discord_id: str) -> Optional[aiosqlite.Row]:
    _conn().row_factory = aiosqlite.Row
    cur = await _conn().execute(
        "SELECT * FROM users WHERE discord_id = ?", (discord_id,)
    )
    return await cur.fetchone()


# ---------- owned_games ----------

async def get_cached_owned_games(steam_id: str) -> Optional[list[aiosqlite.Row]]:
    """キャッシュが有効期限内ならその所持ゲーム一覧を返す。無ければNone。"""
    _conn().row_factory = aiosqlite.Row
    cur = await _conn().execute(
        "SELECT fetched_at FROM fetch_meta WHERE steam_id = ?", (steam_id,)
    )
    row = await cur.fetchone()
    if row is None or (time.time() - row["fetched_at"]) > OWNED_GAMES_TTL:
        return None

    cur = await _conn().execute(
        "SELECT appid, name, playtime_forever, playtime_2weeks FROM owned_games WHERE steam_id = ?",
        (steam_id,),
    )
    return await cur.fetchall()


async def store_owned_games(steam_id: str, games: list[dict]) -> None:
    """所持ゲーム一覧をキャッシュに保存する（既存分は洗い替え）。"""
    conn = _conn()
    await conn.execute("DELETE FROM owned_games WHERE steam_id = ?", (steam_id,))
    await conn.executemany(
        """INSERT INTO owned_games (steam_id, appid, name, playtime_forever, playtime_2weeks)
           VALUES (?, ?, ?, ?, ?)""",
        [
            (
                steam_id,
                g["appid"],
                g["name"],
                g.get("playtime_forever", 0),
                g.get("playtime_2weeks", 0),
            )
            for g in games
        ],
    )
    await conn.execute(
        """INSERT INTO fetch_meta (steam_id, fetched_at) VALUES (?, ?)
           ON CONFLICT(steam_id) DO UPDATE SET fetched_at=excluded.fetched_at""",
        (steam_id, time.time()),
    )
    await conn.commit()


# ---------- app_categories ----------

async def get_cached_category(appid: int) -> Optional[aiosqlite.Row]:
    """キャッシュが有効期限内ならカテゴリ判定結果を返す。無ければNone。"""
    _conn().row_factory = aiosqlite.Row
    cur = await _conn().execute(
        "SELECT * FROM app_categories WHERE appid = ?", (appid,)
    )
    row = await cur.fetchone()
    if row is None or (time.time() - row["fetched_at"]) > APP_CATEGORY_TTL:
        return None
    return row


async def store_category(appid: int, name: str, is_multiplayer: bool) -> None:
    await _conn().execute(
        """INSERT INTO app_categories (appid, name, is_multiplayer, fetched_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(appid) DO UPDATE SET
               name=excluded.name,
               is_multiplayer=excluded.is_multiplayer,
               fetched_at=excluded.fetched_at""",
        (appid, name, int(is_multiplayer), time.time()),
    )
    await _conn().commit()


# ---------- usage_log ----------

async def record_usage(guild_id: str, user_id: str, command: str) -> None:
    """コマンド利用ログを1件記録する。"""
    await _conn().execute(
        "INSERT INTO usage_log (guild_id, user_id, command, used_at) VALUES (?, ?, ?, ?)",
        (guild_id, user_id, command, time.time()),
    )
    await _conn().commit()


async def count_usage_since(guild_id: str, since_ts: float) -> int:
    """指定ギルドで since_ts 以降に記録された利用回数を返す。"""
    cur = await _conn().execute(
        "SELECT COUNT(*) FROM usage_log WHERE guild_id = ? AND used_at >= ?",
        (guild_id, since_ts),
    )
    row = await cur.fetchone()
    return row[0] if row is not None else 0


async def oldest_usage_since(guild_id: str, since_ts: float) -> Optional[float]:
    """指定ギルドで since_ts 以降に記録された利用の中で最も古い used_at を返す。無ければNone。"""
    cur = await _conn().execute(
        "SELECT MIN(used_at) FROM usage_log WHERE guild_id = ? AND used_at >= ?",
        (guild_id, since_ts),
    )
    row = await cur.fetchone()
    return row[0] if row is not None else None


# ---------- entitlements ----------

async def upsert_entitlement(
    subject_type: str,
    subject_id: str,
    plan: str,
    source: str,
    expires_at: Optional[float],
) -> None:
    """entitlementを付与・更新する（subject_type, subject_id, sourceが同じ場合は上書き）。"""
    await _conn().execute(
        """INSERT INTO entitlements (subject_type, subject_id, plan, source, expires_at)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(subject_type, subject_id, source) DO UPDATE SET
               plan=excluded.plan,
               expires_at=excluded.expires_at""",
        (subject_type, subject_id, plan, source, expires_at),
    )
    await _conn().commit()


async def delete_entitlement(subject_type: str, subject_id: str, source: str) -> bool:
    """指定sourceのentitlementを削除する。削除できればTrue。"""
    cur = await _conn().execute(
        "DELETE FROM entitlements WHERE subject_type = ? AND subject_id = ? AND source = ?",
        (subject_type, subject_id, source),
    )
    await _conn().commit()
    return cur.rowcount > 0


async def get_active_entitlement(
    subject_type: str, subject_id: str
) -> Optional[aiosqlite.Row]:
    """有効なentitlement（無期限、または期限内）を1件返す。無ければNone。"""
    _conn().row_factory = aiosqlite.Row
    cur = await _conn().execute(
        """SELECT * FROM entitlements
           WHERE subject_type = ? AND subject_id = ?
             AND (expires_at IS NULL OR expires_at > ?)
           ORDER BY expires_at IS NULL DESC, expires_at DESC
           LIMIT 1""",
        (subject_type, subject_id, time.time()),
    )
    return await cur.fetchone()


async def list_entitlements(subject_type: str, subject_id: str) -> list[aiosqlite.Row]:
    """該当subjectの全entitlementを返す。"""
    _conn().row_factory = aiosqlite.Row
    cur = await _conn().execute(
        "SELECT * FROM entitlements WHERE subject_type = ? AND subject_id = ?",
        (subject_type, subject_id),
    )
    return await cur.fetchall()


# ---------- stripe_subscriptions ----------

async def upsert_stripe_subscription(
    subscription_id: str,
    guild_id: str,
    customer_id: Optional[str],
    status: Optional[str],
) -> None:
    """Stripeのsubscription_idとguild_idの対応を保存・更新する（Webhookでのguild逆引き用）。"""
    await _conn().execute(
        """INSERT INTO stripe_subscriptions
               (subscription_id, guild_id, customer_id, status, updated_at)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(subscription_id) DO UPDATE SET
               guild_id=excluded.guild_id,
               customer_id=excluded.customer_id,
               status=excluded.status,
               updated_at=excluded.updated_at""",
        (subscription_id, guild_id, customer_id, status, time.time()),
    )
    await _conn().commit()


async def get_guild_by_subscription(subscription_id: str) -> Optional[str]:
    """subscription_idから対応するguild_idを引く。登録が無ければNone。"""
    cur = await _conn().execute(
        "SELECT guild_id FROM stripe_subscriptions WHERE subscription_id = ?",
        (subscription_id,),
    )
    row = await cur.fetchone()
    return row[0] if row is not None else None
