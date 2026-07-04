"""Discord × Steam「今日一緒にやるゲーム」Bot エントリポイント。"""

import logging
import os
from typing import Optional

import aiohttp
import discord
from aiohttp import web
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

import db
import stripe_webhook
from steam_api import SteamClient
from translator import LocaleTranslator

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
STEAM_API_KEY = os.getenv("STEAM_API_KEY")
GUILD_ID = os.getenv("GUILD_ID")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
STRIPE_WEBHOOK_PORT = int(os.getenv("STRIPE_WEBHOOK_PORT", "8080"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("discord-steam-bot")

INITIAL_EXTENSIONS = ["cogs.link", "cogs.games", "cogs.premium"]


class SteamVCBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.voice_states = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)
        self.http_session: Optional[aiohttp.ClientSession] = None
        self.steam_client: Optional[SteamClient] = None
        self.stripe_webhook_runner: Optional[web.AppRunner] = None

    async def setup_hook(self):
        if not STEAM_API_KEY:
            raise RuntimeError("STEAM_API_KEYが設定されていません（.envを確認してください）")

        await db.init_db()
        self.http_session = aiohttp.ClientSession()
        self.steam_client = SteamClient(STEAM_API_KEY, self.http_session)

        for ext in INITIAL_EXTENSIONS:
            await self.load_extension(ext)

        await self.tree.set_translator(LocaleTranslator())

        if STRIPE_WEBHOOK_SECRET:
            self.stripe_webhook_runner = await stripe_webhook.start_webhook_server(
                STRIPE_WEBHOOK_SECRET, STRIPE_WEBHOOK_PORT
            )
            logger.info(
                "Stripe Webhookサーバーを起動しました (127.0.0.1:%d%s)",
                STRIPE_WEBHOOK_PORT,
                stripe_webhook.WEBHOOK_PATH,
            )
        else:
            logger.info("Stripe webhook無効（未設定）")

        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info(
                "ギルド限定でコマンドを同期しました（%d件、guild_id=%s）", len(synced), GUILD_ID
            )
        else:
            synced = await self.tree.sync()
            logger.info(
                "グローバルにコマンドを同期しました（%d件、反映まで最大1時間程度）", len(synced)
            )

    async def close(self):
        await super().close()
        if self.stripe_webhook_runner is not None:
            await self.stripe_webhook_runner.cleanup()
        if self.http_session is not None:
            await self.http_session.close()
        await db.close_db()

    async def on_ready(self):
        logger.info("ログインしました: %s (ID: %s)", self.user, self.user.id)


def main():
    if not DISCORD_TOKEN:
        raise RuntimeError("DISCORD_TOKENが設定されていません（.envを確認してください）")

    bot = SteamVCBot()
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
