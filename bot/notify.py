from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardMarkup


async def send_tracked_message(
    bot: Bot,
    chat_id: int,
    old_message_id: Optional[int],
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> int:
    """Ehsonning holati o'zgarganda, shu ehsonga oid oldingi bildirishnoma
    xabari o'chirilib, o'rniga yangisi yuboriladi — bot chatida eskirgan
    holat xabarlari to'planib qolmasligi uchun (masalan, "yangi so'rov"
    xabari ehson yo'lga chiqqanda o'chadi). webapp_api.py (holat
    o'zgarishlarida) va bot/reminders.py (eslatmalarda) ikkalasi ham
    ishlatadi."""
    if old_message_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=old_message_id)
        except TelegramAPIError:
            pass
    sent = await bot.send_message(chat_id, text, reply_markup=reply_markup)
    return sent.message_id
