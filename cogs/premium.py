"""プレミアム状態の確認・付与・剥奪コマンド（/premium /grant /revoke）。"""

import time
from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import db
import premium as premium_module


class PremiumCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="premium", description="このサーバーのプレミアム状況を確認します")
    @app_commands.guild_only()
    async def premium(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        entitlement = await db.get_active_entitlement("guild", guild_id)

        if entitlement is not None:
            expires_at = entitlement["expires_at"]
            expires_text = (
                "無期限"
                if expires_at is None
                else discord.utils.format_dt(
                    datetime.fromtimestamp(expires_at, tz=timezone.utc), style="f"
                )
            )
            embed = discord.Embed(
                title="⭐ プレミアム有効",
                color=discord.Color.gold(),
            )
            embed.add_field(name="プラン", value=entitlement["plan"], inline=True)
            embed.add_field(name="付与元", value=entitlement["source"], inline=True)
            embed.add_field(name="期限", value=expires_text, inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        now = time.time()
        lines = []
        for window, limit in premium_module.FREE_LIMITS:
            since_ts = now - window
            count = await db.count_usage_since(guild_id, since_ts)
            days = window / 86400
            label = f"{int(days)}日間" if days >= 1 else f"{int(window)}秒間"
            lines.append(f"- {label}: {count}/{limit} 回")

        embed = discord.Embed(
            title="無料プラン利用状況",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="プレミアムのご案内",
            value=(
                "プレミアム（月額）に登録すると回数制限なくご利用いただけます。\n"
                f"料金: {premium_module.PRICE_STRIPE}\n"
                "（課金導線は今後のアップデートで追加予定です）"
            ),
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="grant", description="【オーナー限定】サーバーにプレミアムを付与します")
    @app_commands.describe(
        days="有効日数（省略時は無期限）",
        guild_id="対象サーバーID（省略時は実行サーバー）",
    )
    async def grant(
        self,
        interaction: discord.Interaction,
        days: Optional[int] = None,
        guild_id: Optional[str] = None,
    ):
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message(
                "❌ このコマンドはBotオーナーのみ実行できます。", ephemeral=True
            )
            return

        target_guild_id = guild_id or str(interaction.guild_id)
        expires_at = None if days is None else time.time() + days * 86400

        await db.upsert_entitlement("guild", target_guild_id, "premium", "manual", expires_at)

        expires_text = "無期限" if expires_at is None else f"{days}日後"
        await interaction.response.send_message(
            f"✅ サーバー `{target_guild_id}` にプレミアムを付与しました（期限: {expires_text}）。",
            ephemeral=True,
        )

    @app_commands.command(name="revoke", description="【オーナー限定】サーバーの手動付与プレミアムを剥奪します")
    @app_commands.describe(guild_id="対象サーバーID（省略時は実行サーバー）")
    async def revoke(
        self,
        interaction: discord.Interaction,
        guild_id: Optional[str] = None,
    ):
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message(
                "❌ このコマンドはBotオーナーのみ実行できます。", ephemeral=True
            )
            return

        target_guild_id = guild_id or str(interaction.guild_id)
        removed = await db.delete_entitlement("guild", target_guild_id, "manual")

        if removed:
            await interaction.response.send_message(
                f"✅ サーバー `{target_guild_id}` の手動付与プレミアムを剥奪しました。",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"サーバー `{target_guild_id}` に手動付与のプレミアムは登録されていません。",
                ephemeral=True,
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(PremiumCog(bot))
