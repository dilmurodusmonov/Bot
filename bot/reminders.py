import asyncio
import logging
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from bot.config import WEBAPP_URL
from bot.database import (
    get_due_receive_reminders,
    get_due_ship_reminders,
    get_next_reminder_due,
    record_donor_reminder,
    record_needy_reminder,
)
from bot.notify import WIDE_BUBBLE_PAD, send_tracked_message
from bot.texts import category_name, t

logger = logging.getLogger(__name__)

# Tsikl keyingi eslatma vaqtigacha uxlaydi (bazani keraksiz uyg'otmaslik
# uchun — Neon bepul tarifida baza ishlash soatlari cheklangan). Yangi bron
# yoki yo'lga chiqarishda wake_reminders() uni uyg'otadi; har ehtimolga
# qarshi ko'pi bilan 6 soatda bir tekshiriladi.
MIN_SLEEP_SECONDS = 60
MAX_SLEEP_SECONDS = 6 * 3600
_wake_event: Optional[asyncio.Event] = None


def wake_reminders() -> None:
    """Yangi eslatma vaqti paydo bo'ldi (bron, yo'lga chiqarish) — tsikl qayta hisoblaydi."""
    if _wake_event is not None:
        _wake_event.set()

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
    """Fonda ishlaydigan cheksiz tsikl — yo'lga chiqarilmagan va qabul
    qilinmagan bronlarni tekshirib, muddati o'tganlariga eslatma yuboradi,
    so'ng keyingi eslatma vaqtigacha uxlaydi."""
    global _wake_event
    _wake_event = asyncio.Event()
    while True:
        delay = MAX_SLEEP_SECONDS
        try:
            await _check_ship_reminders(bot)
            await _check_receive_reminders(bot)
            next_due = await get_next_reminder_due(
                FIRST_REMINDER_AFTER, SECOND_REMINDER_AFTER, REPEAT_REMINDER_AFTER
            )
            if next_due is not None:
                delay = (next_due - datetime.now(timezone.utc)).total_seconds()
            delay = min(max(delay, MIN_SLEEP_SECONDS), MAX_SLEEP_SECONDS)
        except Exception:
            logger.exception("Eslatma tsiklida xatolik")
            delay = 5 * 60
        _wake_event.clear()
        try:
            await asyncio.wait_for(_wake_event.wait(), timeout=delay)
        except asyncio.TimeoutError:
            pass
