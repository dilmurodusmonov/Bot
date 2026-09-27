"""O'zimizning aloqa (qo'llab-quvvatlash) botimiz — Livegram o'rniga, reklamasiz.

Foydalanuvchi aloqa botiga yozgan har bir xabar (matn, rasm, ovoz, fayl...)
adminlarga uzatiladi (forward) — tepasida yozgan odamning avatari va ismi
ko'rinadi, bosilsa uning profili ochiladi. Admin shu xabarlardan biriga Reply qilib javob yozsa,
javob foydalanuvchiga bot nomidan boradi — admin akkaunti yashirin qoladi.
"""
import logging
import time
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.types import (
    CopyTextButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReactionTypeEmoji,
)

from bot.config import SUPPORT_ADMIN_IDS
from bot.database import get_support_message_user, get_user_language, save_support_message
from bot.texts import LANGUAGES, t

logger = logging.getLogger(__name__)

router = Router()

# "Xabaringiz qabul qilindi" javobi har xabarga emas, foydalanuvchiga
# shuncha vaqtda bir marta yuboriladi (ketma-ket yozganda chat to'lmasin).
ACK_INTERVAL_SECONDS = 30 * 60
_last_ack: dict[int, float] = {}


def _is_admin(message: Message) -> bool:
    return bool(message.from_user) and message.from_user.id in SUPPORT_ADMIN_IDS


async def _lang_for(message: Message) -> str:
    """Asosiy botda tanlangan til; bo'lmasa Telegram ilovasi tili; bo'lmasa o'zbekcha."""
    lang = await get_user_language(message.from_user.id)
    if lang in LANGUAGES:
        return lang
    code = (message.from_user.language_code or "")[:2]
    return code if code in LANGUAGES else "uz"


# Admin javobi foydalanuvchiga shu belgi bilan boradi — javob Ehson App
# jamoasidan ekani darhol ajralib turadi.
REPLY_HEADER = "🤖 <b>Ehson App</b>\n\n"
# Izoh (caption) qo'shib bo'ladigan xabar turlari.
_CAPTION_TYPES = ("photo", "video", "document", "audio", "voice", "animation")


async def _send_reply_to_user(bot: Bot, user_id: int, message: Message) -> None:
    if message.text:
        await bot.send_message(user_id, REPLY_HEADER + message.html_text, disable_web_page_preview=True)
    elif any(getattr(message, kind) for kind in _CAPTION_TYPES):
        caption = REPLY_HEADER + (message.html_text or "")
        await bot.copy_message(
            chat_id=user_id, from_chat_id=message.chat.id, message_id=message.message_id,
            caption=caption[:1024], parse_mode="HTML",
        )
    else:
        # Stiker, dumaloq video va h.k. — izoh qo'yib bo'lmaydi: avval belgi, keyin xabar.
        await bot.send_message(user_id, REPLY_HEADER.strip())
        await bot.copy_message(chat_id=user_id, from_chat_id=message.chat.id, message_id=message.message_id)


async def _copy_with_user_button(bot: Bot, admin_id: int, message: Message) -> Message:
    """Forward'da avatar ko'rinmaganda (foydalanuvchi uzatishni yashirgan):
    xabarning o'zi nusxalanadi, ostida "👤 Ism" tugmasi. Tugma lichkani
    ochadi (username bo'lsa t.me, bo'lmasa tg://user?id=...); foydalanuvchi
    maxfiylik sababli ID orqali lichkaga ruxsat bermasa — ID nusxalanadi."""
    user = message.from_user
    label = f"👤 {user.full_name or user.id}"[:64]
    buttons = []
    if user.username:
        buttons.append(InlineKeyboardButton(text=label, url=f"https://t.me/{user.username}"))
    buttons.append(InlineKeyboardButton(text=label, url=f"tg://user?id={user.id}"))
    buttons.append(InlineKeyboardButton(text=label, copy_text=CopyTextButton(text=str(user.id))))
    for button in buttons:
        try:
            return await bot.copy_message(
                chat_id=admin_id, from_chat_id=message.chat.id, message_id=message.message_id,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[button]]),
            )
        except TelegramBadRequest:
            # Masalan BUTTON_USER_PRIVACY_RESTRICTED — keyingi variant.
            continue
    return await bot.copy_message(chat_id=admin_id, from_chat_id=message.chat.id, message_id=message.message_id)


@router.message(CommandStart())
async def on_start(message: Message) -> None:
    if _is_admin(message):
        await message.answer(
            "👋 Siz aloqa botining adminisiz.\n\n"
            "Foydalanuvchilar yozgan xabarlar shu yerga keladi. Javob berish uchun "
            "xabarga <b>Reply</b> qilib yozing — javob foydalanuvchiga "
            "bot nomidan boradi."
        )
        return
    await message.answer(t(await _lang_for(message), "support_welcome"))


@router.message(F.reply_to_message, F.func(lambda m: m.from_user and m.from_user.id in SUPPORT_ADMIN_IDS))
async def on_admin_reply(message: Message, bot: Bot) -> None:
    """Admin foydalanuvchi xabariga Reply qildi — javobni foydalanuvchiga yuboramiz."""
    user_id = await get_support_message_user(message.chat.id, message.reply_to_message.message_id)
    if not user_id:
        await message.reply("⚠️ Bu xabar qaysi foydalanuvchiniki ekanini topa olmadim. "
                            "Foydalanuvchidan kelgan xabarga Reply qiling.")
        return
    try:
        await _send_reply_to_user(bot, user_id, message)
    except TelegramAPIError as e:
        await message.reply(f"❌ Yuborilmadi: {escape(str(e))[:300]}\n(Foydalanuvchi botni bloklagan bo'lishi mumkin.)")
        return
    try:
        await bot.set_message_reaction(
            chat_id=message.chat.id, message_id=message.message_id,
            reaction=[ReactionTypeEmoji(emoji="👍")],
        )
    except TelegramAPIError:
        await message.reply("✅ Yuborildi")


@router.message(F.func(lambda m: m.from_user and m.from_user.id in SUPPORT_ADMIN_IDS))
async def on_admin_message(message: Message) -> None:
    await message.reply("ℹ️ Javob berish uchun foydalanuvchidan kelgan xabarga <b>Reply</b> qiling.")


@router.message()
async def on_user_message(message: Message, bot: Bot) -> None:
    """Foydalanuvchi xabari — barcha adminlarga yuboriladi."""
    user = message.from_user
    if not user or message.chat.type != "private":
        return
    delivered = False
    for admin_id in SUPPORT_ADMIN_IDS:
        try:
            # Forward: xabar tepasida foydalanuvchining avatari va ismi
            # ko'rinadi, ism bosilsa profili/lichkasi ochiladi.
            sent = await bot.forward_message(
                chat_id=admin_id, from_chat_id=message.chat.id, message_id=message.message_id,
            )
            # Foydalanuvchi uzatishni yashirgan bo'lsa avatar ko'rinmaydi —
            # forward o'rniga xabarning o'zi "👤 Ism" tugmasi bilan yuboriladi.
            if getattr(sent.forward_origin, "type", None) == "hidden_user":
                try:
                    await bot.delete_message(chat_id=admin_id, message_id=sent.message_id)
                except TelegramAPIError:
                    pass
                sent = await _copy_with_user_button(bot, admin_id, message)
        except TelegramAPIError:
            logger.warning("Aloqa xabari adminga yetmadi (admin %s /start bosmagan bo'lishi mumkin)", admin_id)
            continue
        await save_support_message(admin_id, sent.message_id, user.id)
        delivered = True

    if not delivered:
        logger.error("Aloqa xabari hech bir adminga yetmadi (SUPPORT_ADMIN_IDS: %s)", SUPPORT_ADMIN_IDS)
    now = time.time()
    if now - _last_ack.get(user.id, 0) > ACK_INTERVAL_SECONDS:
        _last_ack[user.id] = now
        await message.answer(t(await _lang_for(message), "support_received"))
