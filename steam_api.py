"""Steam Web API / ストアAPIのクライアント。スロットル・リトライを内蔵する。"""

import asyncio
import re
import time
from dataclasses import dataclass
from typing import Optional

import aiohttp

STEAM_API_BASE = "https://api.steampowered.com"
STORE_API_BASE = "https://store.steampowered.com/api/appdetails"

# マルチプレイ系とみなすSteamストアカテゴリID
# 1: Multi-player, 9: Co-op, 20: MMO, 27: Cross-Platform Multiplayer,
# 36: Online PvP, 38: Online Co-op, 49: PvP
MULTIPLAYER_CATEGORY_IDS = {1, 9, 20, 27, 36, 38, 49}

# ストアAPIは非公式のレート制限があるため間隔を空けて呼ぶ
STORE_API_MIN_INTERVAL = 1.5
MAX_NEW_CATEGORY_FETCHES_PER_CALL = 30


class SteamAPIError(Exception):
    """Steam APIとの通信で回復不能なエラーが起きたときに送出する。"""


@dataclass
class SteamProfile:
    steam_id: str
    persona_name: str
    avatar_url: str
    profile_visible: bool


class SteamClient:
    def __init__(self, api_key: str, session: aiohttp.ClientSession):
        self._api_key = api_key
        self._session = session
        self._store_lock = asyncio.Lock()
        self._last_store_call = 0.0

    async def _get_json(self, url: str, params: dict, *, retries: int = 1) -> dict:
        last_error: Optional[Exception] = None
        for attempt in range(retries + 1):
            try:
                async with self._session.get(
                    url, params=params, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    if resp.status in (429, 500, 502, 503, 504) and attempt < retries:
                        await asyncio.sleep(1.0 + attempt)
                        continue
                    raise SteamAPIError(f"Steam APIエラー（HTTP {resp.status}）")
            except asyncio.TimeoutError as e:
                last_error = e
                if attempt < retries:
                    await asyncio.sleep(1.0)
                    continue
                raise SteamAPIError("Steam APIへの接続がタイムアウトしました") from e
            except aiohttp.ClientError as e:
                last_error = e
                if attempt < retries:
                    await asyncio.sleep(1.0)
                    continue
                raise SteamAPIError(f"Steam APIへの接続に失敗しました: {e}") from e
        raise SteamAPIError("Steam APIエラー") from last_error

    @staticmethod
    def parse_steam_input(raw: str) -> tuple[str, str]:
        """入力文字列を (種別, 値) に正規化する。種別は 'steamid64' または 'vanity'。"""
        raw = raw.strip()
        m = re.search(r"steamcommunity\.com/profiles/(\d{17})", raw)
        if m:
            return "steamid64", m.group(1)
        m = re.search(r"steamcommunity\.com/id/([^/\s?]+)", raw)
        if m:
            return "vanity", m.group(1)
        if re.fullmatch(r"\d{17}", raw):
            return "steamid64", raw
        return "vanity", raw

    async def resolve_to_steamid64(self, raw: str) -> str:
        kind, value = self.parse_steam_input(raw)
        if kind == "steamid64":
            return value
        data = await self._get_json(
            f"{STEAM_API_BASE}/ISteamUser/ResolveVanityURL/v1/",
            {"key": self._api_key, "vanityurl": value},
        )
        result = data.get("response", {})
        if result.get("success") != 1:
            raise SteamAPIError(f"「{raw}」に一致するSteamアカウントが見つかりませんでした")
        return result["steamid"]

    async def get_profile(self, steam_id: str) -> SteamProfile:
        data = await self._get_json(
            f"{STEAM_API_BASE}/ISteamUser/GetPlayerSummaries/v2/",
            {"key": self._api_key, "steamids": steam_id},
        )
        players = data.get("response", {}).get("players", [])
        if not players:
            raise SteamAPIError("Steamプロフィールが見つかりませんでした")
        p = players[0]
        return SteamProfile(
            steam_id=steam_id,
            persona_name=p.get("personaname", "unknown"),
            avatar_url=p.get("avatarfull", ""),
            profile_visible=p.get("communityvisibilitystate") == 3,
        )

    async def get_owned_games(self, steam_id: str) -> list[dict]:
        data = await self._get_json(
            f"{STEAM_API_BASE}/IPlayerService/GetOwnedGames/v1/",
            {
                "key": self._api_key,
                "steamid": steam_id,
                "include_appinfo": 1,
                "include_played_free_games": 1,
            },
        )
        games = data.get("response", {}).get("games", [])
        return [
            {
                "appid": g["appid"],
                "name": g.get("name", f"App {g['appid']}"),
                "playtime_forever": g.get("playtime_forever", 0),
                "playtime_2weeks": g.get("playtime_2weeks", 0),
            }
            for g in games
        ]

    async def get_app_multiplayer_info(self, appid: int) -> tuple[str, bool]:
        """appdetails APIでカテゴリを取得し、(ゲーム名, マルチプレイ対応か) を返す。"""
        async with self._store_lock:
            wait = STORE_API_MIN_INTERVAL - (time.monotonic() - self._last_store_call)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_store_call = time.monotonic()
            data = await self._get_json(
                STORE_API_BASE,
                {"appids": appid, "filters": "categories,name", "l": "japanese"},
                retries=1,
            )
        entry = data.get(str(appid))
        if not entry or not entry.get("success"):
            raise SteamAPIError(f"appid={appid} のストア情報取得に失敗しました")
        info = entry["data"]
        categories = {c["id"] for c in info.get("categories", [])}
        is_multiplayer = bool(categories & MULTIPLAYER_CATEGORY_IDS)
        name = info.get("name", f"App {appid}")
        return name, is_multiplayer
