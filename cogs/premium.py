"""プレミアム状態の確認・付与・剥奪コマンド（/premium /grant /revoke）。"""

import time
from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.app_commands import locale_str
from discord.ext import commands

import db
import premium as premium_module
from i18n import t


class PremiumCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="premium", description=locale_str("premium.command_description"))
    @app_commands.guild_only()
    async def premium(self, interaction: discord.Interaction):
        locale = interaction.locale
        guild_id = str(interaction.guild_id)
        entitlement = await db.get_active_entitlement("guild", guild_id)

        if entitlement is not None:
            expires_at = entitlement["expires_at"]
            expires_text = (
                t(locale, "premium.expires_indefinite")
                if expires_at is None
                else discord.utils.format_dt(
                    datetime.fromtimestamp(expires_at, tz=timezone.utc), style="f"
                )
            )
            embed = discord.Embed(
                title=t(locale, "premium.embed_title_active"),
                color=discord.Color.gold(),
            )
            embed.add_field(
                name=t(locale, "premium.field_plan"), value=entitlement["plan"], inline=True
            )
            embed.add_field(
                name=t(locale, "premium.field_source"), value=entitlement["source"], inline=True
            )
            embed.add_field(
                name=t(locale, "premium.field_expires"), value=expires_text, inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        now = time.time()
        lines = []
        for window, limit in premium_module.FREE_LIMITS:
            since_ts = now - window
            count = await db.count_usage_since(guild_id, since_ts)
            days = window / 86400
            label = (
                t(locale, "premium.window_days", days=int(days))
                if days >= 1
                else t(locale, "premium.window_seconds", seconds=int(window))
            )
            lines.append(t(locale, "premium.usage_line", label=label, count=count, limit=limit))

        embed = discord.Embed(
            title=t(locale, "premium.embed_title_free"),
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name=t(locale, "premium.upgrade_field_name"),
            value=t(locale, "premium.upgrade_field_value", price=premium_module.PRICE_STRIPE),
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="grant", description=locale_str("grant.command_description"))
    @app_commands.describe(
        days=locale_str("grant.param_days_description"),
        guild_id=locale_str("common.param_guild_id_description"),
    )
    async def grant(
        self,
        interaction: discord.Interaction,
        days: Optional[int] = None,
        guild_id: Optional[str] = None,
    ):
        locale = interaction.locale
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message(
                t(locale, "common.owner_only_error"), ephemeral=True
            )
            return

        target_guild_id = guild_id or str(interaction.guild_id)
        expires_at = None if days is None else time.time() + days * 86400

        await db.upsert_entitlement("guild", target_guild_id, "premium", "manual", expires_at)

        expires_text = (
            t(locale, "premium.expires_indefinite")
            if expires_at is None
            else t(locale, "grant.expires_in_days", days=days)
        )
        await interaction.response.send_message(
            t(
                locale,
                "grant.success",
                guild_id=target_guild_id,
                expires_text=expires_text,
            ),
            ephemeral=True,
        )

    @app_commands.command(name="revoke", description=locale_str("revoke.command_description"))
    @app_commands.describe(guild_id=locale_str("common.param_guild_id_description"))
    async def revoke(
        self,
        interaction: discord.Interaction,
        guild_id: Optional[str] = None,
    ):
        locale = interaction.locale
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message(
                t(locale, "common.owner_only_error"), ephemeral=True
            )
            return

        target_guild_id = guild_id or str(interaction.guild_id)
        removed = await db.delete_entitlement("guild", target_guild_id, "manual")

        if removed:
            await interaction.response.send_message(
                t(locale, "revoke.success", guild_id=target_guild_id),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                t(locale, "revoke.not_found", guild_id=target_guild_id),
                ephemeral=True,
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(PremiumCog(bot))
