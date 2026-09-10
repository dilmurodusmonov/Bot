from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardRemove,
    WebAppInfo,
)

from bot.config import WEBAPP_URL
from bot.database import create_user_if_missing, get_user, set_user_language, set_user_role
from bot.keyboards import language_keyboard, role_keyboard
from bot.texts import t
from bot.utils import get_lang

router = Router()


async def _show_open_app_hint(message: Message, lang: str) -> None:
    await message.answer(t(lang, "open_app_hint"), reply_markup=ReplyKeyboardRemove())


async def _show_open_app_button(message: Message, lang: str, donation_id: str | None = None) -> None:
    """Mini App'ga to'g'ridan-to'g'ri o'tish uchun inline tugma —
    oddiy t.me havolasidan farqli o'laroq, bu tugma Mini App'ni
    ishonchli ochadi (masalan /d/{id} ulashish sahifasidagi
    "Botni ochish" havolasi orqali kelgan foydalanuvchilar uchun).
    donation_id berilsa, Mini App to'g'ridan-to'g'ri o'sha ehsonni
    ko'rsatadigan holatda ochiladi."""
    if not WEBAPP_URL:
        await _show_open_app_hint(message, lang)
        return
    url = f"{WEBAPP_URL}&d={donation_id}" if donation_id else WEBAPP_URL
    await message.answer(
        t(lang, "open_app_hint"),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text=t(lang, "open_app_button"), web_app=WebAppInfo(url=url))
            ]]
        ),
    )


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await create_user_if_missing(message.from_user.id)
    args = (message.text or "").split(maxsplit=1)
    payload = args[1] if len(args) > 1 else None
    donation_id = payload[2:] if payload and payload.startswith("d_") else None

    if not user["language"]:
        await message.answer(t("uz", "choose_language"), reply_markup=language_keyboard())
        return

    lang = user["language"]
    if not user["role"]:
        await message.answer(t(lang, "choose_role"), reply_markup=role_keyboard(lang))
        return

    await message.answer(t(lang, "welcome_back"))
    if donation_id:
        await _show_open_app_button(message, lang, donation_id)
    else:
        await _show_open_app_hint(message, lang)


@router.callback_query(F.data.startswith("lang:"))
async def language_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    lang = callback.data.split(":", 1)[1]
    await set_user_language(callback.from_user.id, lang)
    await state.clear()

    user = await get_user(callback.from_user.id)
    await callback.message.edit_text(t(lang, "language_set"))
    if user["role"]:
        await _show_open_app_hint(callback.message, lang)
    else:
        await callback.message.answer(t(lang, "choose_role"), reply_markup=role_keyboard(lang))
    await callback.answer()


@router.callback_query(F.data.startswith("role:"))
async def role_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    role = callback.data.split(":", 1)[1]
    await set_user_role(callback.from_user.id, role)
    lang = await get_lang(callback.from_user.id)
    await state.clear()

    await callback.message.edit_text(t(lang, "role_donor" if role == "donor" else "role_needy"))
    await _show_open_app_hint(callback.message, lang)
    await callback.answer()


@router.message(F.text)
async def fallback_text(message: Message) -> None:
    lang = await get_lang(message.from_user.id)
    await message.answer(t(lang, "unknown_command"))
