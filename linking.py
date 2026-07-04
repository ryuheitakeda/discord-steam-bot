"""Steam紐づけ確定後の共通処理（DB保存・所持ゲーム取得・確認Embed生成）。"""

import discord

import db
from steam_api import SteamAPIError, SteamClient


async def finalize_link(
    steam: SteamClient, discord_id: str, steam_id: str, persona_name: str
) -> discord.Embed:
    """紐づけをDBに保存し、所持ゲームを取得した上で確認用Embedを組み立てる。"""
    await db.link_user(discord_id, steam_id, persona_name)

    embed = discord.Embed(
        title="Steamアカウントを紐づけました",
        description=f"**{persona_name}**",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="SteamID64", value=steam_id, inline=False)

    try:
        profile = await steam.get_profile(steam_id)
        if profile.avatar_url:
            embed.set_thumbnail(url=profile.avatar_url)

        if not profile.profile_visible:
            embed.add_field(
                name="⚠️ 注意",
                value=(
                    "プロフィールが非公開になっているようです。\n"
                    "Steamの「プライバシー設定」で「ゲームの詳細」を公開にしないと、"
                    "所持ゲームを取得できません。"
                ),
                inline=False,
            )
            return embed

        games = await steam.get_owned_games(steam_id)
        if games:
            await db.store_owned_games(steam_id, games)
            embed.add_field(name="所持ゲーム数", value=f"{len(games)}本", inline=False)
        else:
            embed.add_field(
                name="⚠️ 注意",
                value=(
                    "所持ゲームが0件、または「ゲームの詳細」の公開設定が"
                    "オフになっている可能性があります。"
                ),
                inline=False,
            )
    except SteamAPIError:
        # 紐づけ自体は成功させる。ゲーム取得は/games実行時に再試行される
        pass

    return embed
