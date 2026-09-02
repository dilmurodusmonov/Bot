from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.database import create_user_if_missing, get_user, set_user_language, set_user_role
from bot.keyboards import language_keyboard, main_menu, role_keyboard
from bot.texts import t
from bot.utils import button_variants, get_lang

router = Router()


async def _show_main_menu(message: Message, lang: str, role: str) -> None:
    hint_key = "menu_donor_hint" if role == "donor" else "menu_needy_hint"
    await message.answer(f"{t(lang, hint_key)}", reply_markup=main_menu(lang, role))


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await create_user_if_missing(message.from_user.id)

    if not user["language"]:
        await message.answer(t("uz", "choose_language"), reply_markup=language_keyboard())
        return

    lang = user["language"]
    if not user["role"]:
        await message.answer(t(lang, "choose_role"), reply_markup=role_keyboard(lang))
        return

    await message.answer(t(lang, "welcome_back"))
    await _show_main_menu(message, lang, user["role"])


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await get_user(message.from_user.id)
    lang = user["language"] if user and user["language"] else "uz"
    await message.answer(t(lang, "cancelled"))
    if user and user["role"]:
        await _show_main_menu(message, lang, user["role"])


@router.message(F.text.in_(button_variants("btn_change_language")))
async def change_language(message: Message, state: FSMContext) -> None:
    await state.clear()
    lang = await get_lang(message.from_user.id)
    await message.answer(t(lang, "choose_language"), reply_markup=language_keyboard())


@router.message(F.text.in_(button_variants("btn_change_role")))
async def change_role(message: Message, state: FSMContext) -> None:
    await state.clear()
    lang = await get_lang(message.from_user.id)
    await message.answer(t(lang, "choose_role"), reply_markup=role_keyboard(lang))


@router.callback_query(F.data.startswith("lang:"))
async def language_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    lang = callback.data.split(":", 1)[1]
    await set_user_language(callback.from_user.id, lang)
    await state.clear()

    user = await get_user(callback.from_user.id)
    await callback.message.edit_text(t(lang, "language_set"))
    if user["role"]:
        await _show_main_menu(callback.message, lang, user["role"])
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
    await _show_main_menu(callback.message, lang, role)
    await callback.answer()
