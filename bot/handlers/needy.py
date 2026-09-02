from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.database import (
    create_reservation,
    get_available_donations,
    get_donation,
    get_reservation,
    get_reservations_by_needy,
    set_donation_status,
    set_reservation_received,
)
from bot.keyboards import category_keyboard, confirm_received_keyboard, reserve_keyboard
from bot.states import NeedyConfirmation, NeedyReservation
from bot.texts import category_name, status_label, t
from bot.utils import button_variants, get_lang

router = Router()


@router.message(F.text.in_(button_variants("btn_browse_donations")))
async def browse_categories(message: Message, state: FSMContext) -> None:
    await state.clear()
    lang = await get_lang(message.from_user.id)
    await message.answer(t(lang, "choose_category"), reply_markup=category_keyboard(lang))


@router.callback_query(F.data.startswith("cat:"))
async def category_browse(callback: CallbackQuery) -> None:
    category = callback.data.split(":", 1)[1]
    lang = await get_lang(callback.from_user.id)
    donations = await get_available_donations(category)

    await callback.answer()
    if not donations:
        await callback.message.answer(t(lang, "no_donations_in_category"))
        return

    for donation in donations:
        caption = t(
            lang,
            "donation_card",
            category=category_name(donation["category"], lang),
            description=donation["description"],
        )
        await callback.message.answer_photo(
            photo=donation["photo_file_id"],
            caption=caption,
            reply_markup=reserve_keyboard(lang, donation["id"]),
        )


@router.callback_query(F.data.startswith("reserve:"))
async def reserve_requested(callback: CallbackQuery, state: FSMContext) -> None:
    donation_id = int(callback.data.split(":", 1)[1])
    lang = await get_lang(callback.from_user.id)
    donation = await get_donation(donation_id)

    if not donation or donation["status"] != "available":
        await callback.answer(t(lang, "already_reserved"), show_alert=True)
        return

    await state.set_state(NeedyReservation.entering_name)
    await state.update_data(donation_id=donation_id)
    await callback.message.answer(t(lang, "ask_full_name"))
    await callback.answer()


@router.message(NeedyReservation.entering_name, F.text)
async def name_entered(message: Message, state: FSMContext) -> None:
    lang = await get_lang(message.from_user.id)
    await state.update_data(full_name=message.text)
    await state.set_state(NeedyReservation.entering_address)
    await message.answer(t(lang, "ask_address"))


@router.message(NeedyReservation.entering_address, F.text)
async def address_entered(message: Message, state: FSMContext) -> None:
    lang = await get_lang(message.from_user.id)
    await state.update_data(address=message.text)
    await state.set_state(NeedyReservation.entering_phone)
    await message.answer(t(lang, "ask_phone"))


@router.message(NeedyReservation.entering_phone, F.text)
async def phone_entered(message: Message, state: FSMContext) -> None:
    lang = await get_lang(message.from_user.id)
    data = await state.get_data()
    donation_id = data["donation_id"]

    donation = await get_donation(donation_id)
    if not donation or donation["status"] != "available":
        await state.clear()
        await message.answer(t(lang, "already_reserved"))
        return

    reservation_id = await create_reservation(
        donation_id=donation_id,
        needy_id=message.from_user.id,
        full_name=data["full_name"],
        address=data["address"],
        phone=message.text,
    )
    await set_donation_status(donation_id, "reserved")
    await state.clear()
    await message.answer(t(lang, "reservation_done_needy"))

    donor_lang = await get_lang(donation["donor_id"])
    await message.bot.send_message(
        chat_id=donation["donor_id"],
        text=t(
            donor_lang,
            "new_reservation_for_donor",
            category=category_name(donation["category"], donor_lang),
            description=donation["description"],
            full_name=data["full_name"],
            address=data["address"],
            phone=message.text,
        ),
    )


@router.message(F.text.in_(button_variants("btn_my_requests")))
async def my_requests(message: Message, state: FSMContext) -> None:
    await state.clear()
    lang = await get_lang(message.from_user.id)
    reservations = await get_reservations_by_needy(message.from_user.id)

    if not reservations:
        await message.answer(t(lang, "my_requests_empty"))
        return

    for reservation in reservations:
        donation = await get_donation(reservation["donation_id"])
        if not donation:
            continue

        caption = t(
            lang,
            "donation_card",
            category=category_name(donation["category"], lang),
            description=donation["description"],
        )
        caption += f"\n\n{status_label(reservation['status'], lang)}"
        if reservation["status"] == "received" and reservation.get("dua_text"):
            caption += t(lang, "dua_info_card", dua_text=reservation["dua_text"])

        if reservation["status"] == "shipped" and reservation.get("receipt_photo_file_id"):
            await message.answer_photo(
                photo=reservation["receipt_photo_file_id"],
                caption=caption,
                reply_markup=confirm_received_keyboard(lang, reservation["id"]),
            )
        else:
            await message.answer_photo(photo=donation["photo_file_id"], caption=caption)


@router.callback_query(F.data.startswith("confirm:"))
async def confirm_requested(callback: CallbackQuery, state: FSMContext) -> None:
    reservation_id = int(callback.data.split(":", 1)[1])
    reservation = await get_reservation(reservation_id)
    lang = await get_lang(callback.from_user.id)

    if not reservation or reservation["needy_id"] != callback.from_user.id:
        await callback.answer()
        return
    if reservation["status"] != "shipped":
        await callback.answer()
        return

    await state.set_state(NeedyConfirmation.entering_dua)
    await state.update_data(reservation_id=reservation_id)
    await callback.message.answer(t(lang, "ask_dua"))
    await callback.answer()


@router.message(NeedyConfirmation.entering_dua, F.text)
async def dua_entered(message: Message, state: FSMContext) -> None:
    lang = await get_lang(message.from_user.id)
    data = await state.get_data()
    reservation_id = data["reservation_id"]
    reservation = await get_reservation(reservation_id)

    await set_reservation_received(reservation_id, message.text)
    await state.clear()
    await message.answer(t(lang, "received_confirmed_needy"))

    donation = await get_donation(reservation["donation_id"])
    donor_lang = await get_lang(donation["donor_id"])
    await message.bot.send_message(
        chat_id=donation["donor_id"],
        text=t(donor_lang, "received_notify_donor", dua_text=message.text),
    )
