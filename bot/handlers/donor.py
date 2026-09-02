from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.database import (
    create_donation,
    get_active_reservation_for_donation,
    get_donation,
    get_donations_by_donor,
    get_reservation,
    get_user,
    set_donation_status,
    set_reservation_shipped,
)
from bot.keyboards import category_keyboard, ship_keyboard, confirm_received_keyboard
from bot.states import DonorAddDonation, DonorShipment
from bot.texts import category_name, status_label, t
from bot.utils import button_variants, get_lang, with_cancel_hint

router = Router()


@router.message(F.text.in_(button_variants("btn_add_donation")))
async def start_add_donation(message: Message, state: FSMContext) -> None:
    user = await get_user(message.from_user.id)
    if not user or user["role"] != "donor":
        return

    lang = user["language"] or "uz"
    await state.set_state(DonorAddDonation.choosing_category)
    await message.answer(t(lang, "choose_category"), reply_markup=category_keyboard(lang))


@router.callback_query(DonorAddDonation.choosing_category, F.data.startswith("cat:"))
async def category_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    category = callback.data.split(":", 1)[1]
    lang = await get_lang(callback.from_user.id)
    await state.update_data(category=category)
    await state.set_state(DonorAddDonation.uploading_photo)
    await callback.message.edit_text(category_name(category, lang))
    await callback.message.answer(with_cancel_hint(lang, "ask_photo"))
    await callback.answer()


@router.message(DonorAddDonation.uploading_photo, F.photo)
async def photo_uploaded(message: Message, state: FSMContext) -> None:
    lang = await get_lang(message.from_user.id)
    await state.update_data(photo_file_id=message.photo[-1].file_id)
    await state.set_state(DonorAddDonation.entering_description)
    await message.answer(with_cancel_hint(lang, "ask_description"))


@router.message(DonorAddDonation.uploading_photo)
async def photo_retry(message: Message) -> None:
    lang = await get_lang(message.from_user.id)
    await message.answer(t(lang, "ask_photo_retry"))


@router.message(DonorAddDonation.entering_description, F.text)
async def description_entered(message: Message, state: FSMContext) -> None:
    lang = await get_lang(message.from_user.id)
    data = await state.get_data()

    await create_donation(
        donor_id=message.from_user.id,
        category=data["category"],
        photo_file_id=data["photo_file_id"],
        description=message.text,
    )
    await state.clear()
    await message.answer(t(lang, "donation_added"))


@router.message(F.text.in_(button_variants("btn_my_donations")))
async def my_donations(message: Message, state: FSMContext) -> None:
    user = await get_user(message.from_user.id)
    if not user or user["role"] != "donor":
        return

    await state.clear()
    lang = user["language"] or "uz"
    donations = await get_donations_by_donor(message.from_user.id)

    if not donations:
        await message.answer(t(lang, "my_donations_empty"))
        return

    for donation in donations:
        caption = t(
            lang,
            "donation_card",
            category=category_name(donation["category"], lang),
            description=donation["description"],
        )
        caption += f"\n\n{status_label(donation['status'], lang)}"

        reply_markup = None
        if donation["status"] in ("reserved", "shipped", "received"):
            reservation = await get_active_reservation_for_donation(donation["id"])
            if reservation:
                if donation["status"] == "reserved":
                    caption += t(
                        lang,
                        "reservation_info_for_donor_card",
                        full_name=reservation["full_name"],
                        address=reservation["address"],
                        phone=reservation["phone"],
                    )
                    reply_markup = ship_keyboard(lang, reservation["id"])
                elif donation["status"] == "received" and reservation.get("dua_text"):
                    caption += t(lang, "dua_info_card", dua_text=reservation["dua_text"])

        await message.answer_photo(
            photo=donation["photo_file_id"], caption=caption, reply_markup=reply_markup
        )


@router.callback_query(F.data.startswith("ship:"))
async def ship_requested(callback: CallbackQuery, state: FSMContext) -> None:
    reservation_id = int(callback.data.split(":", 1)[1])
    reservation = await get_reservation(reservation_id)
    lang = await get_lang(callback.from_user.id)

    if not reservation or reservation["status"] != "reserved":
        await callback.answer()
        return

    donation = await get_donation(reservation["donation_id"])
    if not donation or donation["donor_id"] != callback.from_user.id:
        await callback.answer()
        return

    await state.set_state(DonorShipment.uploading_receipt)
    await state.update_data(reservation_id=reservation_id)
    await callback.message.answer(with_cancel_hint(lang, "ask_receipt_photo"))
    await callback.answer()


@router.message(DonorShipment.uploading_receipt, F.photo)
async def receipt_uploaded(message: Message, state: FSMContext) -> None:
    lang = await get_lang(message.from_user.id)
    data = await state.get_data()
    reservation_id = data["reservation_id"]
    reservation = await get_reservation(reservation_id)

    photo_file_id = message.photo[-1].file_id
    await set_reservation_shipped(reservation_id, photo_file_id, message.caption)
    await set_donation_status(reservation["donation_id"], "shipped")
    await state.clear()

    await message.answer(t(lang, "shipped_saved_donor"))

    needy_lang = await get_lang(reservation["needy_id"])
    await message.bot.send_photo(
        chat_id=reservation["needy_id"],
        photo=photo_file_id,
        caption=t(needy_lang, "shipped_notify_needy"),
        reply_markup=confirm_received_keyboard(needy_lang, reservation_id),
    )


@router.message(DonorShipment.uploading_receipt)
async def receipt_retry(message: Message) -> None:
    lang = await get_lang(message.from_user.id)
    await message.answer(t(lang, "ask_photo_retry"))
