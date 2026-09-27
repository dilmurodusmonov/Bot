"""O'zimizning aloqa (qo'llab-quvvatlash) botimiz — Livegram o'rniga, reklamasiz.

Foydalanuvchi aloqa botiga yozgan har bir xabar (matn, rasm, ovoz, fayl...)
adminlarga uzatiladi (forward) — tepasida yozgan odamning avatari va ismi
ko'rinadi, bosilsa uning profili ochiladi. Admin shu xabarlardan biriga Reply qilib javob yozsa,
javob foydalanuvchiga bot nomidan boradi — admin akkaunti yashirin qoladi.

Aloqa botlari bir nechta bo'lishi mumkin (SUPPORT_BOT_TOKEN_2): foydalanuvchi
qaysi botga yozsa ham xabar har bir botdagi admin chatlariga keladi (admin
qaysi botga /start bosgan bo'lsa). Admin qaysi botdan javob yozsa ham, javob
foydalanuvchiga u yozgan bot orqali boradi. Botlar bir-birining chatidagi
xabarni nusxalay olmaydi va fayl ID'lari botga xos — boshqa bot orqali
yuborishda matn qayta yoziladi, fayllar yuklab olinib qayta yuklanadi.
"""
import logging
import time
from html import escape
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BufferedInputFile,
    CopyTextButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReactionTypeEmoji,
    ReplyParameters,
)

from bot.config import MINI_APP_SHORT_NAME, SUPPORT_ADMIN_IDS
from bot.database import (
    get_support_message_copies,
    get_support_message_target,
    get_user_language,
    save_support_message,
)
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


# Admin javobi foydalanuvchiga matnning o'zi bo'lib boradi, ostida
# "🤖 Ehson App" tugmasi — bosilsa Ehson App ochiladi (javobni ilovada
# tekshirish uchun). Asosiy bot nomi ma'lum bo'lmasa, belgi matn boshida.
REPLY_HEADER = "🤖 <b>Ehson App</b>\n\n"
REPLY_BUTTON_TEXT = "🤖 Ehson App"
# Izoh (caption) qo'shib bo'ladigan xabar turlari.
_CAPTION_TYPES = ("photo", "video", "document", "audio", "voice", "animation")


def _app_keyboard(main_bot_username: Optional[str]) -> Optional[InlineKeyboardMarkup]:
    if not main_bot_username:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text=REPLY_BUTTON_TEXT, url=f"https://t.me/{main_bot_username}/{MINI_APP_SHORT_NAME}",
    )]])


# Boshqa bot orqali qayta yuboriladigan fayl turlari: (maydon, usul, standart nom).
# animation document'dan oldin — GIF'da ikkalasi ham bo'ladi.
_MEDIA_KINDS = (
    ("photo", "send_photo", "photo.jpg"),
    ("animation", "send_animation", "animation.mp4"),
    ("video", "send_video", "video.mp4"),
    ("video_note", "send_video_note", "video_note.mp4"),
    ("sticker", "send_sticker", "sticker.webp"),
    ("voice", "send_voice", "voice.ogg"),
    ("audio", "send_audio", "audio.mp3"),
    ("document", "send_document", "file"),
)

Media = tuple[str, str, bytes, str]


async def _download_media(src: Bot, message: Message) -> Optional[Media]:
    """Xabardagi faylni src bot orqali yuklab oladi: (tur, usul, baytlar, nom)."""
    for kind, method, default_name in _MEDIA_KINDS:
        obj = getattr(message, kind)
        if not obj:
            continue
        if kind == "photo":
            obj = obj[-1]
        name = getattr(obj, "file_name", None) or default_name
        if kind == "sticker":
            name = "sticker.webm" if obj.is_video else "sticker.tgs" if obj.is_animated else name
        buf = await src.download(obj.file_id)
        return kind, method, buf.getvalue(), name
    return None


def _describe(message: Message) -> str:
    """Fayl bo'lmagan, boshqa bot orqali nusxalab bo'lmaydigan xabar turlari."""
    if message.location:
        return f"📍 {message.location.latitude}, {message.location.longitude}"
    if message.contact:
        c = message.contact
        return f"📞 {escape(' '.join(filter(None, [c.first_name, c.last_name])))}: {escape(c.phone_number)}"
    return f"[{message.content_type}]"


async def _copy(
    src: Bot, dst: Bot, chat_id: int, message: Message,
    caption: Optional[str] = None, reply_markup: Optional[InlineKeyboardMarkup] = None,
    media: Optional[Media] = None, reply_parameters: Optional[ReplyParameters] = None,
) -> Message:
    """message'ni chat_id ga dst bot orqali yuboradi. Bir bot bo'lsa —
    copy_message; boshqa bot bo'lsa matn qayta yoziladi, fayl qayta yuklanadi
    (media — oldindan yuklab olingan fayl, har admin uchun qayta yuklamaslik uchun)."""
    if src.id == dst.id:
        kwargs = {}
        if caption is not None:
            kwargs.update(caption=caption[:1024], parse_mode="HTML")
        if reply_markup is not None:
            kwargs["reply_markup"] = reply_markup
        if reply_parameters is not None:
            kwargs["reply_parameters"] = reply_parameters
        return await dst.copy_message(
            chat_id=chat_id, from_chat_id=message.chat.id, message_id=message.message_id, **kwargs,
        )
    if message.text:
        return await dst.send_message(
            chat_id, message.html_text, disable_web_page_preview=True, reply_markup=reply_markup,
            reply_parameters=reply_parameters,
        )
    if media is None:
        media = await _download_media(src, message)
    if media is None:
        return await dst.send_message(
            chat_id, (caption or "") + _describe(message), reply_markup=reply_markup,
            reply_parameters=reply_parameters,
        )
    kind, method, data, name = media
    kwargs = {
        kind: BufferedInputFile(data, filename=name),
        "reply_markup": reply_markup, "reply_parameters": reply_parameters,
    }
    if kind in _CAPTION_TYPES:
        text = caption if caption is not None else message.html_text
        if text:
            kwargs.update(caption=text[:1024], parse_mode="HTML")
    return await getattr(dst, method)(chat_id, **kwargs)


async def _send_reply_to_user(
    src: Bot, dst: Bot, user_id: int, message: Message, main_bot_username: Optional[str] = None,
) -> None:
    """Admin javobi (src botdagi xabar) foydalanuvchiga dst bot orqali."""
    keyboard = _app_keyboard(main_bot_username)
    header = "" if keyboard else REPLY_HEADER
    if message.text:
        await dst.send_message(
            user_id, header + message.html_text, disable_web_page_preview=True, reply_markup=keyboard,
        )
    elif any(getattr(message, kind) for kind in _CAPTION_TYPES):
        await _copy(src, dst, user_id, message, caption=header + (message.html_text or ""), reply_markup=keyboard)
    elif keyboard:
        # Stiker, dumaloq video va h.k. — tugma xabarning o'ziga biriktiriladi.
        await _copy(src, dst, user_id, message, reply_markup=keyboard)
    else:
        await dst.send_message(user_id, REPLY_HEADER.strip())
        await _copy(src, dst, user_id, message)


async def _copy_with_user_button(
    src: Bot, dst: Bot, admin_id: int, message: Message, media: Optional[Media] = None,
) -> Message:
    """Xabarning o'zi, ostida "👤 Ism" tugmasi — forward'da avatar ko'rinmaganda
    (foydalanuvchi uzatishni yashirgan) yoki xabar boshqa bot orqali kelganda.
    Tugma lichkani ochadi (username bo'lsa t.me, bo'lmasa tg://user?id=...);
    foydalanuvchi maxfiylik sababli ID orqali lichkaga ruxsat bermasa — ID nusxalanadi."""
    user = message.from_user
    label = f"👤 {user.full_name or user.id}"[:64]
    buttons = []
    if user.username:
        buttons.append(InlineKeyboardButton(text=label, url=f"https://t.me/{user.username}"))
    buttons.append(InlineKeyboardButton(text=label, url=f"tg://user?id={user.id}"))
    buttons.append(InlineKeyboardButton(text=label, copy_text=CopyTextButton(text=str(user.id))))
    for button in buttons:
        try:
            return await _copy(
                src, dst, admin_id, message, media=media,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[button]]),
            )
        except TelegramBadRequest as e:
            # Masalan BUTTON_USER_PRIVACY_RESTRICTED — keyingi variant.
            # Boshqa xato (admin botga /start bosmagan va h.k.) — tugma aybdor emas.
            if "BUTTON" not in str(e).upper():
                raise
    return await _copy(src, dst, admin_id, message, media=media)


async def _mirror_reply(
    src: Bot, dst: Bot, chat_id: int, message: Message, header: str, reply_to: int,
    media: Optional[Media] = None,
) -> Message:
    """Admin javobining nusxasi boshqa admin chatiga — foydalanuvchi xabari
    ostida (Reply), tepasida kim javob bergani."""
    reply = ReplyParameters(message_id=reply_to, allow_sending_without_reply=True)
    if message.text:
        return await dst.send_message(
            chat_id, header + message.html_text, disable_web_page_preview=True, reply_parameters=reply,
        )
    if any(getattr(message, kind) for kind in _CAPTION_TYPES):
        return await _copy(
            src, dst, chat_id, message, caption=header + (message.html_text or ""),
            media=media, reply_parameters=reply,
        )
    sent = await dst.send_message(chat_id, header.strip(), reply_parameters=reply)
    await _copy(src, dst, chat_id, message, media=media)
    return sent


async def _share_reply_with_admins(
    bot: Bot, message: Message, support_bots: dict[int, Bot],
    user_id: int, origin_bot_id: int, user_message_id: int,
) -> None:
    """Bir admin javob berdi — javob shu foydalanuvchi xabari kelgan boshqa
    admin chatlarida ham (boshqa botda ham) ko'rsatiladi. Nusxaga Reply
    qilinsa, u ham foydalanuvchiga boradi."""
    if not user_message_id:
        return
    header = f"↩️ <b>{escape(message.from_user.full_name or 'Admin', quote=False)}</b> javob berdi:\n\n"
    media: Optional[Media] = None
    media_loaded = False
    for bot_id, chat_id, message_id in await get_support_message_copies(user_id, origin_bot_id, user_message_id):
        if (bot_id or bot.id) == bot.id and chat_id == message.chat.id:
            continue
        dst = support_bots.get(bot_id) if bot_id else bot
        if dst is None:
            continue
        try:
            if dst.id != bot.id and not media_loaded and not message.text:
                media_loaded = True
                media = await _download_media(bot, message)
            sent = await _mirror_reply(bot, dst, chat_id, message, header, message_id, media)
        except TelegramAPIError:
            logger.warning("Admin javobi boshqa adminga ko'rsatilmadi (admin %s bot %s)", chat_id, bot_id)
            continue
        await save_support_message(dst.id, chat_id, sent.message_id, user_id, origin_bot_id, user_message_id)


@router.message(Command("id"))
async def on_id(message: Message) -> None:
    """Har kim o'z Telegram ID'sini bilib olishi uchun (admin ro'yxatiga qo'shishda kerak)."""
    await message.answer(f"🆔 Sizning Telegram ID: <code>{message.from_user.id}</code>")


@router.message(CommandStart())
async def on_start(message: Message) -> None:
    if _is_admin(message):
        await message.answer(
            "👋 Siz aloqa botining adminisiz.\n\n"
            "📩 Foydalanuvchilar yozgan xabarlar shu yerga keladi!\n"
            "✍️ Javob berish uchun xabarga <b>Reply</b> qilib yozing!\n"
            "🤖 Javob foydalanuvchiga bot nomidan boradi!\n"
            "👥 Boshqa adminlarning javoblari ham shu yerda ko'rinadi!"
        )
        return
    await message.answer(t(await _lang_for(message), "support_welcome"))


@router.message(F.reply_to_message, F.func(lambda m: m.from_user and m.from_user.id in SUPPORT_ADMIN_IDS))
async def on_admin_reply(
    message: Message, bot: Bot, main_bot_username: Optional[str] = None,
    support_bots: Optional[dict[int, Bot]] = None,
) -> None:
    """Admin foydalanuvchi xabariga Reply qildi — javobni foydalanuvchiga
    u yozgan bot orqali yuboramiz."""
    target = await get_support_message_target(bot.id, message.chat.id, message.reply_to_message.message_id)
    if not target:
        await message.reply("⚠️ Bu xabar qaysi foydalanuvchiniki ekanini topa olmadim. "
                            "Foydalanuvchidan kelgan xabarga Reply qiling.")
        return
    user_id, origin_bot_id, user_message_id = target
    dst = (support_bots or {}).get(origin_bot_id, bot)
    try:
        await _send_reply_to_user(bot, dst, user_id, message, main_bot_username)
    except TelegramAPIError as e:
        await message.reply(f"❌ Yuborilmadi: {escape(str(e))[:300]}\n(Foydalanuvchi botni bloklagan bo'lishi mumkin.)")
        return
    await _share_reply_with_admins(
        bot, message, support_bots or {bot.id: bot}, user_id, origin_bot_id or bot.id, user_message_id,
    )
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
async def on_user_message(message: Message, bot: Bot, support_bots: Optional[dict[int, Bot]] = None) -> None:
    """Foydalanuvchi xabari — har bir aloqa botidagi barcha adminlarga yuboriladi."""
    user = message.from_user
    if not user or message.chat.type != "private":
        return
    # Avval foydalanuvchi yozgan bot, keyin qolganlari.
    bots = sorted((support_bots or {bot.id: bot}).values(), key=lambda b: b.id != bot.id)
    media: Optional[Media] = None
    media_loaded = False
    delivered = False
    for dst in bots:
        for admin_id in SUPPORT_ADMIN_IDS:
            try:
                if dst.id == bot.id:
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
                        sent = await _copy_with_user_button(bot, bot, admin_id, message)
                else:
                    # Boshqa bot forward qila olmaydi — fayl bir marta yuklab
                    # olinadi va har bir adminga qayta yuklanadi.
                    if not media_loaded and not message.text:
                        media_loaded = True
                        media = await _download_media(bot, message)
                    sent = await _copy_with_user_button(bot, dst, admin_id, message, media)
            except TelegramAPIError:
                logger.warning("Aloqa xabari adminga yetmadi (admin %s bot %s ga /start bosmagan bo'lishi mumkin)",
                               admin_id, dst.id)
                continue
            await save_support_message(dst.id, admin_id, sent.message_id, user.id, bot.id, message.message_id)
            delivered = True

    if not delivered:
        logger.error("Aloqa xabari hech bir adminga yetmadi (SUPPORT_ADMIN_IDS: %s)", SUPPORT_ADMIN_IDS)
    if not delivered:
        return
    # Xabar qabul qilinganini 👍 reaksiya bilan tasdiqlaymiz (chatda ortiqcha
    # matn yo'q). Reaksiya qo'yib bo'lmasa — matnli javob (30 daqiqada bir marta).
    try:
        await bot.set_message_reaction(
            chat_id=message.chat.id, message_id=message.message_id,
            reaction=[ReactionTypeEmoji(emoji="👍")],
        )
        return
    except TelegramAPIError:
        pass
    now = time.time()
    if now - _last_ack.get(user.id, 0) > ACK_INTERVAL_SECONDS:
        _last_ack[user.id] = now
        await message.answer(t(await _lang_for(message), "support_received"))
