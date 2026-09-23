import asyncio
import ipaddress
import json
import logging
import re
from html import escape, unescape
from typing import Any, Optional
from urllib.parse import urlparse

import aiohttp
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import (
    BufferedInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    WebAppInfo,
)
from aiohttp import web

from bot.collage import build_collage
from bot.config import BASE_URL, CHANNEL_ID, MINI_APP_SHORT_NAME, WEBAPP_URL
from bot.database import (
    cancel_reservation,
    count_pending_receive,
    count_pending_ship,
    create_donation,
    create_reservation,
    create_user_if_missing,
    count_new_donations_last_24h,
    delete_donation,
    claim_ad_bids_for_description,
    fill_ad_bid_preview,
    get_ad_bids_ranked,
    increment_ad_bid_clicks,
    increment_ad_views,
    increment_donation_share,
    get_active_reservation_for_donation,
    get_available_donations,
    get_donation,
    get_donations_by_donor,
    get_like_info,
    get_reservation,
    get_category_stats,
    get_reservations_by_needy,
    get_stats,
    get_user,
    set_donation_channel_messages,
    set_donation_status,
    set_donor_notify_message,
    set_needy_notify_message,
    set_reservation_received,
    set_reservation_shipped,
    set_user_language,
    set_user_role,
    toggle_donation_like,
    insert_ad_bid,
)
from bot.notify import send_tracked_message as _send_tracked_message
from bot.texts import (
    CATEGORIES,
    CHANNEL_OPEN_BUTTON,
    LANGUAGES,
    category_name,
    status_label,
    t,
)
from bot.webapp_auth import validate_init_data

logger = logging.getLogger(__name__)


# --- kanalga e'lon qilish ----------------------------------------------------

def _donation_photo_ids(donation: dict) -> list[str]:
    return [
        pid for pid in (
            donation["photo_file_id"],
            donation.get("photo_file_id_2"),
            donation.get("photo_file_id_3"),
        ) if pid
    ]


def _channel_message_ids(donation: dict) -> list[int]:
    raw = donation.get("channel_message_ids") if donation else None
    if not raw:
        return []
    return [int(part) for part in raw.split(",") if part]


def _app_url(bot_username: Optional[str], donation_id: int) -> Optional[str]:
    """Mini App'ni to'g'ridan-to'g'ri shu ehson ustida ochadigan havola."""
    if not bot_username:
        return None
    return f"https://t.me/{bot_username}/{MINI_APP_SHORT_NAME}?startapp=d_{donation_id}"


def _channel_caption(
    bot_username: Optional[str], donation_id: int, status: str
) -> str:
    """Post sarlavhasi — holat yorlig'i, qalin va havorang.

    Telegram'da matn rangini belgilaydigan teg yo'q: havorang faqat
    havoladan chiqadi. Shuning uchun yorliq ilovaga olib boradigan
    havolaga o'raladi — bosilsa ehson ilovada ochiladi."""
    label = f"<b>{escape(status_label(status, 'uz'), quote=False)}</b>"
    url = _app_url(bot_username, donation_id)
    return f'<a href="{escape(url)}">{label}</a>' if url else label


def _receipt_keyboard(
    lang: str,
    reservation_id: int,
    screen: str,
    active_tab: str = "shipped",
    button_text_key: str = "view_receipt_button",
) -> Optional[InlineKeyboardMarkup]:
    """Bot chatida chek rasmini katta holda ko'rsatish o'rniga, qisqa
    matnli xabar ostiga tugma qo'yiladi — bosilganda Mini App aynan
    shu chekni ko'rsatadigan bo'limda ochiladi (deep-link, bootstrap
    kodidagi "r" parametri orqali)."""
    if not WEBAPP_URL:
        return None
    url = f"{WEBAPP_URL}&screen={screen}&activeTab={active_tab}&r={reservation_id}"
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, button_text_key), web_app=WebAppInfo(url=url))
    ]])


def _channel_keyboard(
    bot_username: Optional[str], donation_id: int, status: str
) -> Optional[InlineKeyboardMarkup]:
    """Ilovaga o'tish tugmasi. Tugma suratga biriktirilgani uchun Telegram
    uni har doim surat kengligida chizadi — qurilma ekrani va shrift
    o'lchamidan qat'i nazar. Ehson band qilinganda tugma olib
    tashlanadi."""
    url = _app_url(bot_username, donation_id)
    if not url or status != "available":
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=CHANNEL_OPEN_BUTTON, url=url)]]
    )


async def _download_photo(bot: Bot, file_id: str) -> bytes:
    file = await bot.get_file(file_id)
    buf = await bot.download_file(file.file_path)
    return buf.read()


async def _channel_photo(bot: Bot, photo_ids: list[str]):
    """Kanalga yuboriladigan surat. Bir nechta rasm bo'lsa ular bitta
    kollajga birlashtiriladi — shunda post bitta surat bo'lib chiqadi va
    tugma aynan surat kengligida turadi."""
    if len(photo_ids) == 1:
        return photo_ids[0]
    photos = [await _download_photo(bot, pid) for pid in photo_ids]
    return BufferedInputFile(build_collage(photos), filename="ehson.jpg")


async def _publish_to_channel(
    bot: Bot, bot_username: Optional[str], donation_id: int
) -> None:
    """Yangi ehsonni kanalga bitta surat va tugma bilan e'lon qiladi.

    Kanal bilan bog'liq har qanday muammo (bot admin emas, rasm yuklab
    olinmadi va h.k.) ehson joylanishini buzmasligi kerak — funksiya fon
    vazifasi sifatida chaqiriladi va barcha xatolar jurnalga yoziladi."""
    if not CHANNEL_ID:
        return
    try:
        donation = await get_donation(donation_id)
        if not donation:
            return
        photo_ids = _donation_photo_ids(donation)
        if not photo_ids:
            return
        msg = await bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=await _channel_photo(bot, photo_ids),
            caption=_channel_caption(bot_username, donation_id, "available"),
            reply_markup=_channel_keyboard(bot_username, donation_id, "available"),
        )
        await set_donation_channel_messages(donation_id, [msg.message_id])
    except Exception:
        logger.exception("Kanalga e'lon qilib bo'lmadi (ehson %s)", donation_id)


async def _refresh_channel_post(
    bot: Bot, bot_username: Optional[str], donation_id: int, status: str
) -> None:
    """Post sarlavhasidagi holatni yangilaydi va ehson band qilinganda
    tugmani olib tashlaydi."""
    if not CHANNEL_ID:
        return
    donation = await get_donation(donation_id)
    message_ids = _channel_message_ids(donation)
    if not message_ids:
        return
    try:
        await bot.edit_message_caption(
            chat_id=CHANNEL_ID,
            message_id=message_ids[0],
            caption=_channel_caption(bot_username, donation_id, status),
            reply_markup=_channel_keyboard(bot_username, donation_id, status),
        )
    except Exception:
        logger.exception("Kanal postini yangilab bo'lmadi (ehson %s)", donation_id)


async def _remove_channel_post(bot: Bot, donation: dict) -> None:
    message_ids = _channel_message_ids(donation)
    if not CHANNEL_ID or not message_ids:
        return
    for message_id in message_ids:
        try:
            await bot.delete_message(chat_id=CHANNEL_ID, message_id=message_id)
        except Exception:
            logger.exception("Kanal postini o'chirib bo'lmadi (xabar %s)", message_id)


def _auth_telegram_id(request: web.Request) -> Optional[int]:
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    user = validate_init_data(init_data)
    return user["id"] if user else None


async def _require_user_id(request: web.Request) -> int:
    telegram_id = _auth_telegram_id(request)
    if telegram_id is None:
        raise web.HTTPUnauthorized(text="invalid init data")
    return telegram_id


async def _lang_for(telegram_id: int) -> str:
    user = await get_user(telegram_id)
    return (user and user["language"]) or "uz"


async def _read_multipart_photo(request: web.Request) -> tuple[dict, bytes, str]:
    """Mini App'dan multipart/form-data orqali kelgan matn maydonlari va rasmni o'qiydi."""
    fields: dict[str, str] = {}
    photo_bytes: Optional[bytes] = None
    filename = "photo.jpg"

    reader = await request.multipart()
    while True:
        field = await reader.next()
        if field is None:
            break
        if field.name == "photo":
            filename = field.filename or filename
            photo_bytes = await field.read(decode=False)
        else:
            fields[field.name] = await field.text()

    if not photo_bytes:
        raise web.HTTPBadRequest(text="photo required")
    return fields, photo_bytes, filename


MAX_DONATION_PHOTOS = 3


async def _read_multipart_photos(request: web.Request) -> tuple[dict, list[tuple[bytes, str]]]:
    """Mini App'dan multipart/form-data orqali kelgan matn maydonlari va bir nechta
    (max MAX_DONATION_PHOTOS) rasmni o'qiydi."""
    fields: dict[str, str] = {}
    photos: list[tuple[bytes, str]] = []

    reader = await request.multipart()
    while True:
        field = await reader.next()
        if field is None:
            break
        if field.name == "photo":
            filename = field.filename or "photo.jpg"
            photo_bytes = await field.read(decode=False)
            if len(photos) < MAX_DONATION_PHOTOS:
                photos.append((photo_bytes, filename))
        else:
            fields[field.name] = await field.text()

    if not photos:
        raise web.HTTPBadRequest(text="photo required")
    return fields, photos


def _donation_json(
    d: dict, lang: str, like_count: int = 0, liked_by_me: bool = False,
    viewer_id: Optional[int] = None,
) -> dict:
    photo_ids = [d["photo_file_id"]]
    if d.get("photo_file_id_2"):
        photo_ids.append(d["photo_file_id_2"])
    if d.get("photo_file_id_3"):
        photo_ids.append(d["photo_file_id_3"])
    return {
        "id": d["id"],
        "category": d["category"],
        "category_label": category_name(d["category"], lang),
        "description": d["description"],
        "status": d["status"],
        "status_label": status_label(d["status"], lang),
        "photo_url": f"/api/photo/{d['photo_file_id']}",
        "photo_urls": [f"/api/photo/{pid}" for pid in photo_ids],
        "created_at": d["created_at"].isoformat(),
        "like_count": like_count,
        "liked_by_me": liked_by_me,
        "share_count": d.get("share_count", 0),
        "is_mine": d["donor_id"] == viewer_id if viewer_id else False,
    }


async def api_me(request: web.Request) -> web.Response:
    telegram_id = await _require_user_id(request)
    user = await create_user_if_missing(telegram_id)
    return web.json_response({"language": user["language"], "role": user["role"]})


async def api_set_language(request: web.Request) -> web.Response:
    telegram_id = await _require_user_id(request)
    body = await request.json()
    lang = body.get("language")
    if lang not in LANGUAGES:
        raise web.HTTPBadRequest(text="invalid language")
    await create_user_if_missing(telegram_id)
    await set_user_language(telegram_id, lang)
    return web.json_response({"ok": True})


async def api_set_role(request: web.Request) -> web.Response:
    telegram_id = await _require_user_id(request)
    body = await request.json()
    role = body.get("role")
    if role not in ("donor", "needy"):
        raise web.HTTPBadRequest(text="invalid role")
    await create_user_if_missing(telegram_id)
    await set_user_role(telegram_id, role)
    return web.json_response({"ok": True})


async def api_stats(request: web.Request) -> web.Response:
    await _require_user_id(request)
    stats = await get_stats()
    by_category = await get_category_stats()
    new_last_24h = await count_new_donations_last_24h()
    return web.json_response(
        {
            "total_donations": stats["total_donations"],
            "delivered_donations": stats["completed_donations"],
            "new_last_24h": new_last_24h,
            "by_category": by_category,
        }
    )


async def api_categories(request: web.Request) -> web.Response:
    telegram_id = await _require_user_id(request)
    lang = await _lang_for(telegram_id)
    return web.json_response(
        [{"key": key, "label": category_name(key, lang)} for key in CATEGORIES]
    )


async def api_donations(request: web.Request) -> web.Response:
    telegram_id = await _require_user_id(request)
    category = request.query.get("category")
    if category not in CATEGORIES:
        raise web.HTTPBadRequest(text="invalid category")
    lang = await _lang_for(telegram_id)
    donations = await get_available_donations(category)
    likes = await get_like_info([d["id"] for d in donations], telegram_id)
    return web.json_response(
        [
            _donation_json(
                d, lang,
                like_count=likes.get(d["id"], {}).get("count", 0),
                liked_by_me=likes.get(d["id"], {}).get("liked", False),
                viewer_id=telegram_id,
            )
            for d in donations
        ]
    )


async def api_donation(request: web.Request) -> web.Response:
    telegram_id = await _require_user_id(request)
    donation_id = int(request.match_info["id"])
    donation = await get_donation(donation_id)
    if not donation:
        raise web.HTTPNotFound()
    lang = await _lang_for(telegram_id)
    likes = await get_like_info([donation_id], telegram_id)
    like = likes.get(donation_id, {})
    return web.json_response(
        _donation_json(donation, lang, like_count=like.get("count", 0), liked_by_me=like.get("liked", False))
    )


async def api_my_donations(request: web.Request) -> web.Response:
    telegram_id = await _require_user_id(request)
    lang = await _lang_for(telegram_id)
    donations = await get_donations_by_donor(telegram_id)
    likes = await get_like_info([d["id"] for d in donations], telegram_id)

    result = []
    for d in donations:
        like = likes.get(d["id"], {})
        item = _donation_json(d, lang, like_count=like.get("count", 0), liked_by_me=like.get("liked", False))
        if d["status"] in ("reserved", "shipped", "received"):
            res = await get_active_reservation_for_donation(d["id"])
            if res:
                item["reservation"] = {
                    "id": res["id"],
                    "full_name": res["full_name"],
                    "address": res["address"],
                    "phone": res["phone"],
                    "status": res["status"],
                    "dua_text": res["dua_text"],
                }
        result.append(item)
    return web.json_response(result)


async def api_my_requests(request: web.Request) -> web.Response:
    telegram_id = await _require_user_id(request)
    lang = await _lang_for(telegram_id)
    reservations = await get_reservations_by_needy(telegram_id)
    donations = [await get_donation(r["donation_id"]) for r in reservations]
    likes = await get_like_info([d["id"] for d in donations if d], telegram_id)

    result = []
    for r, donation in zip(reservations, donations):
        like = likes.get(donation["id"], {}) if donation else {}
        result.append(
            {
                "reservation_id": r["id"],
                "status": r["status"],
                "status_label": status_label(r["status"], lang),
                "donation": (
                    _donation_json(
                        donation, lang,
                        like_count=like.get("count", 0),
                        liked_by_me=like.get("liked", False),
                    )
                    if donation else None
                ),
                "receipt_note": r["receipt_note"],
                "receipt_photo_url": (
                    f"/api/photo/{r['receipt_photo_file_id']}" if r["receipt_photo_file_id"] else None
                ),
                "dua_text": r["dua_text"],
            }
        )
    return web.json_response(result)


async def api_create_reservation(request: web.Request) -> web.Response:
    telegram_id = await _require_user_id(request)
    body = await request.json()
    donation_id = body.get("donation_id")
    full_name = (body.get("full_name") or "").strip()
    address = (body.get("address") or "").strip()
    phone = (body.get("phone") or "").strip()
    if not (donation_id and full_name and address and phone):
        raise web.HTTPBadRequest(text="missing fields")

    donation = await get_donation(donation_id)
    if not donation or donation["status"] != "available":
        raise web.HTTPConflict(text="already reserved")
    # BETA: bitta test akkaunt bilan ham saxiy, ham muhtoj rolini sinash
    # uchun o'z ehsonini band qilish vaqtincha ochiq qoldirildi. Ilova
    # ishga tushirilganda quyidagi tekshiruv qaytarilishi kerak:
    #   if donation["donor_id"] == telegram_id:
    #       raise web.HTTPForbidden(text="own donation")

    reservation_id = await create_reservation(
        donation_id, telegram_id, full_name, address, phone
    )
    await set_donation_status(donation_id, "reserved")
    await _refresh_channel_post(
        request.app["bot"], request.app.get("bot_username"), donation_id, "reserved"
    )

    donor_lang = await _lang_for(donation["donor_id"])
    bot: Bot = request.app["bot"]
    message_id = await _send_tracked_message(
        bot,
        donation["donor_id"],
        None,
        t(
            donor_lang,
            "new_reservation_for_donor",
            category=escape(category_name(donation["category"], donor_lang), quote=False),
            description=escape(donation["description"] or "", quote=False),
            full_name=escape(full_name, quote=False),
            address=escape(address, quote=False),
            phone=escape(phone, quote=False),
        ),
        reply_markup=(
            InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text=t(donor_lang, "upload_receipt_button"),
                    web_app=WebAppInfo(url=f"{WEBAPP_URL}&screen=donor_cabinet"),
                )
            ]])
            if WEBAPP_URL else None
        ),
    )
    await set_donor_notify_message(reservation_id, message_id)
    return web.json_response({"ok": True, "reservation_id": reservation_id})


async def api_confirm_received(request: web.Request) -> web.Response:
    telegram_id = await _require_user_id(request)
    reservation_id = int(request.match_info["id"])
    body = await request.json()
    dua_text = (body.get("dua_text") or "").strip()
    if not dua_text:
        raise web.HTTPBadRequest(text="dua_text required")

    reservation = await get_reservation(reservation_id)
    if not reservation or reservation["needy_id"] != telegram_id:
        raise web.HTTPForbidden()
    if reservation["status"] != "shipped":
        raise web.HTTPConflict()

    bot: Bot = request.app["bot"]
    await set_reservation_received(reservation_id, dua_text)
    donation = await get_donation(reservation["donation_id"])
    await set_donation_status(donation["id"], "received")
    await _refresh_channel_post(
        bot, request.app.get("bot_username"), donation["id"], "received"
    )

    donor_lang = await _lang_for(donation["donor_id"])
    donor_message_id = await _send_tracked_message(
        bot,
        donation["donor_id"],
        reservation["donor_notify_message_id"],
        t(donor_lang, "received_notify_donor", dua_text=escape(dua_text, quote=False)),
        reply_markup=(
            InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text=t(donor_lang, "open_app_button"),
                    web_app=WebAppInfo(
                        url=f"{WEBAPP_URL}&screen=donor_cabinet&activeTab=received&r={reservation_id}"
                    ),
                )
            ]])
            if WEBAPP_URL else None
        ),
    )
    await set_donor_notify_message(reservation_id, donor_message_id)

    # Muhtojning o'zi qabulni tasdiqlayapti — unga yangi xabar kerak emas,
    # faqat "Yo'lda" bildirishnomasi endi eskirgani uchun o'chiriladi.
    if reservation["needy_notify_message_id"]:
        try:
            await bot.delete_message(
                chat_id=reservation["needy_id"],
                message_id=reservation["needy_notify_message_id"],
            )
        except TelegramAPIError:
            pass
        await set_needy_notify_message(reservation_id, None)
    return web.json_response({"ok": True})


async def api_ad_view(request: web.Request) -> web.Response:
    await _require_user_id(request)
    body = await request.json()
    slide = body.get("slide")
    if slide not in (1, 2, 3, 4, 5, 6, 7, 8):
        raise web.HTTPBadRequest(text="invalid slide")
    views = await increment_ad_views(slide)
    return web.json_response({"slide": slide, "views": views})


# --- "Reklama berish" reyting/taklif tizimi ----------------------------------
# ESLATMA: hozircha Click/Payme kabi haqiqiy to'lov integratsiyasi ulanmagan —
# taklif shu yerda "test rejimida" darhol tasdiqlangan deb qabul qilinadi.
# Haqiqiy to'lov ulanganda, upsert_ad_bid() chaqirilishidan oldin to'lov
# tasdiqlanishini kutish kerak bo'ladi.
AD_MIN_STARTING_BID = 200_000
AD_MIN_INCREMENT = 100_000

_AD_PLATFORM_HOSTS = {
    "t.me": "telegram", "telegram.me": "telegram", "telegram.dog": "telegram",
    "instagram.com": "instagram", "www.instagram.com": "instagram",
    "youtube.com": "youtube", "www.youtube.com": "youtube", "youtu.be": "youtube",
    "apps.apple.com": "appstore",
    "play.google.com": "googleplay",
}

_AD_CATEGORY_KEYS = {"tech", "trade", "people", "education", "marketing", "lifestyle", "other"}


async def _resolve_is_public_host(hostname: str) -> bool:
    """SSRF himoyasi — link ichki/lokal manzilga (localhost, 169.254.x.x va h.k.)
    ishora qilmasligini tekshiradi, faqat ochiq internet manzillariga so'rov
    yuborilishiga ruxsat beradi."""
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(hostname, None)
    except OSError:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return False
    return True


def _derive_ad_platform(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return _AD_PLATFORM_HOSTS.get(host, "website")


def _sanitize_ad_photo_url(photo_url: Any) -> Optional[str]:
    if not isinstance(photo_url, str):
        return None
    photo_url = photo_url.strip()
    if photo_url.startswith("/api/photo/") or photo_url.startswith("http://") or photo_url.startswith("https://"):
        return photo_url[:500]
    return None


def _sanitize_ad_description(description: Any) -> Optional[str]:
    if not isinstance(description, str):
        return None
    description = description.strip()
    return description[:200] or None


def _extract_meta(html_text: str, *props: str) -> str:
    for prop in props:
        escaped = re.escape(prop)
        m = re.search(
            r'<meta[^>]+(?:property|name)=["\']' + escaped + r'["\'][^>]+content=["\']([^"\']*)["\']',
            html_text, re.I,
        )
        if not m:
            m = re.search(
                r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']' + escaped + r'["\']',
                html_text, re.I,
            )
        if m:
            return unescape(m.group(1)).strip()
    return ""


class _AdPreviewError(Exception):
    def __init__(self, status: int, reason: str):
        super().__init__(reason)
        self.status = status
        self.reason = reason


async def _fetch_ad_preview(bot: Bot, url: str) -> dict:
    """URL bo'yicha brend nomi/tavsifi/rasmini aniqlaydi (sindr.uz'dagi kabi).
    Telegram havolalari uchun bot.get_chat() orqali, boshqa saytlar uchun
    Open Graph meta teglarini o'qib."""
    if not re.match(r"^https?://", url):
        url = "https://" + url

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        raise _AdPreviewError(400, "invalid url")

    platform = _derive_ad_platform(url)

    if platform == "telegram":
        username = parsed.path.strip("/").split("/")[0]
        if not username or username.startswith("+") or username.lower() == "joinchat":
            raise _AdPreviewError(400, "invalid telegram link")
        try:
            chat = await bot.get_chat("@" + username)
        except TelegramAPIError:
            raise _AdPreviewError(404, "chat_not_found")
        title = chat.title or " ".join(filter(None, [chat.first_name, chat.last_name])) or username
        description = chat.description or chat.bio or ""
        photo_url = f"/api/photo/{chat.photo.small_file_id}" if chat.photo else None
        return {"platform": "telegram", "title": title, "description": description, "photo_url": photo_url}

    if not await _resolve_is_public_host(host):
        raise _AdPreviewError(400, "host_not_allowed")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=6),
                headers={"User-Agent": "Mozilla/5.0 (compatible; EhsonAppBot/1.0)"},
            ) as resp:
                html_text = await resp.text(errors="ignore")
    except Exception:
        return {"platform": platform, "title": "", "description": "", "photo_url": None}

    title = _extract_meta(html_text, "og:title", "twitter:title")
    if not title:
        m = re.search(r"<title[^>]*>([^<]*)</title>", html_text, re.I)
        title = unescape(m.group(1)).strip() if m else ""
    description = _extract_meta(html_text, "og:description", "twitter:description", "description")
    image = _extract_meta(html_text, "og:image", "twitter:image")

    return {
        "platform": platform,
        "title": title[:120],
        "description": description[:200],
        "photo_url": image or None,
    }


async def api_ads_preview(request: web.Request) -> web.Response:
    await _require_user_id(request)
    url = (request.query.get("url") or "").strip()
    if not url:
        raise web.HTTPBadRequest(text="missing url")
    try:
        preview = await _fetch_ad_preview(request.app["bot"], url)
    except _AdPreviewError as e:
        if e.status == 404:
            raise web.HTTPNotFound(text=e.reason)
        raise web.HTTPBadRequest(text=e.reason)
    return web.json_response(preview)


_background_tasks: set[asyncio.Task] = set()


async def _backfill_ad_descriptions(bot: Bot, bid_ids: list[int]) -> None:
    """Tavsif ustuni qo'shilishidan oldin joylangan takliflar uchun preview
    orqa fonda bir marta so'raladi — keyingi ochilishda tavsif ko'rinadi."""
    for bid in await claim_ad_bids_for_description(bid_ids):
        try:
            preview = await _fetch_ad_preview(bot, bid["url"])
        except Exception:
            continue
        description = _sanitize_ad_description(preview.get("description"))
        photo_url = None if bid["photo_url"] else _sanitize_ad_photo_url(preview.get("photo_url"))
        if description or photo_url:
            await fill_ad_bid_preview(bid["id"], description, photo_url)


async def api_ads_leaderboard(request: web.Request) -> web.Response:
    telegram_id = await _require_user_id(request)
    bids = await get_ad_bids_ranked()
    top_amount = bids[0]["bid_amount"] if bids else 0

    missing = [b["id"] for b in bids if b["description"] is None and not b["description_checked"]]
    if missing:
        task = asyncio.create_task(_backfill_ad_descriptions(request.app["bot"], missing))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    result = [
        {
            "id": b["id"],
            "rank": i + 1,
            "brand_name": b["brand_name"],
            "url": b["url"],
            "bid_amount": b["bid_amount"],
            "platform": b["platform"],
            "photo_url": b["photo_url"],
            "category": b["category"],
            "description": b["description"],
            "clicks": b["clicks"],
            "is_me": b["telegram_id"] == telegram_id,
        }
        for i, b in enumerate(bids)
    ]
    return web.json_response({
        "bids": result,
        "min_starting_bid": AD_MIN_STARTING_BID,
        "min_increment": AD_MIN_INCREMENT,
        "next_top_bid": top_amount + AD_MIN_INCREMENT if bids else AD_MIN_STARTING_BID,
    })


async def api_ads_bid(request: web.Request) -> web.Response:
    telegram_id = await _require_user_id(request)
    body = await request.json()
    brand_name = (body.get("brand_name") or "").strip()
    url = (body.get("url") or "").strip()
    bid_amount = body.get("bid_amount")

    if not brand_name or not url:
        raise web.HTTPBadRequest(text="missing fields")
    if not re.match(r"^https?://", url):
        url = "https://" + url
    if not isinstance(bid_amount, (int, float)) or bid_amount <= 0:
        raise web.HTTPBadRequest(text="invalid bid_amount")
    bid_amount = int(bid_amount)

    if bid_amount < AD_MIN_STARTING_BID:
        raise web.HTTPConflict(text="bid_too_low")

    # Platforma URL manzilidan serverda aniqlanadi (klientga ishonilmaydi),
    # rasm URL'i esa /api/ads/preview orqali oldindan olingan bo'lsa shundan
    # olinadi — top 10 reytingda ham preview kartadagi kabi rasm chiqishi uchun.
    platform = _derive_ad_platform(url)
    photo_url = _sanitize_ad_photo_url(body.get("photo_url"))
    category = body.get("category")
    category = category if category in _AD_CATEGORY_KEYS else None
    description = _sanitize_ad_description(body.get("description"))
    await insert_ad_bid(telegram_id, brand_name[:80], url, bid_amount, platform, photo_url, category, description)
    return web.json_response({"ok": True})


async def api_ads_click(request: web.Request) -> web.Response:
    await _require_user_id(request)
    clicks = await increment_ad_bid_clicks(int(request.match_info["id"]))
    if clicks is None:
        raise web.HTTPNotFound()
    return web.json_response({"clicks": clicks})


async def api_badges(request: web.Request) -> web.Response:
    telegram_id = await _require_user_id(request)
    donor_pending = await count_pending_ship(telegram_id)
    needy_pending = await count_pending_receive(telegram_id)
    return web.json_response({"donor_pending": donor_pending, "needy_pending": needy_pending})


async def api_cancel_reservation(request: web.Request) -> web.Response:
    telegram_id = await _require_user_id(request)
    reservation_id = int(request.match_info["id"])

    reservation = await get_reservation(reservation_id)
    if not reservation or reservation["needy_id"] != telegram_id:
        raise web.HTTPForbidden()
    if reservation["status"] != "reserved":
        raise web.HTTPConflict()

    bot: Bot = request.app["bot"]
    donation = await get_donation(reservation["donation_id"])
    await cancel_reservation(reservation_id)
    await set_donation_status(reservation["donation_id"], "available")
    await _refresh_channel_post(
        bot, request.app.get("bot_username"), reservation["donation_id"], "available"
    )

    if donation:
        donor_lang = await _lang_for(donation["donor_id"])
        # Bekor qilingan bronning yozuvi o'chirilgani uchun (cancel_reservation)
        # yangi xabar id'ini saqlashning hojati yo'q — bu bronning tsikli
        # shu yerda tugaydi.
        await _send_tracked_message(
            bot,
            donation["donor_id"],
            reservation["donor_notify_message_id"],
            t(
                donor_lang,
                "reservation_cancelled_notify_donor",
                description=escape(donation["description"] or "", quote=False),
            ),
        )
    return web.json_response({"ok": True})


async def api_delete_donation(request: web.Request) -> web.Response:
    telegram_id = await _require_user_id(request)
    donation_id = int(request.match_info["id"])

    donation = await get_donation(donation_id)
    if not donation or donation["donor_id"] != telegram_id:
        raise web.HTTPForbidden()
    if donation["status"] != "available":
        raise web.HTTPConflict()

    await _remove_channel_post(request.app["bot"], donation)
    await delete_donation(donation_id)
    return web.json_response({"ok": True})


async def api_toggle_donation_like(request: web.Request) -> web.Response:
    telegram_id = await _require_user_id(request)
    donation_id = int(request.match_info["id"])

    donation = await get_donation(donation_id)
    if not donation:
        raise web.HTTPNotFound()

    liked, count = await toggle_donation_like(donation_id, telegram_id)
    return web.json_response({"liked": liked, "like_count": count})


async def api_share_donation(request: web.Request) -> web.Response:
    await _require_user_id(request)
    donation_id = int(request.match_info["id"])

    donation = await get_donation(donation_id)
    if not donation:
        raise web.HTTPNotFound()

    count = await increment_donation_share(donation_id)
    return web.json_response({"share_count": count})


async def api_create_donation(request: web.Request) -> web.Response:
    telegram_id = await _require_user_id(request)
    fields, photos = await _read_multipart_photos(request)
    category = fields.get("category")
    description = (fields.get("description") or "").strip()
    if category not in CATEGORIES or not description:
        raise web.HTTPBadRequest(text="missing fields")

    await create_user_if_missing(telegram_id)
    bot: Bot = request.app["bot"]

    # Rasmlar Telegram serverida file_id sifatida saqlanadi, uni olishning
    # yagona yo'li — suratni yuborish. Foydalanuvchi bu xabarni bot
    # sahifasida ko'rmasligi uchun file_id olingach darhol o'chiramiz
    # (o'chirilgan xabarning file_id'si amal qilishda davom etadi).
    if len(photos) == 1:
        photo_bytes, filename = photos[0]
        sent = await bot.send_photo(
            chat_id=telegram_id,
            photo=BufferedInputFile(photo_bytes, filename=filename),
            disable_notification=True,
        )
        photo_file_ids = [sent.photo[-1].file_id]
        sent_messages = [sent]
    else:
        media = [
            InputMediaPhoto(media=BufferedInputFile(photo_bytes, filename=filename))
            for photo_bytes, filename in photos
        ]
        sent_messages = await bot.send_media_group(
            chat_id=telegram_id, media=media, disable_notification=True
        )
        photo_file_ids = [msg.photo[-1].file_id for msg in sent_messages]

    for msg in sent_messages:
        try:
            await bot.delete_message(chat_id=telegram_id, message_id=msg.message_id)
        except TelegramAPIError:
            pass

    donation_id = await create_donation(
        donor_id=telegram_id,
        category=category,
        photo_file_ids=photo_file_ids,
        description=description,
    )
    asyncio.create_task(
        _publish_to_channel(bot, request.app.get("bot_username"), donation_id)
    )
    return web.json_response({"ok": True, "donation_id": donation_id})


async def api_ship_reservation(request: web.Request) -> web.Response:
    telegram_id = await _require_user_id(request)
    reservation_id = int(request.match_info["id"])
    fields, photo_bytes, filename = await _read_multipart_photo(request)
    receipt_note = (fields.get("receipt_note") or "").strip() or None

    reservation = await get_reservation(reservation_id)
    if not reservation or reservation["status"] != "reserved":
        raise web.HTTPConflict()

    donation = await get_donation(reservation["donation_id"])
    if not donation or donation["donor_id"] != telegram_id:
        raise web.HTTPForbidden()

    lang = await _lang_for(telegram_id)
    bot: Bot = request.app["bot"]

    # file_id olishning yagona yo'li — suratni yuborish. Bot chatini
    # katta rasm bilan band qilmaslik uchun xabar darhol o'chiriladi
    # (o'chirilgan xabarning file_id'si amal qilishda davom etadi),
    # o'rniga qisqa matnli xabar + "Chekni ko'rish" tugmasi yuboriladi.
    sent = await bot.send_photo(
        chat_id=telegram_id,
        photo=BufferedInputFile(photo_bytes, filename=filename),
        disable_notification=True,
    )
    photo_file_id = sent.photo[-1].file_id
    try:
        await bot.delete_message(chat_id=telegram_id, message_id=sent.message_id)
    except TelegramAPIError:
        pass

    await set_reservation_shipped(reservation_id, photo_file_id, receipt_note)
    await set_donation_status(donation["id"], "shipped")
    await _refresh_channel_post(
        bot, request.app.get("bot_username"), donation["id"], "shipped"
    )

    donor_message_id = await _send_tracked_message(
        bot,
        telegram_id,
        reservation["donor_notify_message_id"],
        t(lang, "shipped_saved_donor"),
        reply_markup=_receipt_keyboard(
            lang, reservation_id, "donor_cabinet", button_text_key="view_donation_button"
        ),
    )
    await set_donor_notify_message(reservation_id, donor_message_id)

    needy_lang = await _lang_for(reservation["needy_id"])
    needy_message_id = await _send_tracked_message(
        bot,
        reservation["needy_id"],
        reservation["needy_notify_message_id"],
        t(needy_lang, "shipped_notify_needy"),
        reply_markup=_receipt_keyboard(needy_lang, reservation_id, "needy_cabinet", "receipt"),
    )
    await set_needy_notify_message(reservation_id, needy_message_id)
    return web.json_response({"ok": True})


async def api_photo(request: web.Request) -> web.Response:
    file_id = request.match_info["file_id"]
    bot: Bot = request.app["bot"]
    try:
        file = await bot.get_file(file_id)
        buf = await bot.download_file(file.file_path)
    except Exception:
        raise web.HTTPNotFound()
    return web.Response(body=buf.read(), content_type="image/jpeg")


_UZ_MONTHS = [
    "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentyabr", "Oktyabr", "Noyabr", "Dekabr",
]


def _format_date_uz(dt) -> str:
    return f"{dt.day}-{_UZ_MONTHS[dt.month - 1]}, {dt.year}"


_HEART_ICON_PATH = (
    "M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78"
    "l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"
)
_SHARE_ICON_PATH = (
    "M20.1 7.5 L16.5 17.8 Q15 22 13.2 17.9 L11 13 L6.1 10.8 Q2 9 6.2 7.5 "
    "L16.5 3.9 Q22 2 20.1 7.5 Z"
)
# Ilovadagi "Qabul qilingan" holatida ishlatiladigan xuddi shu ko'k
# rozetka — /d/{id} ulashish sahifasi ham ilovaning o'zi kabi haqiqiy
# HTML/CSS bo'lgani uchun (Telegram xabar matnidan farqli o'laroq) bu
# yerda aynan bir xil SVG va animatsiyani ishlatish mumkin.
_VERIFIED_BADGE_SVG = (
    '<svg viewBox="0 0 24 24" width="16" height="16" fill="#4EA4F5">'
    '<path fill-rule="evenodd" clip-rule="evenodd" d="M8.603 3.799A4.49 4.49 0 0112 2.25c1.357 0 2.573.6 '
    '3.397 1.549a4.49 4.49 0 013.498 1.307 4.491 4.491 0 011.307 3.497A4.49 4.49 0 0121.75 12a4.49 4.49 0 '
    '01-1.549 3.397 4.491 4.491 0 01-1.307 3.497 4.491 4.491 0 01-3.497 1.307A4.49 4.49 0 0112 21.75a4.49 '
    '4.49 0 01-3.397-1.549 4.49 4.49 0 01-3.498-1.306 4.491 4.491 0 01-1.307-3.498A4.49 4.49 0 012.25 12c0'
    '-1.357.6-2.573 1.549-3.397a4.49 4.49 0 011.307-3.497 4.49 4.49 0 013.497-1.307zm7.007 6.387a.75.75 0 '
    '10-1.22-.872l-3.236 4.53L9.53 12.22a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.14-.094l3.75-5.25z">'
    "</path></svg>"
)


def _status_emoji_html(status: str, emoji: str) -> str:
    """statusEmojiHtml() (webapp/index.html) bilan bir xil — /d/{id}
    ulashish sahifasidagi holat belgisi ilovadagidan farq qilmasligi
    uchun."""
    if status == "available":
        return '<span class="hourglass-swap"><span class="a">⏳</span><span class="b">⌛</span></span>'
    if status == "shipped":
        return f'<span class="truck-road">{escape(emoji)}<span class="road-track"></span></span>'
    if status == "received":
        return f'<span class="check-pop">{_VERIFIED_BADGE_SVG}</span>'
    if status == "reserved":
        return f'<span class="handshake-shake">{escape(emoji)}</span>'
    return escape(emoji)


async def donation_share_page(request: web.Request) -> web.Response:
    """Ehsonni Telegram'da 'post' ko'rinishida (rasm + sarlavha bilan)
    ulashish uchun statik sahifa — Telegram link preview shu OG teglarni
    o'qib, rasmli karta ko'rsatadi. Sahifaning o'zi ham ilovadagi ehson
    kartochkasining aynan o'zini (galereya, like/ulashish, tavsif) takrorlaydi,
    pastida esa botni ochish havolasi turadi."""
    donation_id = int(request.match_info["id"])
    donation = await get_donation(donation_id)
    if not donation:
        raise web.HTTPNotFound()

    lang = "uz"
    category_label = category_name(donation["category"], lang)
    cat_emoji, _, cat_name = category_label.partition(" ")
    status_full = status_label(donation["status"], lang)
    status_emoji, _, status_text = status_full.partition(" ")
    description = donation["description"] or ""

    photo_ids = [donation["photo_file_id"]]
    if donation.get("photo_file_id_2"):
        photo_ids.append(donation["photo_file_id_2"])
    if donation.get("photo_file_id_3"):
        photo_ids.append(donation["photo_file_id_3"])
    photo_urls = [f"{BASE_URL}/api/photo/{pid}" for pid in photo_ids]

    likes = await get_like_info([donation_id], 0)
    like_count = likes.get(donation_id, {}).get("count", 0)
    share_count = donation.get("share_count", 0)

    image_url = photo_urls[0]
    page_url = f"{BASE_URL}/d/{donation_id}"
    bot_username = request.app.get("bot_username")
    bot_url = (
        f"https://t.me/{bot_username}/{MINI_APP_SHORT_NAME}?startapp=d_{donation_id}"
        if bot_username else BASE_URL
    )

    if len(photo_urls) > 1:
        dots_html = '<div class="card-gallery-dots">' + "".join(
            f'<span class="card-gallery-dot{" active" if i == 0 else ""}"></span>'
            for i in range(len(photo_urls))
        ) + "</div>"
        counter_html = f'<div class="card-gallery-counter">1/{len(photo_urls)}</div>'
        gallery_html = (
            '<div class="card-media">'
            '<div class="card-gallery">'
            + "".join(f'<img src="{escape(url)}" alt="">' for url in photo_urls)
            + "</div>" + counter_html + "</div>" + dots_html
        )
    else:
        gallery_html = f'<img src="{escape(image_url)}" alt="">'

    like_count_html = (
        f'<span class="like-count">{like_count}</span>' if like_count else ""
    )
    share_count_html = (
        f'<span class="share-count">{share_count}</span>' if share_count else ""
    )

    html = f"""<!doctype html>
<html lang="uz">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta property="og:type" content="article">
<meta property="og:title" content="{escape(cat_name)}">
<meta property="og:description" content="{escape(description)}">
<meta property="og:image" content="{escape(image_url)}">
<meta property="og:url" content="{escape(page_url)}">
<meta name="twitter:card" content="summary_large_image">
<title>{escape(cat_name)}</title>
<style>
  :root {{ --text: #1C1C1E; --hint: #8E96A3; --section-bg: #FFFFFF; --border: rgba(0,0,0,0.08); --blue: #1C93F3; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; background:#F2F3F5; margin:0; padding:20px; color:var(--text); }}
  .wrap {{ max-width: 380px; margin: 0 auto; }}
  .card {{ background: var(--section-bg); border: 1px solid var(--border); border-radius: 16px; overflow: hidden; }}
  .card img {{ width: 100%; aspect-ratio: 1 / 1; object-fit: cover; display: block; background: #232B36; }}
  .card-media {{ position: relative; }}
  .card-gallery {{ display: flex; overflow-x: auto; scroll-snap-type: x mandatory; scrollbar-width: none; }}
  .card-gallery::-webkit-scrollbar {{ display: none; }}
  .card-gallery img {{ flex: 0 0 100%; scroll-snap-align: start; }}
  .card-gallery-dots {{ display: flex; gap: 6px; justify-content: center; padding: 10px 0 0; }}
  .card-gallery-dot {{ width: 6px; height: 6px; border-radius: 3px; background: rgba(28,147,243,0.25); transition: all .3s ease; }}
  .card-gallery-dot.active {{ width: 18px; background: var(--blue); }}
  .card-gallery-counter {{ position: absolute; top: 10px; right: 10px; z-index: 2; background: rgba(0,0,0,0.55); color: #fff; font-size: 12px; font-weight: 600; padding: 2px 9px; border-radius: 10px; }}
  .card-header {{ display: flex; align-items: center; gap: 8px; padding: 10px 12px; }}
  .card-header-avatar {{ width: 32px; height: 32px; border-radius: 50%; background: rgba(120,140,160,0.15); display: flex; align-items: center; justify-content: center; font-size: 16px; flex-shrink: 0; }}
  .card-header-name {{ font-weight: 700; font-size: 13.5px; color: var(--text); }}
  .card-actions {{ display: flex; align-items: center; gap: 16px; padding: 10px 12px 0; }}
  .action-btn {{ display: flex; align-items: center; gap: 6px; color: var(--text); font-size: 14px; font-weight: 700; }}
  .action-btn svg {{ width: 28px; height: 28px; }}
  .like-btn svg {{ width: 22px; height: 22px; }}
  .card-body {{ padding: 12px 14px; }}
  .card-desc {{ font-size: 13.5px; font-weight: 700; line-height: 1.4; margin-bottom: 8px; }}
  .pill {{ display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 12px; background: rgba(0,0,0,0.06); margin-bottom: 8px; }}
  .pill-available {{ color: #9AA7B3; }}
  .pill-reserved {{ color: #FFB454; }}
  .pill-shipped {{ color: #4EA4F5; }}
  .pill-received {{ color: #4EA4F5; }}
  .hourglass-swap {{ position: relative; display: inline-block; width: 1em; height: 1em; vertical-align: -0.15em; }}
  .hourglass-swap span {{ position: absolute; left: 0; top: 0; }}
  .hourglass-swap .a {{ animation: hourglassA 3.2s infinite; }}
  .hourglass-swap .b {{ animation: hourglassB 3.2s infinite; }}
  @keyframes hourglassA {{ 0%, 45% {{ opacity: 1; }} 50%, 95% {{ opacity: 0; }} 100% {{ opacity: 1; }} }}
  @keyframes hourglassB {{ 0%, 45% {{ opacity: 0; }} 50%, 95% {{ opacity: 1; }} 100% {{ opacity: 0; }} }}
  .truck-road {{ position: relative; display: inline-block; vertical-align: -0.15em; padding-bottom: 1px; }}
  .truck-road .road-track {{
    position: absolute; left: 0; right: 0; bottom: 0; height: 2px; border-radius: 1px; overflow: hidden;
    background-image: repeating-linear-gradient(90deg, currentColor 0 3px, transparent 3px 6px);
    background-size: 12px 2px; animation: roadScroll 0.6s linear infinite; opacity: 0.55;
  }}
  @keyframes roadScroll {{ from {{ background-position: -12px 0; }} to {{ background-position: 0 0; }} }}
  .check-pop {{ display: inline-block; vertical-align: -0.28em; animation: checkOpen 4s ease-in-out infinite; }}
  @keyframes checkOpen {{ 0% {{ transform: scale(0); opacity: 0; }} 25% {{ transform: scale(1); opacity: 1; }} 100% {{ transform: scale(1); opacity: 1; }} }}
  .handshake-shake {{ display: inline-block; transform-origin: 70% 70%; animation: handshakeShake 3s ease-in-out infinite; }}
  @keyframes handshakeShake {{
    0%, 60%, 100% {{ transform: rotate(0deg); }}
    65% {{ transform: rotate(-12deg); }}
    75% {{ transform: rotate(10deg); }}
    85% {{ transform: rotate(-6deg); }}
    92% {{ transform: rotate(0deg); }}
  }}
  .card-date {{ font-size: 11px; color: var(--hint); letter-spacing: 0.3px; margin-top: 2px; }}
  a.btn {{ display:block; text-align:center; margin-top: 16px; background:#2AABEE; color:#fff; text-decoration:none; padding: 13px 28px; border-radius: 24px; font-weight:600; }}
</style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <div class="card-header">
        <span class="card-header-avatar">{escape(cat_emoji)}</span>
        <span class="card-header-name">{escape(cat_name)}</span>
      </div>
      {gallery_html}
      <div class="card-actions">
        <span class="action-btn like-btn">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="{_HEART_ICON_PATH}"></path></svg>
          {like_count_html}
        </span>
        <span class="action-btn share-btn">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="14" y1="9" x2="11" y2="13"></line><path d="{_SHARE_ICON_PATH}"></path></svg>
          {share_count_html}
        </span>
      </div>
      <div class="card-body">
        <div class="card-desc">{escape(description)}</div>
        <span class="pill pill-{donation["status"]}">{_status_emoji_html(donation["status"], status_emoji)} {escape(status_text)}</span>
        <div class="card-date">{escape(_format_date_uz(donation["created_at"]))}</div>
      </div>
    </div>
    <a class="btn" href="{escape(bot_url)}">Botni ochish</a>
  </div>
  <script>
    // Telegram'ning link-preview "crawler"i JS ishlatmaydi, shuning uchun
    // karta (rasm/sarlavha/tavsif) chatda odatdagidek to'g'ri ko'rsatiladi.
    // Haqiqiy foydalanuvchi shu havolani bossa esa, sahifa darhol Mini
    // App'ning o'ziga (aynan shu ehsonga) qayta yo'naltiradi.
    try {{ window.location.replace({json.dumps(bot_url)}); }} catch (e) {{}}

    document.querySelectorAll(".card-gallery").forEach(function (gallery) {{
      var card = gallery.closest(".card");
      var dots = card ? card.querySelectorAll(".card-gallery-dots .card-gallery-dot") : [];
      var counter = gallery.parentNode.querySelector(".card-gallery-counter");
      if (!dots.length) return;
      gallery.addEventListener("scroll", function () {{
        var index = Math.round(gallery.scrollLeft / gallery.clientWidth);
        dots.forEach(function (dot, i) {{ dot.classList.toggle("active", i === index); }});
        if (counter) counter.textContent = (index + 1) + "/" + dots.length;
      }}, {{ passive: true }});
    }});
  </script>
</body>
</html>"""
    return web.Response(text=html, content_type="text/html")


def setup_api_routes(app: web.Application) -> None:
    app.router.add_get("/api/me", api_me)
    app.router.add_post("/api/language", api_set_language)
    app.router.add_post("/api/role", api_set_role)
    app.router.add_get("/api/stats", api_stats)
    app.router.add_get("/api/badges", api_badges)
    app.router.add_post("/api/ad-view", api_ad_view)
    app.router.add_get("/api/ads/preview", api_ads_preview)
    app.router.add_get("/api/ads/leaderboard", api_ads_leaderboard)
    app.router.add_post("/api/ads/bid", api_ads_bid)
    app.router.add_post("/api/ads/{id:\\d+}/click", api_ads_click)
    app.router.add_get("/api/categories", api_categories)
    app.router.add_get("/api/donations", api_donations)
    app.router.add_get("/api/donation/{id}", api_donation)
    app.router.add_get("/api/my-donations", api_my_donations)
    app.router.add_get("/api/my-requests", api_my_requests)
    app.router.add_post("/api/reservations", api_create_reservation)
    app.router.add_post("/api/reservations/{id}/receive", api_confirm_received)
    app.router.add_post("/api/reservations/{id}/ship", api_ship_reservation)
    app.router.add_post("/api/reservations/{id}/cancel", api_cancel_reservation)
    app.router.add_post("/api/donations", api_create_donation)
    app.router.add_post("/api/donations/{id}/delete", api_delete_donation)
    app.router.add_post("/api/donations/{id}/like", api_toggle_donation_like)
    app.router.add_post("/api/donations/{id}/share", api_share_donation)
    app.router.add_get("/api/photo/{file_id}", api_photo)
    app.router.add_get("/d/{id}", donation_share_page)
