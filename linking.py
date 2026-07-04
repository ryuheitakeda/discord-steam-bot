"""Steam紐づけ確定後の共通処理（DB保存・所持ゲーム取得・確認Embed生成）。"""

from typing import Optional, Union

import discord

import db
from i18n import t
from steam_api import SteamAPIError, SteamClient


async def finalize_link(
    steam: SteamClient,
    discord_id: str,
    steam_id: str,
    persona_name: str,
    locale: Optional[Union[discord.Locale, str]] = None,
) -> discord.Embed:
    """紐づけをDBに保存し、所持ゲームを取得した上で確認用Embedを組み立てる。"""
    await db.link_user(discord_id, steam_id, persona_name)

    embed = discord.Embed(
        title=t(locale, "link_finalize.embed_title"),
        description=f"**{persona_name}**",
        color=discord.Color.blurple(),
    )
    embed.add_field(name=t(locale, "common.field_steamid"), value=steam_id, inline=False)

    try:
        profile = await steam.get_profile(steam_id)
        if profile.avatar_url:
            embed.set_thumbnail(url=profile.avatar_url)

        if not profile.profile_visible:
            embed.add_field(
                name=t(locale, "common.warning_field_name"),
                value=t(locale, "link_finalize.private_profile_warning"),
                inline=False,
            )
            return embed

        games = await steam.get_owned_games(steam_id)
        if games:
            await db.store_owned_games(steam_id, games)
            embed.add_field(
                name=t(locale, "link_finalize.games_count_field"),
                value=t(locale, "link_finalize.games_count_value", count=len(games)),
                inline=False,
            )
        else:
            embed.add_field(
                name=t(locale, "common.warning_field_name"),
                value=t(locale, "link_finalize.zero_games_warning"),
                inline=False,
            )
    except SteamAPIError:
        # 紐づけ自体は成功させる。ゲーム取得は/games実行時に再試行される
        pass

    return embed
