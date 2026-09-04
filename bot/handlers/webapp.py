from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import Message

from bot.database import (
    clear_pending_action,
    create_donation,
    get_pending_action,
    get_reservation,
    set_donation_status,
    set_reservation_shipped,
)
from bot.keyboards import confirm_received_keyboard
from bot.texts import t
from bot.utils import get_lang

router = Router()


@router.message(StateFilter(None), F.photo)
async def photo_for_pending_action(message: Message) -> None:
    """Mini App orqali boshlangan (ehson qo'shish / chek yuklash) amalni
    chatdan kelgan rasm bilan yakunlaydi. Faqat hech qanday chat-FSM
    holati faol bo'lmaganda ishlaydi — eski chat oqimiga xalaqit bermaydi.
    """
    pending = await get_pending_action(message.from_user.id)
    if not pending:
        return

    lang = await get_lang(message.from_user.id)
    photo_file_id = message.photo[-1].file_id
    payload = pending["payload"]

    if pending["action"] == "add_donation":
        await create_donation(
            donor_id=message.from_user.id,
            category=payload["category"],
            photo_file_id=photo_file_id,
            description=payload["description"],
        )
        await clear_pending_action(message.from_user.id)
        await message.answer(t(lang, "donation_added"))

    elif pending["action"] == "ship_reservation":
        reservation_id = payload["reservation_id"]
        reservation = await get_reservation(reservation_id)
        if not reservation:
            await clear_pending_action(message.from_user.id)
            return

        await set_reservation_shipped(reservation_id, photo_file_id, payload.get("receipt_note"))
        await set_donation_status(reservation["donation_id"], "shipped")
        await clear_pending_action(message.from_user.id)

        await message.answer(t(lang, "shipped_saved_donor"))

        needy_lang = await get_lang(reservation["needy_id"])
        await message.bot.send_photo(
            chat_id=reservation["needy_id"],
            photo=photo_file_id,
            caption=t(needy_lang, "shipped_notify_needy"),
            reply_markup=confirm_received_keyboard(needy_lang, reservation_id),
        )
