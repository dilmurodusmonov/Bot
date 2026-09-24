"""Reklama to'lovlari: chekni adminga yuborish va admin xabari matni.

Hozircha to'lov kartaga o'tkazma orqali — foydalanuvchi chekni yuklaydi,
admin Telegram'da "Tasdiqlash"/"Rad etish" tugmasini bosadi."""
from html import escape
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import AD_ADMIN_IDS

CALLBACK_PREFIX = "adpay"


def format_som(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " so'm"


def admin_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"{CALLBACK_PREFIX}:ok:{payment_id}"),
        InlineKeyboardButton(text="❌ Rad etish", callback_data=f"{CALLBACK_PREFIX}:no:{payment_id}"),
    ]])


def admin_caption(payment_id: int, kind: str, amount: int, bid: dict, telegram_id: int) -> str:
    kind_label = "🆕 Yangi reklama" if kind == "new" else "⬆️ Taklifni oshirish"
    lines = [
        f"💳 <b>Reklama to'lovi #{payment_id}</b>",
        f"Tur: {kind_label}",
        f"Brend: {escape(bid['brand_name'])}",
        f"Sayt: {escape(bid['url'])}",
        f"Summa: <b>{format_som(amount)}</b>",
    ]
    if kind == "raise":
        lines.append(f"Hozirgi taklif: {format_som(bid['bid_amount'])} → {format_som(bid['bid_amount'] + amount)}")
    lines.append(f'Foydalanuvchi: <a href="tg://user?id={telegram_id}">{telegram_id}</a>')
    lines.append("")
    lines.append("Kartaga shu summa tushganini tekshirib, tasdiqlang.")
    return "\n".join(lines)


async def send_receipt_to_admins(
    bot: Bot, photo_bytes: bytes, filename: str, caption: str, payment_id: int,
) -> Optional[str]:
    """Chekni har bir adminga yuboradi va rasmning file_id'sini qaytaradi.
    Birorta adminga ham yetib bormasa None."""
    file_id: Optional[str] = None
    for admin_id in AD_ADMIN_IDS:
        photo = file_id or BufferedInputFile(photo_bytes, filename=filename)
        try:
            sent = await bot.send_photo(
                chat_id=admin_id, photo=photo, caption=caption,
                reply_markup=admin_keyboard(payment_id),
            )
        except TelegramAPIError:
            continue
        file_id = file_id or sent.photo[-1].file_id
    return file_id
