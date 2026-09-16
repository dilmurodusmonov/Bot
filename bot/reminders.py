import asyncio
import logging
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Optional

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from bot.config import WEBAPP_URL
from bot.database import (
    get_donation,
    get_reservations_pending_receive,
    get_reservations_pending_ship,
    get_user,
    record_donor_reminder,
    record_needy_reminder,
)
from bot.notify import send_tracked_message
from bot.texts import t

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 5 * 60

# Birinchi eslatma holat boshlanganidan 12 soat o'tgach, ikkinchisi undan
# 6 soat keyin, keyingilari esa har 1 soatda — javob berilmaguncha yoki
# ehson keyingi holatga (masalan, "yetib bordi"ga) o'tmaguncha davom etadi.
FIRST_REMINDER_AFTER = timedelta(hours=12)
SECOND_REMINDER_AFTER = timedelta(hours=6)
REPEAT_REMINDER_AFTER = timedelta(hours=1)


def _is_due(
    state_started_at: datetime, last_reminder_at: Optional[datetime], reminder_count: int
) -> bool:
    now = datetime.now(timezone.utc)
    if reminder_count == 0:
        threshold = state_started_at + FIRST_REMINDER_AFTER
    elif reminder_count == 1:
        threshold = last_reminder_at + SECOND_REMINDER_AFTER
    else:
        threshold = last_reminder_at + REPEAT_REMINDER_AFTER
    return now >= threshold


async def _lang_for(telegram_id: int) -> str:
    user = await get_user(telegram_id)
    return (user and user["language"]) or "uz"


def _open_app_keyboard(lang: str, screen: str) -> Optional[InlineKeyboardMarkup]:
    if not WEBAPP_URL:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=t(lang, "open_app_button"),
            web_app=WebAppInfo(url=f"{WEBAPP_URL}&screen={screen}"),
        )
    ]])


async def _check_ship_reminders(bot: Bot) -> None:
    for reservation in await get_reservations_pending_ship():
        if not _is_due(
            reservation["created_at"],
            reservation["donor_last_reminder_at"],
            reservation["donor_reminder_count"],
        ):
            continue
        donation_id = reservation["donation_id"]
        donation = await get_donation(donation_id)
        if not donation:
            continue
        donor_lang = await _lang_for(donation["donor_id"])
        try:
            message_id = await send_tracked_message(
                bot,
                donation["donor_id"],
                reservation["donor_notify_message_id"],
                t(
                    donor_lang,
                    "ship_reminder",
                    description=escape(donation["description"] or "", quote=False),
                ),
                reply_markup=_open_app_keyboard(donor_lang, "donor_cabinet"),
            )
            await record_donor_reminder(reservation["id"], message_id)
        except Exception:
            logger.exception("Yo'lga chiqarish eslatmasini yuborib bo'lmadi (bron %s)", reservation["id"])


async def _check_receive_reminders(bot: Bot) -> None:
    for reservation in await get_reservations_pending_receive():
        if not _is_due(
            reservation["shipped_at"],
            reservation["needy_last_reminder_at"],
            reservation["needy_reminder_count"],
        ):
            continue
        needy_lang = await _lang_for(reservation["needy_id"])
        try:
            message_id = await send_tracked_message(
                bot,
                reservation["needy_id"],
                reservation["needy_notify_message_id"],
                t(needy_lang, "receive_reminder"),
                reply_markup=_open_app_keyboard(needy_lang, "needy_cabinet"),
            )
            await record_needy_reminder(reservation["id"], message_id)
        except Exception:
            logger.exception("Qabul qilish eslatmasini yuborib bo'lmadi (bron %s)", reservation["id"])


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
