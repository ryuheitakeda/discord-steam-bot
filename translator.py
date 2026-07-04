"""スラッシュコマンドのdescription/パラメータ説明をlocalesから翻訳するTranslator実装。

コマンド名（name）自体はDiscordの制約回避のため英語固定で翻訳対象外。
description・パラメータ説明のみ `app_commands.locale_str("<localesのキー>")` として
埋め込まれ、ここでlocalesの内容に翻訳する。
"""

from __future__ import annotations

from typing import Optional

from discord import app_commands
from discord.app_commands import TranslationContextTypes, locale_str
from discord.enums import Locale

import i18n


class LocaleTranslator(app_commands.Translator):
    """`locale_str`のmessageをlocalesのキーとして扱い、翻訳結果を返すTranslator。"""

    async def translate(
        self,
        string: locale_str,
        locale: Locale,
        context: TranslationContextTypes,
    ) -> Optional[str]:
        key = string.message
        if not i18n.has_key(key):
            # locales未登録のキー（通常の文字列がlocale_str化された場合など）は翻訳しない
            return None
        return i18n.t(locale, key)
