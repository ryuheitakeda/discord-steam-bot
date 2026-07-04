"""Steamアカウント紐づけ関連コマンド（/link /unlink /profile）。"""

from typing import Optional

import discord
from discord import app_commands
from discord.app_commands import locale_str
from discord.ext import commands

import db
import linking
from i18n import t
from steam_api import SteamAPIError


class LinkCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @property
    def steam(self):
        return self.bot.steam_client

    @app_commands.command(
        name="link",
        description=locale_str("link.command_description"),
    )
    @app_commands.describe(steam=locale_str("link.param_steam_description"))
    async def link(self, interaction: discord.Interaction, steam: str):
        await interaction.response.defer(ephemeral=True)

        try:
            steam_id = await self.steam.resolve_to_steamid64(steam)
            profile = await self.steam.get_profile(steam_id)
        except SteamAPIError as e:
            await interaction.followup.send(
                t(interaction.locale, "link.error", error=e), ephemeral=True
            )
            return

        embed = await linking.finalize_link(
            self.steam,
            str(interaction.user.id),
            steam_id,
            profile.persona_name,
            interaction.locale,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="unlink", description=locale_str("unlink.command_description"))
    async def unlink(self, interaction: discord.Interaction):
        removed = await db.unlink_user(str(interaction.user.id))
        if removed:
            await interaction.response.send_message(
                t(interaction.locale, "unlink.success"), ephemeral=True
            )
        else:
            await interaction.response.send_message(
                t(interaction.locale, "unlink.not_linked"), ephemeral=True
            )

    @app_commands.command(name="profile", description=locale_str("profile.command_description"))
    @app_commands.describe(user=locale_str("profile.param_user_description"))
    async def profile(
        self, interaction: discord.Interaction, user: Optional[discord.User] = None
    ):
        target = user or interaction.user
        row = await db.get_user(str(target.id))
        if row is None:
            await interaction.response.send_message(
                t(interaction.locale, "profile.not_linked", mention=target.mention),
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=t(interaction.locale, "profile.embed_title", display_name=target.display_name),
            description=f"**{row['persona_name']}**",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name=t(interaction.locale, "common.field_steamid"),
            value=row["steam_id"],
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=(user is None))


async def setup(bot: commands.Bot):
    await bot.add_cog(LinkCog(bot))
