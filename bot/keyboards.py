from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from bot.config import WEBAPP_URL
from bot.texts import CATEGORIES, LANGUAGES, t

LANGUAGE_FLAGS = {"uz": "🇺🇿 O'zbekcha", "ru": "🇷🇺 Русский", "en": "🇬🇧 English"}


def _kabinet_row(lang: str) -> list[KeyboardButton]:
    if not WEBAPP_URL:
        return []
    return [KeyboardButton(text=t(lang, "btn_kabinet"), web_app=WebAppInfo(url=WEBAPP_URL))]


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


def category_keyboard(lang: str) -> InlineKeyboardMarkup:
    rows = []
    for key, names in CATEGORIES.items():
        label = names.get(lang, names["uz"])
        rows.append(
            [InlineKeyboardButton(text=label, callback_data=f"cat:{key}")]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def donor_main_menu(lang: str) -> ReplyKeyboardMarkup:
    rows = [
        _kabinet_row(lang),
        [KeyboardButton(text=t(lang, "btn_add_donation"))],
        [KeyboardButton(text=t(lang, "btn_my_donations"))],
        [
            KeyboardButton(text=t(lang, "btn_change_language")),
            KeyboardButton(text=t(lang, "btn_change_role")),
        ],
    ]
    return ReplyKeyboardMarkup(keyboard=[row for row in rows if row], resize_keyboard=True)


def needy_main_menu(lang: str) -> ReplyKeyboardMarkup:
    rows = [
        _kabinet_row(lang),
        [KeyboardButton(text=t(lang, "btn_browse_donations"))],
        [KeyboardButton(text=t(lang, "btn_my_requests"))],
        [
            KeyboardButton(text=t(lang, "btn_change_language")),
            KeyboardButton(text=t(lang, "btn_change_role")),
        ],
    ]
    return ReplyKeyboardMarkup(keyboard=[row for row in rows if row], resize_keyboard=True)


def main_menu(lang: str, role: str) -> ReplyKeyboardMarkup:
    return donor_main_menu(lang) if role == "donor" else needy_main_menu(lang)


def reserve_keyboard(lang: str, donation_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_reserve"), callback_data=f"reserve:{donation_id}"
                )
            ]
        ]
    )


def ship_keyboard(lang: str, reservation_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_mark_shipped"),
                    callback_data=f"ship:{reservation_id}",
                )
            ]
        ]
    )


def confirm_received_keyboard(lang: str, reservation_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_confirm_received"),
                    callback_data=f"confirm:{reservation_id}",
                )
            ]
        ]
    )
