"""Admin chekni ko'rib "Tasdiqlash"/"Rad etish" tugmasini bosganda."""
import logging
from html import escape

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery

from bot.ad_payments import CALLBACK_PREFIX, decided_keyboard, format_som
from bot.config import AD_ADMIN_IDS
from bot.database import decide_ad_payment, get_ad_payment, get_user
from bot.texts import t

router = Router()


@router.callback_query(F.data.startswith(CALLBACK_PREFIX + ":"))
async def on_ad_payment_decision(callback: CallbackQuery) -> None:
    if callback.from_user.id not in AD_ADMIN_IDS:
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    try:
        _, action, raw_id = callback.data.split(":")
        payment_id = int(raw_id)
    except ValueError:
        await callback.answer()
        return

    if action == "view":
        payment = await get_ad_payment(payment_id)
        await callback.answer()
        if payment and payment["receipt_file_id"]:
            await callback.message.answer_photo(payment["receipt_file_id"], caption=f"🧾 Chek #{payment_id}")
        return

    approve = action == "ok"
    result = await decide_ad_payment(payment_id, approve, callback.from_user.id)
    if result is None:
        await callback.answer("Bu to'lov allaqachon ko'rib chiqilgan", show_alert=True)
        return

    payment, bid = result["payment"], result["bid"]
    status_line = "✅ <b>Tasdiqlandi</b>" if approve else "❌ <b>Rad etildi</b>"
    try:
        await callback.message.edit_text(
            f"{callback.message.html_text}\n\n{status_line}",
            reply_markup=decided_keyboard(payment_id, payment["receipt_file_id"]),
            disable_web_page_preview=True,
        )
    except TelegramAPIError:
        pass
    await callback.answer("Tasdiqlandi" if approve else "Rad etildi")

    user = await get_user(payment["telegram_id"])
    lang = (user or {}).get("language") or "uz"
    brand = escape(bid["brand_name"]) if bid else ""
    if not approve:
        key = "ad_payment_rejected"
    elif payment["kind"] == "new":
        key = "ad_payment_approved_new"
    else:
        key = "ad_payment_approved_raise"
    try:
        await callback.bot.send_message(
            payment["telegram_id"], t(lang, key, brand=brand, amount=format_som(payment["amount"]))
        )
    except TelegramAPIError:
        logging.warning("Reklama to'lovi haqida foydalanuvchiga xabar yuborilmadi: %s", payment["telegram_id"])
