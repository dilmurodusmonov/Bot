import json

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.states import DonorAddDonation, DonorShipment
from bot.utils import get_lang, with_cancel_hint

router = Router()


@router.message(F.web_app_data)
async def web_app_data_received(message: Message, state: FSMContext) -> None:
    lang = await get_lang(message.from_user.id)
    try:
        payload = json.loads(message.web_app_data.data)
    except (ValueError, AttributeError):
        return

    action = payload.get("type")

    if action == "start_add_donation":
        category = payload.get("category")
        description = (payload.get("description") or "").strip()
        if not category or not description:
            return
        await state.set_state(DonorAddDonation.uploading_photo)
        await state.update_data(category=category, description=description)
        await message.answer(with_cancel_hint(lang, "ask_photo"))

    elif action == "start_shipment":
        reservation_id = payload.get("reservation_id")
        if not reservation_id:
            return
        await state.set_state(DonorShipment.uploading_receipt)
        await state.update_data(reservation_id=reservation_id)
        await message.answer(with_cancel_hint(lang, "ask_receipt_photo"))
