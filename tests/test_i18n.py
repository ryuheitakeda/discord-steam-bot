"""i18n.py（多言語化ヘルパー）のユニットテスト。"""

import json
from pathlib import Path

import discord

import i18n

LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"


def _load(locale: str) -> dict:
    with (LOCALES_DIR / f"{locale}.json").open(encoding="utf-8") as f:
        return json.load(f)


def test_ja_and_en_have_identical_key_sets():
    """ja.jsonとen.jsonのキー集合が完全一致していること（欠落防止）。"""
    ja_keys = set(_load("ja").keys())
    en_keys = set(_load("en").keys())

    assert ja_keys == en_keys
    assert len(ja_keys) > 0


def test_t_returns_japanese_for_japanese_locale():
    result = i18n.t("ja", "unlink.success")
    assert result == "✅ 紐づけを解除しました。"


def test_t_returns_english_for_english_locale():
    result = i18n.t("en", "unlink.success")
    assert result == "✅ Your Steam account has been unlinked."


def test_t_returns_japanese_for_discord_japanese_locale_enum():
    result = i18n.t(discord.Locale.japanese, "unlink.success")
    assert result == "✅ 紐づけを解除しました。"


def test_t_falls_back_to_english_for_unsupported_locale():
    """未対応ロケール（例: フランス語）は英語にフォールバックする。"""
    result = i18n.t(discord.Locale.french, "unlink.success")
    assert result == "✅ Your Steam account has been unlinked."


def test_t_falls_back_to_english_when_locale_is_none():
    result = i18n.t(None, "unlink.success")
    assert result == "✅ Your Steam account has been unlinked."


def test_t_unknown_key_does_not_raise_and_returns_key():
    """未知キーでもKeyErrorを投げず、キー文字列自体にフォールバックする。"""
    result = i18n.t("ja", "this.key.does.not.exist")
    assert result == "this.key.does.not.exist"

    result_en = i18n.t("en", "this.key.does.not.exist")
    assert result_en == "this.key.does.not.exist"


def test_t_format_placeholder_expansion():
    result = i18n.t("ja", "profile.not_linked", mention="<@123>")
    assert result == "<@123> はまだSteamアカウントを紐づけていません。"

    result_en = i18n.t("en", "profile.not_linked", mention="<@123>")
    assert result_en == "<@123> hasn't linked a Steam account yet."


def test_t_missing_format_kwargs_does_not_raise():
    """プレースホルダに対応するkwargsが無くてもKeyErrorを投げない。"""
    result = i18n.t("ja", "profile.not_linked")
    assert result  # フォーマットに失敗しても元テキストを返す


def test_has_key():
    assert i18n.has_key("unlink.success") is True
    assert i18n.has_key("no.such.key") is False


def test_normalize_locale():
    assert i18n.normalize_locale("ja") == "ja"
    assert i18n.normalize_locale(discord.Locale.japanese) == "ja"
    assert i18n.normalize_locale("en-US") == "en"
    assert i18n.normalize_locale(discord.Locale.american_english) == "en"
    assert i18n.normalize_locale(None) == "en"
    assert i18n.normalize_locale("fr") == "en"
