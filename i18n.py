"""多言語化（i18n）ヘルパー。

`locales/*.json` を起動時に読み込み、`t(locale, key, **kwargs)` で
ロケールに応じた文字列を取得する。フォールバック順は
「対象言語 → 英語（デフォルト） → キー文字列そのもの」で、
未知のキーやロケールでも例外を投げない設計にしている。

キーはフラットなドット区切り文字列（例: "link.success_title"）。
ja.json / en.json は完全に同じキー集合を持つこと（tests/test_i18n.py で検証）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Union

LOCALES_DIR = Path(__file__).resolve().parent / "locales"

# デフォルト/フォールバック言語は英語（国際展開向け）。日本語クライアントのみ日本語。
DEFAULT_LOCALE = "en"
SUPPORTED_LOCALES = ("en", "ja")

_catalogs: dict[str, dict[str, str]] = {}


def _load_catalog(locale: str) -> dict[str, str]:
    path = LOCALES_DIR / f"{locale}.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _ensure_loaded() -> None:
    if _catalogs:
        return
    for locale in SUPPORTED_LOCALES:
        _catalogs[locale] = _load_catalog(locale)


_ensure_loaded()


def normalize_locale(locale: Optional[Union[str, object]]) -> str:
    """discord.Localeまたは文字列をサポート済みロケールコード（"ja"/"en"）に正規化する。

    "ja"系（discord.Locale.japanese等）は日本語、それ以外は英語にフォールバックする。
    """
    if locale is None:
        return DEFAULT_LOCALE
    code = str(locale)
    if code.lower().startswith("ja"):
        return "ja"
    return DEFAULT_LOCALE


def has_key(key: str) -> bool:
    """キーがロケールカタログに存在するか（英語カタログを正とする）。"""
    return key in _catalogs.get(DEFAULT_LOCALE, {})


def t(locale: Optional[Union[str, object]], key: str, /, **kwargs) -> str:
    """ロケールに応じた翻訳文字列を返す。

    フォールバック順: 対象ロケール → 英語（デフォルト） → キー文字列そのもの。
    キーが存在しない/フォーマット引数が不足していても例外を投げない。
    """
    normalized = normalize_locale(locale)

    text = _catalogs.get(normalized, {}).get(key)
    if text is None and normalized != DEFAULT_LOCALE:
        text = _catalogs.get(DEFAULT_LOCALE, {}).get(key)
    if text is None:
        text = key

    if not kwargs:
        return text

    try:
        return text.format(**kwargs)
    except (KeyError, IndexError):
        return text
