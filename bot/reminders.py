import asyncio
import logging
from datetime import timedelta
from html import escape
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from bot.config import WEBAPP_URL
from bot.database import (
    get_due_receive_reminders,
    get_due_ship_reminders,
    record_donor_reminder,
    record_needy_reminder,
)
from bot.notify import WIDE_BUBBLE_PAD, send_tracked_message
from bot.texts import category_name, t

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 5 * 60

# Birinchi eslatma holat boshlanganidan 12 soat o'tgach, ikkinchisi undan
# 6 soat keyin, keyingilari esa har 1 soatda — javob berilmaguncha yoki
# ehson keyingi holatga (masalan, "yetib bordi"ga) o'tmaguncha davom etadi.
FIRST_REMINDER_AFTER = timedelta(hours=12)
SECOND_REMINDER_AFTER = timedelta(hours=6)
REPEAT_REMINDER_AFTER = timedelta(hours=1)


# Bir vaqtda ko'p eslatma yuborilganda Telegram limitiga (sekundiga ~30
# xabar) urilmaslik uchun xabarlar orasida qisqa tanaffus.
SEND_PAUSE_SECONDS = 0.05


def _open_app_keyboard(lang: str, screen: str) -> Optional[InlineKeyboardMarkup]:
    if not WEBAPP_URL:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=t(lang, "open_app_button"),
            web_app=WebAppInfo(url=f"{WEBAPP_URL}&screen={screen}"),
        )
    ]])


async def _send_with_retry(factory):
    """Telegram limitiga urilsa (429) aytilgan vaqtcha kutib qayta yuboradi."""
    for attempt in range(3):
        try:
            return await factory()
        except TelegramRetryAfter as e:
            if attempt == 2:
                raise
            await asyncio.sleep(e.retry_after + 1)


def _ship_reminder_text(lang: str, reservation: dict) -> str:
    """Eslatma sarlavhasi + "yangi so'rov" xabaridagi to'liq ma'lumotlar
    (bo'lim, ehson, muhtojning ismi, manzili, telefoni) — eslatma o'sha
    xabar o'rniga keladi, ma'lumotlar chatda yo'qolmasin."""
    full = t(
        lang,
        "new_reservation_for_donor",
        category=escape(category_name(reservation["category"], lang), quote=False),
        description=escape(reservation["description"] or "", quote=False),
        full_name=escape(reservation["full_name"], quote=False),
        address=escape(reservation["address"], quote=False),
        phone=escape(reservation["phone"], quote=False),
    )
    # "🔔 Yangi so'rov!" sarlavhasi eslatma sarlavhasiga almashtiriladi.
    body = full.split("\n\n", 1)[-1]
    return t(lang, "ship_reminder") + "\n\n" + body + WIDE_BUBBLE_PAD


def _upload_receipt_keyboard(lang: str) -> Optional[InlineKeyboardMarkup]:
    if not WEBAPP_URL:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=t(lang, "upload_receipt_button"),
            web_app=WebAppInfo(url=f"{WEBAPP_URL}&screen=donor_cabinet"),
        )
    ]])


async def _check_ship_reminders(bot: Bot) -> None:
    # Vaqti kelgan bronlar bazaning o'zida saralanadi (ehson va til bilan
    # birga, bitta so'rovda) — bronlar soni ko'payganda ham tez ishlaydi.
    # Eslatma chek yuklanmaguncha (ehson yo'lga chiqmaguncha) takrorlanadi.
    due = await get_due_ship_reminders(
        FIRST_REMINDER_AFTER, SECOND_REMINDER_AFTER, REPEAT_REMINDER_AFTER
    )
    for reservation in due:
        donor_lang = reservation["donor_language"] or "uz"
        try:
            message_id = await _send_with_retry(lambda: send_tracked_message(
                bot,
                reservation["donor_id"],
                reservation["donor_notify_message_id"],
                _ship_reminder_text(donor_lang, reservation),
                reply_markup=_upload_receipt_keyboard(donor_lang),
            ))
            await record_donor_reminder(reservation["id"], message_id)
        except TelegramForbiddenError:
            # Foydalanuvchi botni bloklagan — eslatma "yuborilgan" deb
            # hisoblanadi, aks holda har 5 daqiqada qayta urinilaveradi.
            await record_donor_reminder(reservation["id"], None)
        except Exception:
            logger.exception("Yo'lga chiqarish eslatmasini yuborib bo'lmadi (bron %s)", reservation["id"])
        await asyncio.sleep(SEND_PAUSE_SECONDS)


async def _check_receive_reminders(bot: Bot) -> None:
    due = await get_due_receive_reminders(
        FIRST_REMINDER_AFTER, SECOND_REMINDER_AFTER, REPEAT_REMINDER_AFTER
    )
    for reservation in due:
        needy_lang = reservation["needy_language"] or "uz"
        try:
            message_id = await _send_with_retry(lambda: send_tracked_message(
                bot,
                reservation["needy_id"],
                reservation["needy_notify_message_id"],
                t(needy_lang, "receive_reminder"),
                reply_markup=_open_app_keyboard(needy_lang, "needy_cabinet"),
            ))
            await record_needy_reminder(reservation["id"], message_id)
        except TelegramForbiddenError:
            # Foydalanuvchi botni bloklagan — eslatma "yuborilgan" deb
            # hisoblanadi, aks holda har 5 daqiqada qayta urinilaveradi.
            await record_needy_reminder(reservation["id"], None)
        except Exception:
            logger.exception("Qabul qilish eslatmasini yuborib bo'lmadi (bron %s)", reservation["id"])
        await asyncio.sleep(SEND_PAUSE_SECONDS)


async def run_reminder_loop(bot: Bot) -> None:
    """Fonda ishlaydigan cheksiz tsikl — har CHECK_INTERVAL_SECONDS'da
    yo'lga chiqarilmagan va qabul qilinmagan bronlarni tekshirib,
    muddati o'tganlariga eslatma yuboradi."""
    while True:
        try:
            await _check_ship_reminders(bot)
            await _check_receive_reminders(bot)
        except Exception:
            logger.exception("Eslatma tsiklida xatolik")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
