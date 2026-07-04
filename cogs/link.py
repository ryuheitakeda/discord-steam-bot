"""Steamアカウント紐づけ関連コマンド（/link /unlink /profile）。"""

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import db
import linking
from steam_api import SteamAPIError


class LinkCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @property
    def steam(self):
        return self.bot.steam_client

    @app_commands.command(
        name="link",
        description="自分のSteamアカウントを紐づけます（プロフィールURL / SteamID64 / カスタムURL名）",
    )
    @app_commands.describe(steam="例: https://steamcommunity.com/id/xxxx")
    async def link(self, interaction: discord.Interaction, steam: str):
        await interaction.response.defer(ephemeral=True)

        try:
            steam_id = await self.steam.resolve_to_steamid64(steam)
            profile = await self.steam.get_profile(steam_id)
        except SteamAPIError as e:
            await interaction.followup.send(f"❌ {e}", ephemeral=True)
            return

        embed = await linking.finalize_link(
            self.steam, str(interaction.user.id), steam_id, profile.persona_name
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="unlink", description="Steamアカウントの紐づけを解除します")
    async def unlink(self, interaction: discord.Interaction):
        removed = await db.unlink_user(str(interaction.user.id))
        if removed:
            await interaction.response.send_message("✅ 紐づけを解除しました。", ephemeral=True)
        else:
            await interaction.response.send_message("紐づけは登録されていません。", ephemeral=True)

    @app_commands.command(name="profile", description="Steam連携状況を確認します")
    @app_commands.describe(user="確認したいユーザー（省略時は自分）")
    async def profile(
        self, interaction: discord.Interaction, user: Optional[discord.User] = None
    ):
        target = user or interaction.user
        row = await db.get_user(str(target.id))
        if row is None:
            await interaction.response.send_message(
                f"{target.mention} はまだSteamアカウントを紐づけていません。", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"{target.display_name} のSteam連携",
            description=f"**{row['persona_name']}**",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="SteamID64", value=row["steam_id"], inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=(user is None))


async def setup(bot: commands.Bot):
    await bot.add_cog(LinkCog(bot))
