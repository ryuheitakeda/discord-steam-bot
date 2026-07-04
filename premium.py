"""フリーミアム化のためのクォータエンジン（無料枠のローリングウィンドウ制限とプレミアム判定）。"""

import time
from dataclasses import dataclass
from typing import Optional

import db

# ローリングウィンドウ制限: (window_seconds, max_count) のリスト。全ウィンドウを満たす必要がある。
FREE_LIMITS = [(86400, 3), (86400 * 30, 60)]  # 3回/日 かつ 60回/月

PRICE_DISCORD = "$2.99/月"   # Discord公式課金（日本payout未対応のため現状UI非表示。対応後に再開）
PRICE_STRIPE = "¥380/月"     # Stripe直販（現行の唯一の課金チャネル）


@dataclass
class QuotaResult:
    allowed: bool
    is_premium: bool
    retry_after: Optional[float] = None  # 制限に達した場合、最も近い解除までの秒数
    reason: Optional[str] = None  # 言語非依存のキー（例: "quota_exceeded"）。表示側でt()して翻訳する


async def check_quota(guild_id: str) -> QuotaResult:
    """ギルドが現在コマンドを実行できるか判定する。

    プレミアム（entitlement有効）なら無制限で許可する。
    無料の場合はFREE_LIMITSの各ローリングウィンドウを満たしているか確認し、
    いずれかのウィンドウで上限に達していれば拒否する。
    """
    entitlement = await db.get_active_entitlement("guild", guild_id)
    if entitlement is not None:
        return QuotaResult(allowed=True, is_premium=True)

    now = time.time()
    retry_afters: list[float] = []
    for window, limit in FREE_LIMITS:
        since_ts = now - window
        count = await db.count_usage_since(guild_id, since_ts)
        if count >= limit:
            oldest = await db.oldest_usage_since(guild_id, since_ts)
            if oldest is not None:
                retry_afters.append(max(0.0, (oldest + window) - now))

    if retry_afters:
        # 複数ウィンドウ超過時は最も遅く解除されるウィンドウに合わせる（全ウィンドウがクリアされるまで解禁されないため）
        return QuotaResult(
            allowed=False,
            is_premium=False,
            retry_after=max(retry_afters),
            # reasonはUI表示用の言語非依存キー（localesのquota.<reason>で表示側が翻訳する）。
            # ロジック層に言語を持ち込まないための設計。
            reason="quota_exceeded",
        )

    return QuotaResult(allowed=True, is_premium=False)


async def record_use(guild_id: str, user_id: str, command: str) -> None:
    """コマンドの利用実績を記録する（クォータは成功時のみ消費する設計のため、成功時にのみ呼ぶこと）。"""
    await db.record_usage(guild_id, user_id, command)
