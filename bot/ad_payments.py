"""Reklama to'lovlari: chekni adminga yuborish va admin xabari matni.

Hozircha to'lov kartaga o'tkazma orqali — foydalanuvchi chekni yuklaydi,
admin Telegram'da "Tasdiqlash"/"Rad etish" tugmasini bosadi."""
from html import escape
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import AD_ADMIN_IDS, BASE_URL

CALLBACK_PREFIX = "adpay"


def format_som(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " so'm"


def receipt_button(payment_id: int, receipt_file_id: Optional[str]) -> InlineKeyboardButton:
    """"Chekni ko'rish": chek chatga katta rasm bo'lib tushmaydi — tugma
    uni Telegram ichidagi brauzerda ochadi (BASE_URL bo'lmasa, bosilganda
    bot rasmni yuboradi)."""
    if BASE_URL and receipt_file_id:
        return InlineKeyboardButton(text="🧾 Chekni ko'rish", url=f"{BASE_URL}/api/photo/{receipt_file_id}")
    return InlineKeyboardButton(text="🧾 Chekni ko'rish", callback_data=f"{CALLBACK_PREFIX}:view:{payment_id}")


def admin_keyboard(payment_id: int, receipt_file_id: Optional[str]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [receipt_button(payment_id, receipt_file_id)],
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"{CALLBACK_PREFIX}:ok:{payment_id}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"{CALLBACK_PREFIX}:no:{payment_id}"),
        ],
    ])


# Rad etish sabablari: callback kodi -> (admin tugmasi, foydalanuvchi matni kaliti).
REJECT_REASONS = {
    "nr": ("💸 Summa kartaga kelib tushmadi", "ad_reject_not_received"),
    "wa": ("⚠️ Noto'g'ri summa to'langan", "ad_reject_wrong_amount"),
    "br": ("🧾 Chek noto'g'ri yoki o'qib bo'lmaydi", "ad_reject_bad_receipt"),
}


def reject_reasons_keyboard(payment_id: int, receipt_file_id: Optional[str]) -> InlineKeyboardMarkup:
    """"Rad etish" bosilganda: avval sabab tanlanadi."""
    rows = [[receipt_button(payment_id, receipt_file_id)]]
    rows += [
        [InlineKeyboardButton(text=label, callback_data=f"{CALLBACK_PREFIX}:rj:{payment_id}:{code}")]
        for code, (label, _) in REJECT_REASONS.items()
    ]
    rows.append([InlineKeyboardButton(text="✍️ Boshqa sabab (yozish)", callback_data=f"{CALLBACK_PREFIX}:rc:{payment_id}")])
    rows.append([InlineKeyboardButton(text="↩️ Orqaga", callback_data=f"{CALLBACK_PREFIX}:back:{payment_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def decided_keyboard(payment_id: int, receipt_file_id: Optional[str]) -> InlineKeyboardMarkup:
    """Qaror qabul qilingach tasdiqlash tugmalari olinadi, chek qoladi."""
    return InlineKeyboardMarkup(inline_keyboard=[[receipt_button(payment_id, receipt_file_id)]])


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
    """Adminlarga ixcham matnli xabar + inline tugmalar yuboradi va chek
    rasmining file_id'sini qaytaradi. file_id olishning yagona yo'li —
    rasmni yuborish, shuning uchun u birinchi adminga yuborilib, darhol
    o'chiriladi (file_id amal qilishda davom etadi). Birorta adminga ham
    yetib bormasa None."""
    file_id: Optional[str] = None
    for admin_id in AD_ADMIN_IDS:
        try:
            sent = await bot.send_photo(
                chat_id=admin_id, photo=BufferedInputFile(photo_bytes, filename=filename),
                disable_notification=True,
            )
        except TelegramAPIError:
            continue
        file_id = sent.photo[-1].file_id
        try:
            await bot.delete_message(chat_id=admin_id, message_id=sent.message_id)
        except TelegramAPIError:
            pass
        break
    if not file_id:
        return None

    delivered = False
    for admin_id in AD_ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id, text=caption, reply_markup=admin_keyboard(payment_id, file_id),
                disable_web_page_preview=True,
            )
            delivered = True
        except TelegramAPIError:
            continue
    return file_id if delivered else None
