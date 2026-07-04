"""VCメンバーの共通所持ゲームから今日遊べるゲームを提案するコマンド（/games /pick）。"""

import logging
import random
from dataclasses import dataclass
from typing import Optional, Union

import discord
from discord import app_commands
from discord.app_commands import locale_str
from discord.ext import commands

import db
import premium
from i18n import normalize_locale, t
from steam_api import MAX_NEW_CATEGORY_FETCHES_PER_CALL, SteamAPIError

logger = logging.getLogger("discord-steam-bot.games")

CANDIDATE_POOL_SIZE = 60
DISPLAY_LIMIT = 10


def _format_duration(locale: Optional[Union[discord.Locale, str]], seconds: float) -> str:
    """秒数を「N時間M分」形式の人間可読文字列に変換する（ロケール対応）。"""
    total_minutes = max(1, int(seconds // 60))
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return t(locale, "duration.hours_minutes", hours=hours, minutes=minutes)
    if hours:
        return t(locale, "duration.hours_only", hours=hours)
    return t(locale, "duration.minutes_only", minutes=minutes)


def _build_upsell_embed(
    locale: Optional[Union[discord.Locale, str]], quota: "premium.QuotaResult"
) -> discord.Embed:
    """無料枠を使い切った際に表示するアップセルEmbedを構築する。

    quota.reasonは言語非依存のキー（例: "quota_exceeded"）。ここ（表示層）でt()して翻訳する。
    """
    title_key = f"quota.{quota.reason}" if quota.reason else "quota.quota_exceeded"
    embed = discord.Embed(
        title=t(locale, title_key),
        color=discord.Color.orange(),
    )
    if quota.retry_after is not None:
        embed.description = t(
            locale, "games.upsell_retry", duration=_format_duration(locale, quota.retry_after)
        )
    else:
        embed.description = t(locale, "games.upsell_retry_unknown")

    embed.add_field(
        name=t(locale, "games.upsell_field_name"),
        value=t(locale, "games.upsell_field_value", price=premium.PRICE_STRIPE),
        inline=False,
    )
    return embed


@dataclass
class GameCandidate:
    appid: int
    name: str
    playtime_forever: int  # 全メンバー合計（分）
    playtime_2weeks: int  # 全メンバー合計（分、直近2週間）


@dataclass
class PipelineResult:
    candidates: list[GameCandidate]
    unlinked_names: list[str]
    private_names: list[str]
    category_limit_hit: bool


class GamesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @property
    def steam(self):
        return self.bot.steam_client

    async def _collect_member_games(
        self, members: list[discord.Member]
    ) -> tuple[dict[str, list[dict]], list[str], list[str]]:
        """VCメンバーごとの所持ゲームを取得する。

        戻り値は (discord_id -> 所持ゲーム一覧, 未紐づけメンバー名一覧, 取得不可メンバー名一覧)。
        """
        member_games: dict[str, list[dict]] = {}
        unlinked_names: list[str] = []
        private_names: list[str] = []

        for member in members:
            row = await db.get_user(str(member.id))
            if row is None:
                unlinked_names.append(member.display_name)
                continue

            steam_id = row["steam_id"]
            cached = await db.get_cached_owned_games(steam_id)
            if cached is None:
                try:
                    fetched = await self.steam.get_owned_games(steam_id)
                except SteamAPIError:
                    private_names.append(member.display_name)
                    continue
                await db.store_owned_games(steam_id, fetched)
                games = fetched
            else:
                games = [dict(r) for r in cached]

            if not games:
                private_names.append(member.display_name)
                continue

            member_games[str(member.id)] = games

        return member_games, unlinked_names, private_names

    @staticmethod
    def _build_candidates(member_games: dict[str, list[dict]]) -> list[GameCandidate]:
        game_lists = list(member_games.values())
        common_appids = set(g["appid"] for g in game_lists[0])
        for games in game_lists[1:]:
            common_appids &= set(g["appid"] for g in games)

        candidates: dict[int, GameCandidate] = {}
        for games in game_lists:
            for g in games:
                if g["appid"] not in common_appids:
                    continue
                c = candidates.get(g["appid"])
                if c is None:
                    candidates[g["appid"]] = GameCandidate(
                        appid=g["appid"],
                        name=g["name"],
                        playtime_forever=g["playtime_forever"],
                        playtime_2weeks=g["playtime_2weeks"],
                    )
                else:
                    c.playtime_forever += g["playtime_forever"]
                    c.playtime_2weeks += g["playtime_2weeks"]

        result = list(candidates.values())
        result.sort(key=lambda c: (c.playtime_2weeks, c.playtime_forever), reverse=True)
        return result

    async def _filter_multiplayer(
        self, candidates: list[GameCandidate]
    ) -> tuple[list[GameCandidate], bool]:
        pool = candidates[:CANDIDATE_POOL_SIZE]
        filtered: list[GameCandidate] = []
        new_fetches = 0
        limit_hit = False

        for c in pool:
            cached = await db.get_cached_category(c.appid)
            if cached is not None:
                if cached["is_multiplayer"]:
                    filtered.append(c)
                continue

            if new_fetches >= MAX_NEW_CATEGORY_FETCHES_PER_CALL:
                limit_hit = True
                continue

            new_fetches += 1
            try:
                name, is_multiplayer = await self.steam.get_app_multiplayer_info(c.appid)
            except SteamAPIError:
                continue
            await db.store_category(c.appid, name, is_multiplayer)
            if is_multiplayer:
                filtered.append(c)

        return filtered, limit_hit

    @staticmethod
    def _add_notes(
        locale: Optional[Union[discord.Locale, str]],
        embed: discord.Embed,
        result: PipelineResult,
    ) -> None:
        separator = "、" if normalize_locale(locale) == "ja" else ", "
        notes = []
        if result.unlinked_names:
            notes.append(
                t(locale, "games.note_unlinked", names=separator.join(result.unlinked_names))
            )
        if result.private_names:
            notes.append(
                t(locale, "games.note_private", names=separator.join(result.private_names))
            )
        if result.category_limit_hit:
            notes.append(t(locale, "games.note_category_limit"))
        if notes:
            embed.set_footer(text=" / ".join(notes))

    async def _resolve_voice_channel(
        self, interaction: discord.Interaction
    ) -> Optional[discord.VoiceChannel]:
        """実行者が入っているVCを取得する。キャッシュで見つからない場合はREST APIで再確認する。"""
        member = interaction.user
        voice_state = member.voice if isinstance(member, discord.Member) else None
        if voice_state is not None and voice_state.channel is not None:
            return voice_state.channel

        guild = interaction.guild
        logger.warning(
            "キャッシュからVC状態を取得できませんでした: user=%s member_type=%s "
            "guild_id=%s botのギルドキャッシュに存在=%s",
            member.id,
            type(member).__name__,
            interaction.guild_id,
            interaction.guild_id is not None
            and self.bot.get_guild(interaction.guild_id) is not None,
        )
        if guild is None:
            return None

        try:
            data = await self.bot.http.get_voice_state(guild.id, member.id)
        except discord.HTTPException as e:
            logger.warning("REST APIでのVC状態取得にも失敗しました: %s", e)
            return None

        channel_id = data.get("channel_id")
        if channel_id is None:
            return None
        channel = guild.get_channel(int(channel_id))
        logger.info(
            "REST APIでVC状態を取得しました: channel_id=%s キャッシュ解決=%s",
            channel_id,
            channel is not None,
        )
        return channel if isinstance(channel, discord.VoiceChannel) else None

    async def _run_pipeline(
        self, interaction: discord.Interaction, all_flag: bool
    ) -> Optional[PipelineResult]:
        locale = interaction.locale
        channel = await self._resolve_voice_channel(interaction)
        if channel is None:
            await interaction.followup.send(
                t(locale, "games.error_no_voice_channel"),
                ephemeral=True,
            )
            return None

        vc_members = [m for m in channel.members if not m.bot]
        member_games, unlinked_names, private_names = await self._collect_member_games(
            vc_members
        )

        if len(member_games) < 2:
            await interaction.followup.send(
                t(locale, "games.error_need_two_members"),
                ephemeral=True,
            )
            return None

        candidates = self._build_candidates(member_games)
        category_limit_hit = False
        if not all_flag:
            candidates, category_limit_hit = await self._filter_multiplayer(candidates)

        if not candidates:
            reason_key = "games.reason_all" if all_flag else "games.reason_multiplayer"
            await interaction.followup.send(
                t(locale, "games.no_candidates", reason=t(locale, reason_key)),
                ephemeral=True,
            )
            return None

        return PipelineResult(candidates, unlinked_names, private_names, category_limit_hit)

    @app_commands.command(
        name="games", description=locale_str("games.command_description")
    )
    @app_commands.guild_only()
    @app_commands.describe(all=locale_str("games.param_all_description"))
    async def games(self, interaction: discord.Interaction, all: bool = False):
        await interaction.response.defer()
        locale = interaction.locale

        quota = await premium.check_quota(str(interaction.guild_id))
        if not quota.allowed:
            await interaction.followup.send(
                embed=_build_upsell_embed(locale, quota), ephemeral=True
            )
            return

        result = await self._run_pipeline(interaction, all)
        if result is None:
            return

        lines = []
        for i, c in enumerate(result.candidates[:DISPLAY_LIMIT], start=1):
            url = f"https://store.steampowered.com/app/{c.appid}"
            hours = c.playtime_forever / 60
            total_hours = t(locale, "games.total_hours", hours=f"{hours:.1f}")
            lines.append(f"**{i}. [{c.name}]({url})** — {total_hours}")

        title = t(locale, "games.title_all" if all else "games.title_default")
        embed = discord.Embed(
            title=title, description="\n".join(lines), color=discord.Color.green()
        )
        self._add_notes(locale, embed, result)
        await interaction.followup.send(embed=embed)
        await premium.record_use(str(interaction.guild_id), str(interaction.user.id), "games")

    @app_commands.command(
        name="pick", description=locale_str("pick.command_description")
    )
    @app_commands.guild_only()
    @app_commands.describe(all=locale_str("pick.param_all_description"))
    async def pick(self, interaction: discord.Interaction, all: bool = False):
        await interaction.response.defer()
        locale = interaction.locale

        quota = await premium.check_quota(str(interaction.guild_id))
        if not quota.allowed:
            await interaction.followup.send(
                embed=_build_upsell_embed(locale, quota), ephemeral=True
            )
            return

        result = await self._run_pipeline(interaction, all)
        if result is None:
            return

        choice = random.choice(result.candidates)
        url = f"https://store.steampowered.com/app/{choice.appid}"
        embed = discord.Embed(
            title=t(locale, "pick.title"),
            description=f"**[{choice.name}]({url})**",
            color=discord.Color.gold(),
        )
        embed.set_image(
            url=f"https://cdn.cloudflare.steamstatic.com/steam/apps/{choice.appid}/header.jpg"
        )
        self._add_notes(locale, embed, result)
        await interaction.followup.send(embed=embed)
        await premium.record_use(str(interaction.guild_id), str(interaction.user.id), "pick")


async def setup(bot: commands.Bot):
    await bot.add_cog(GamesCog(bot))
