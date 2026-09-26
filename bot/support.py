"""O'zimizning aloqa (qo'llab-quvvatlash) botimiz — Livegram o'rniga, reklamasiz.

Foydalanuvchi aloqa botiga yozgan har bir xabar (matn, rasm, ovoz, fayl...)
adminlarga yuboriladi: avval kimdan kelgani haqida qisqa sarlavha, keyin
xabarning o'zi. Admin shu xabarlardan biriga Reply qilib javob yozsa,
javob foydalanuvchiga bot nomidan boradi — admin akkaunti yashirin qoladi.
"""
import logging
import time
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import CommandStart
from aiogram.types import Message, ReactionTypeEmoji

from bot.config import SUPPORT_ADMIN_IDS
from bot.database import get_support_message_user, get_user_language, save_support_message
from bot.texts import LANGUAGES, t

logger = logging.getLogger(__name__)

router = Router()

# "Xabaringiz qabul qilindi" javobi har xabarga emas, foydalanuvchiga
# shuncha vaqtda bir marta yuboriladi (ketma-ket yozganda chat to'lmasin).
ACK_INTERVAL_SECONDS = 30 * 60
_last_ack: dict[int, float] = {}
# Adminga "kimdan" sarlavhasi ketma-ket xabarlarda takrorlanmaydi.
HEADER_INTERVAL_SECONDS = 10 * 60
_last_header: dict[tuple[int, int], float] = {}


def _is_admin(message: Message) -> bool:
    return bool(message.from_user) and message.from_user.id in SUPPORT_ADMIN_IDS


async def _lang_for(message: Message) -> str:
    """Asosiy botda tanlangan til; bo'lmasa Telegram ilovasi tili; bo'lmasa o'zbekcha."""
    lang = await get_user_language(message.from_user.id)
    if lang in LANGUAGES:
        return lang
    code = (message.from_user.language_code or "")[:2]
    return code if code in LANGUAGES else "uz"


@router.message(CommandStart())
async def on_start(message: Message) -> None:
    if _is_admin(message):
        await message.answer(
            "👋 Siz aloqa botining adminisiz.\n\n"
            "Foydalanuvchilar yozgan xabarlar shu yerga keladi. Javob berish uchun "
            "xabarga <b>Reply</b> (Ответить) qilib yozing — javob foydalanuvchiga "
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
        await bot.copy_message(chat_id=user_id, from_chat_id=message.chat.id, message_id=message.message_id)
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
    name = escape(user.full_name or "")
    username = f" (@{escape(user.username)})" if user.username else ""
    header = f"✉️ <b>Yangi xabar</b>\n👤 {name}{username}\n🆔 <code>{user.id}</code>"

    delivered = False
    now = time.time()
    for admin_id in SUPPORT_ADMIN_IDS:
        try:
            head = None
            if now - _last_header.get((admin_id, user.id), 0) > HEADER_INTERVAL_SECONDS:
                head = await bot.send_message(admin_id, header)
            copy = await bot.copy_message(
                chat_id=admin_id, from_chat_id=message.chat.id, message_id=message.message_id,
                reply_to_message_id=head.message_id if head else None,
            )
        except TelegramAPIError:
            logger.warning("Aloqa xabari adminga yetmadi (admin %s /start bosmagan bo'lishi mumkin)", admin_id)
            continue
        _last_header[(admin_id, user.id)] = now
        if head:
            await save_support_message(admin_id, head.message_id, user.id)
        await save_support_message(admin_id, copy.message_id, user.id)
        delivered = True

    if not delivered:
        logger.error("Aloqa xabari hech bir adminga yetmadi (SUPPORT_ADMIN_IDS: %s)", SUPPORT_ADMIN_IDS)
    if now - _last_ack.get(user.id, 0) > ACK_INTERVAL_SECONDS:
        _last_ack[user.id] = now
        await message.answer(t(await _lang_for(message), "support_received"))
