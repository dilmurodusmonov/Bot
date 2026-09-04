from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.texts import LANGUAGES, t

LANGUAGE_FLAGS = {"uz": "🇺🇿 O'zbekcha", "ru": "🇷🇺 Русский", "en": "🇬🇧 English"}


def language_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=LANGUAGE_FLAGS[lang], callback_data=f"lang:{lang}")]
        for lang in LANGUAGES
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def role_keyboard(lang: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=t(lang, "role_donor"), callback_data="role:donor")],
        [InlineKeyboardButton(text=t(lang, "role_needy"), callback_data="role:needy")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
