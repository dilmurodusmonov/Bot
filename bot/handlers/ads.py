"""Admin chekni ko'rib "Tasdiqlash"/"Rad etish" tugmasini bosganda."""
import logging
from html import escape

from typing import Optional

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from bot.ad_payments import (
    CALLBACK_PREFIX,
    REJECT_REASONS,
    admin_keyboard,
    decided_keyboard,
    format_som,
    reject_reasons_keyboard,
)
from bot.config import AD_ADMIN_IDS
from bot.database import decide_ad_payment, get_ad_payment, get_bot_stats, get_user
from bot.texts import t

router = Router()


class AdReject(StatesGroup):
    """Admin "Boshqa sabab"ni tanlab, sababni matn bilan yozmoqda."""
    waiting_reason = State()


async def _finish_decision(
    bot: Bot, admin_id: int, payment_id: int, approve: bool,
    reason_code: Optional[str] = None, reason_text: Optional[str] = None,
) -> Optional[dict]:
    """To'lovni hal qiladi va to'lovchiga xabar beradi. Allaqachon hal
    qilingan bo'lsa None."""
    stored_reason = REJECT_REASONS[reason_code][1] if reason_code else reason_text
    result = await decide_ad_payment(payment_id, approve, admin_id, stored_reason)
    if result is None:
        return None
    payment, bid = result["payment"], result["bid"]
    # To'lovchining o'zi qaror qilgan admin bo'lsa, admin xabaridagi holat
    # yetarli — alohida bildirishnoma yuborilmaydi.
    if payment["telegram_id"] == admin_id:
        return result

    user = await get_user(payment["telegram_id"])
    lang = (user or {}).get("language") or "uz"
    brand = escape(bid["brand_name"]) if bid else ""
    if approve:
        key = "ad_payment_approved_new" if payment["kind"] == "new" else "ad_payment_approved_raise"
        text = t(lang, key, brand=brand, amount=format_som(payment["amount"]))
    else:
        reason = t(lang, REJECT_REASONS[reason_code][1]) if reason_code else escape(reason_text or "")
        text = t(lang, "ad_payment_rejected_reason", brand=brand, reason=reason)
    try:
        await bot.send_message(payment["telegram_id"], text)
    except TelegramAPIError:
        logging.warning("Reklama to'lovi haqida foydalanuvchiga xabar yuborilmadi: %s", payment["telegram_id"])
    return result


def _status_line(approve: bool, reason_code: Optional[str] = None, reason_text: Optional[str] = None) -> str:
    if approve:
        return "✅ <b>Tasdiqlandi</b>"
    reason = REJECT_REASONS[reason_code][0] if reason_code else escape(reason_text or "")
    return f"❌ <b>Rad etildi</b>\nSabab: {reason}"


@router.callback_query(F.data.startswith(CALLBACK_PREFIX + ":"))
async def on_ad_payment_decision(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user.id not in AD_ADMIN_IDS:
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    parts = callback.data.split(":")
    try:
        action, payment_id = parts[1], int(parts[2])
    except (IndexError, ValueError):
        await callback.answer()
        return
    payment = await get_ad_payment(payment_id)
    receipt_file_id = payment["receipt_file_id"] if payment else None

    if action == "view":
        await callback.answer()
        if receipt_file_id:
            await callback.message.answer_photo(receipt_file_id, caption=f"🧾 Chek #{payment_id}")
        return

    if payment is None or payment["status"] != "pending":
        await callback.answer("Bu to'lov allaqachon ko'rib chiqilgan", show_alert=True)
        return

    # "Rad etish" — avval sabab so'raladi; "Orqaga" — asl tugmalar.
    if action in ("no", "back"):
        keyboard = (
            reject_reasons_keyboard(payment_id, receipt_file_id) if action == "no"
            else admin_keyboard(payment_id, receipt_file_id)
        )
        try:
            await callback.message.edit_reply_markup(reply_markup=keyboard)
        except TelegramAPIError:
            pass
        await callback.answer("Rad etish sababini tanlang" if action == "no" else None)
        return

    if action == "rc":
        await state.set_state(AdReject.waiting_reason)
        await state.update_data(
            payment_id=payment_id,
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            original_html=callback.message.html_text,
        )
        await callback.answer()
        await callback.message.answer(
            f"✍️ #{payment_id} to'lovni rad etish sababini yozing — foydalanuvchiga shu matn yuboriladi.\n"
            "Bekor qilish: /cancel"
        )
        return

    if action == "ok":
        approve, reason_code = True, None
    elif action == "rj" and len(parts) == 4 and parts[3] in REJECT_REASONS:
        approve, reason_code = False, parts[3]
    else:
        await callback.answer()
        return

    result = await _finish_decision(callback.bot, callback.from_user.id, payment_id, approve, reason_code)
    if result is None:
        await callback.answer("Bu to'lov allaqachon ko'rib chiqilgan", show_alert=True)
        return
    try:
        await callback.message.edit_text(
            f"{callback.message.html_text}\n\n{_status_line(approve, reason_code)}",
            reply_markup=decided_keyboard(payment_id, receipt_file_id),
            disable_web_page_preview=True,
        )
    except TelegramAPIError:
        pass
    await callback.answer("Tasdiqlandi" if approve else "Rad etildi")


@router.message(StateFilter(AdReject.waiting_reason), F.text)
async def on_custom_reject_reason(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()
    # /cancel (yoki istalgan boshqa buyruq) sabab sifatida olinmaydi.
    if message.text.strip().startswith("/") or message.text.strip().lower() == "bekor":
        await message.answer("Bekor qilindi. To'lov hali ham kutilmoqda.")
        return
    reason_text = message.text.strip()[:300]
    payment_id = data["payment_id"]
    result = await _finish_decision(message.bot, message.from_user.id, payment_id, False, reason_text=reason_text)
    if result is None:
        await message.answer("Bu to'lov allaqachon ko'rib chiqilgan.")
        return
    try:
        await message.bot.edit_message_text(
            f"{data['original_html']}\n\n{_status_line(False, reason_text=reason_text)}",
            chat_id=data["chat_id"], message_id=data["message_id"],
            reply_markup=decided_keyboard(payment_id, result["payment"]["receipt_file_id"]),
            disable_web_page_preview=True,
        )
    except TelegramAPIError:
        pass
    await message.answer(f"❌ #{payment_id} rad etildi. Sabab foydalanuvchiga yuborildi.")


@router.message(Command("stats"), F.from_user.id.in_(AD_ADMIN_IDS))
async def on_stats(message: Message) -> None:
    """Admin uchun: foydalanuvchilar va tashrif buyuruvchilar soni (reklama
    sahifasidagi "N onlayn · M tashrif buyuruvchi" shu yerdan)."""
    st = await get_bot_stats()
    num = lambda n: f"{n:,}".replace(",", " ")  # noqa: E731
    await message.answer(
        "📊 <b>Statistika</b>\n\n"
        f"👥 Bot foydalanuvchilari (/start): <b>{num(st['users'])}</b> (bugun +{num(st['users_new_day'])})\n"
        f"🚶 Tashrif buyuruvchilar: <b>{num(st['visitors'])}</b>\n"
        f"🟢 Hozir onlayn (2 daqiqa): <b>{num(st['online'])}</b>\n"
        f"📅 Oxirgi 24 soatda faol: <b>{num(st['active_day'])}</b>\n"
        f"🗓 Oxirgi 7 kunda faol: <b>{num(st['active_week'])}</b>\n"
        f"👁 Reklama banneri ko'rishlari: <b>{num(st['banner_views'])}</b>\n"
        f"📢 Reytingdagi reklamalar: <b>{num(st['ads'])}</b>",
        parse_mode="HTML",
    )


@router.message(Command("logo"), F.from_user.id.in_(AD_ADMIN_IDS))
async def on_logo_debug(message: Message, command: CommandObject) -> None:
    """Admin uchun tashxis: /logo click.uz — logotip qidiruvining har bir
    manbasi natijasi va topilgan rasm. Admin bo'lmaganlarga filtr mos
    kelmaydi va odatiy javob beriladi."""
    from bot.webapp_api import _resolve_logo_for_url  # aylanma importdan qochish

    raw = (command.args or "").strip()
    if not raw:
        await message.answer("Foydalanish: /logo click.uz")
        return
    url = raw if raw.lower().startswith(("http://", "https://")) else "https://" + raw
    await message.answer("🔎 Qidirilmoqda...")
    trace: list = []
    try:
        logo = await _resolve_logo_for_url(url, trace)
    except Exception as e:  # tashxis — xatoni ham ko'rsatamiz
        await message.answer(f"Xato: {escape(repr(e))[:3500]}")
        return

    lines = [f"<b>{escape(url)}</b>", "Topildi ✅" if logo else "Topilmadi ❌"]
    for step in trace:
        if "tried" in step:
            lines.append(f"\nXost: {escape(step['host'])} · sayt ochiq: {step['site_allowed']} · HTML: {step['html']}")
            lines.extend("• " + escape(t) for t in step["tried"])
        else:
            lines.append(f"Yakuniy manzil: {escape(str(step.get('final_url')))}")
    text = "\n".join(lines)
    await message.answer(text[:4000], disable_web_page_preview=True)
    if logo:
        body, ctype = logo
        ext = "png" if "png" in ctype else "jpg" if "jpeg" in ctype else "img"
        try:
            await message.answer_document(BufferedInputFile(body, filename=f"logo.{ext}"), caption=ctype)
        except TelegramAPIError:
            pass


@router.message(Command("preview"), F.from_user.id.in_(AD_ADMIN_IDS))
async def on_preview_debug(message: Message, command: CommandObject) -> None:
    """Admin uchun tashxis: /preview bank.uz — sayt har bir so'rovga (brauzer,
    preview botlari) nima javob bergani va yakuniy nom/tavsif/rasm."""
    from bot.webapp_api import _FETCH_TRACE, _AdPreviewError, _fetch_ad_preview  # aylanma importdan qochish

    raw = (command.args or "").strip()
    if not raw:
        await message.answer("Foydalanish: /preview bank.uz")
        return
    await message.answer("🔎 Tekshirilmoqda...")
    trace: list = []
    token = _FETCH_TRACE.set(trace)
    try:
        result = await _fetch_ad_preview(message.bot, raw)
    except _AdPreviewError as e:
        result = {"xato": e.reason}
    except Exception as e:  # tashxis — xatoni ham ko'rsatamiz
        result = {"xato": repr(e)}
    finally:
        _FETCH_TRACE.reset(token)

    lines = [f"<b>{escape(raw)}</b>", "", "<b>So'rovlar:</b>"]
    lines += [f"• {escape(step)}" for step in trace] or ["• (sahifa so'ralmadi)"]
    lines += ["", "<b>Natija:</b>"]
    for key in ("title", "description", "photo_url", "xato"):
        if key in result:
            lines.append(f"{key}: {escape(str(result[key]) or '—')[:300]}")
    await message.answer("\n".join(lines)[:4000], disable_web_page_preview=True)
