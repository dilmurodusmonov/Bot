import asyncio
import base64
import binascii
import contextvars
import ipaddress
import json
import logging
import re
import time
import uuid
from html import escape, unescape
from typing import Any, Optional
from urllib.parse import quote, urljoin, urlparse

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

from bot.ad_payments import admin_caption, send_receipt_to_admins
from bot.collage import build_collage
from bot.config import (
    AD_ADMIN_IDS,
    AD_CARD_HOLDER,
    AD_CARD_NUMBER,
    BASE_URL,
    CHANNEL_ID,
    MINI_APP_SHORT_NAME,
    WEBAPP_URL,
)
from bot.database import (
    get_ad_logo_cache,
    put_ad_logo_cache,
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
    get_ad_bid,
    create_ad_payment_new,
    create_ad_payment_raise,
    delete_ad_payment,
    get_pending_ad_payments,
    get_recent_rejected_ad_payments,
    dismiss_ad_payment_rejection,
    set_ad_payment_receipt,
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
    "instagram.com": "instagram", "www.instagram.com": "instagram", "m.instagram.com": "instagram",
    "instagr.am": "instagram",
    "youtube.com": "youtube", "www.youtube.com": "youtube", "m.youtube.com": "youtube", "youtu.be": "youtube",
    "apps.apple.com": "appstore",
    "play.google.com": "googleplay",
}

_AD_CATEGORY_KEYS = {"tech", "fintech", "ai", "trade", "people", "education", "marketing", "lifestyle", "other"}


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


_META_TAG_RE = re.compile(r"""<meta\b(?:[^>"']|"[^"]*"|'[^']*')*>""", re.I)
_ATTR_RE = re.compile(r"""([\w:.-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""")


def _extract_meta(html_text: str, *props: str) -> str:
    """<meta property|name="..." content="..."> qiymati. Qo'shtirnoq ichidagi
    apostrof ("Zo'r", "o'yna") matnni kesmasligi uchun atributlar to'liq
    tahlil qilinadi."""
    found: dict[str, str] = {}
    for tag in _META_TAG_RE.findall(html_text):
        attrs = {
            m.group(1).lower(): m.group(2) if m.group(2) is not None else (m.group(3) if m.group(3) is not None else m.group(4))
            for m in _ATTR_RE.finditer(tag)
        }
        key = (attrs.get("property") or attrs.get("name") or attrs.get("itemprop") or "").lower()
        if key and "content" in attrs and key not in found:
            found[key] = attrs["content"]
    for prop in props:
        value = found.get(prop.lower())
        if value:
            return unescape(value).strip()
    return ""


def _absolute_image_url(base_url: str, src: str) -> Optional[str]:
    """Nisbiy ("/img/logo.png", "//cdn...") manzilni to'liq https manzilga
    aylantiradi — Telegram WebView http rasmlarni ko'rsatmaydi."""
    src = (src or "").strip()
    if not src or src.startswith("data:"):
        return None
    full = urljoin(base_url, src)
    if full.startswith("http://"):
        full = "https://" + full[len("http://"):]
    return full if full.startswith("https://") else None


# Next.js loyihasi yaratilganda keladigan standart favicon (Vercel uchburchagi) —
# sayt egasi almashtirmagan bo'lsa bu brend logotipi emas.
_DEFAULT_FAVICON_RE = re.compile(r"favicon\.0b3bf435\.ico|/_next/static/media/favicon\.[0-9a-f]+\.ico", re.I)


def _is_default_favicon(url: Optional[str]) -> bool:
    return bool(url and _DEFAULT_FAVICON_RE.search(url))


def _site_icon_candidates(html_text: str, base_url: str) -> list[tuple[int, str]]:
    """Sahifadagi barcha <link rel=...icon...> ikonkalar, eng yaxshisi birinchi:
    apple-touch-icon > SVG > o'lchami bo'yicha. (ball, to'liq_url) ro'yxati."""
    found: list[tuple[int, str]] = []
    for tag in re.findall(r"<link\b[^>]*>", html_text, re.I):
        rel_m = re.search(r'rel=["\']([^"\']*)["\']', tag, re.I)
        href_m = re.search(r'href=["\']([^"\']*)["\']', tag, re.I)
        if not rel_m or not href_m:
            continue
        rel = rel_m.group(1).lower()
        if "icon" not in rel or "mask-icon" in rel:
            continue
        sizes = [int(n) for n in re.findall(r"(\d+)x\d+", tag)]
        size = max(sizes) if sizes else 0
        if "apple-touch-icon" in rel:
            score = 1000 + (size or 180)
        elif href_m.group(1).lower().split("?")[0].endswith(".svg"):
            score = 500
        else:
            score = size
        href = unescape(href_m.group(1)).strip()
        if _is_default_favicon(href):
            continue
        # Ba'zi saytlar ikonkani sahifaning o'ziga (data:image/...) joylaydi.
        full = href if href.startswith("data:image/") else _absolute_image_url(base_url, href)
        if full:
            found.append((score, full))
    found.sort(key=lambda item: -item[0])
    return found


def _extract_site_icon(html_text: str, base_url: str) -> Optional[str]:
    """Saytning logotip ikonkasi: apple-touch-icon yoki kamida 96px (yoki
    SVG) icon. Kichik favicon'lar olinmaydi."""
    for score, url in _site_icon_candidates(html_text, base_url):
        if score >= 96:
            return url
    return None


_BROWSER_HEADERS = {
    # Oddiy brauzer kabi — ko'p saytlar bot User-Agent'ini to'sadi.
    "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36",
    "Accept-Language": "uz,ru;q=0.9,en;q=0.8",
}


# Platformaga xos sarlavhalar: Instagram oddiy so'rovga login sahifasini
# qaytaradi, Facebook'ning havola-preview botiga esa profil og:image'ini
# beradi; YouTube Yevropa serverlariga cookie-rozilik sahifasini ko'rsatadi.
_PLATFORM_HEADERS = {
    "instagram": {"User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"},
    "youtube": {"Cookie": "SOCS=CAI; CONSENT=YES+1"},
}


# /preview tashxisi uchun: har bir sahifa so'rovi natijasi shu ro'yxatga yoziladi.
_FETCH_TRACE: contextvars.ContextVar[Optional[list]] = contextvars.ContextVar("fetch_trace", default=None)


async def _fetch_site_html(
    url: str, platform: str = "website", user_agent: Optional[str] = None,
) -> Optional[tuple[str, str]]:
    """Sahifa HTML'i va yakuniy (redirectdan keyingi) manzili. Xato holati
    (4xx/5xx) — masalan anti-bot'ning "400"/"403" sahifasi — None."""
    headers = {**_BROWSER_HEADERS, "Accept": "text/html,application/xhtml+xml"}
    headers.update(_PLATFORM_HEADERS.get(platform, {}))
    if user_agent:
        headers["User-Agent"] = user_agent
    trace = _FETCH_TRACE.get()
    agent = (user_agent or "brauzer").split(" ")[0].split("/")[0]
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=6), max_redirects=5, headers=headers,
            ) as resp:
                html_text, final_url = await resp.text(errors="ignore"), str(resp.url)
                if trace is not None:
                    trace.append(
                        f"{agent}: HTTP {resp.status} → {final_url[:60]} · "
                        f"title={_html_title(html_text)[:40]!r} og={_has_rich_meta(html_text)}"
                    )
                if resp.status >= 400:
                    return None
                return html_text, final_url
    except Exception as e:
        if trace is not None:
            trace.append(f"{agent}: {type(e).__name__}")
        return None


# Marketplace'lar (Uzum, Wildberries, Ozon...) datacenter so'rovlariga
# "Верификация"/captcha sahifasini beradi, lekin havola-preview botlariga
# (Telegram, Facebook, Twitter) mahsulot og:tag'larini beradi — aks holda
# Telegram'da havola preview'i chiqmasdi.
_PREVIEW_BOT_AGENTS = (
    "TelegramBot (like TwitterBot)",
    "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
    "Twitterbot/1.0",
)
_CHALLENGE_TITLE_RE = re.compile(
    r"верификац|проверка|just a moment|attention required|access denied|ddos-guard|"
    r"captcha|security check|are you a robot|robot check|доступ ограничен|bot protection|"
    # Vercel/Cloudflare/DDoS-Guard kabi hosting himoyasi sahifalari.
    r"security checkpoint|checking your browser|checking if the site|один момент|подождите|"
    # Xato sahifalari: "400", "403 Forbidden", "404 - Not Found", "Error"...
    # ("100 ta eng yaxshi..." kabi oddiy sarlavhalar tushib qolmasligi uchun
    # faqat 4xx/5xx kodi yolg'iz yoki xato so'zi bilan, xato so'zi esa yolg'iz).
    r"^\s*[45]\d\d\s*$|"
    r"^\s*[45]\d\d\s*[-:–—|]?\s*(error|forbidden|not found|bad request|unauthorized|"
    r"service unavailable|internal server error|ошибка|доступ запрещ)|"
    r"^\s*(error|forbidden|not found|bad request|service unavailable|ошибка)\s*$",
    re.I,
)


def _html_title(html_text: str) -> str:
    m = re.search(r"<title[^>]*>([^<]*)</title>", html_text, re.I)
    return unescape(m.group(1)).strip() if m else ""


def _is_challenge(html_text: str) -> bool:
    """Captcha / "Верификация" / "Just a moment" kabi anti-bot sahifa."""
    title = _extract_meta(html_text, "og:title") or _html_title(html_text)
    return bool(_CHALLENGE_TITLE_RE.search(title or ""))


def _has_rich_meta(html_text: str) -> bool:
    """og:title/og:image yoki schema.org Product bor — to'liq preview."""
    return bool(_extract_meta(html_text, "og:title", "og:image") or _json_ld_product(html_text))


def _json_ld_product(html_text: str) -> Optional[dict]:
    """schema.org Product (JSON-LD) — og:tag'lari yo'q marketplace sahifalari uchun."""
    for raw in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html_text, re.I | re.S):
        try:
            data = json.loads(raw.strip())
        except ValueError:
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, dict):
                types = node.get("@type")
                types = types if isinstance(types, list) else [types]
                if "Product" in types and node.get("name"):
                    return node
                stack.extend(v for k, v in node.items() if k == "@graph" or isinstance(v, (dict, list)))
    return None


def _json_ld_image(product: dict) -> str:
    image = product.get("image")
    if isinstance(image, list):
        image = image[0] if image else ""
    if isinstance(image, dict):
        image = image.get("url") or image.get("contentUrl") or ""
    return image if isinstance(image, str) else ""


# --- Wildberries: mahsulot kartasi ochiq CDN'dagi card.json'da ---------------
# Sayt brauzerda yig'iladigan ilova va datacenter so'rovlariga anti-bot sahifa
# beradi; har bir tovarning nomi/tavsifi/brendi esa
# basket-NN.wbbasket.ru/vol{V}/part{P}/{nm}/info/ru/card.json da, rasmlari
# o'sha papkadagi images/big/1.webp da.
_WB_HOST_RE = re.compile(r"(^|\.)(wildberries\.(ru|uz|kz|by|am|kg|ge|tj)|wb\.ru)$")
_WB_BASKET_VOL_LIMITS = (
    143, 287, 431, 719, 1007, 1061, 1115, 1169, 1313, 1601, 1655, 1919, 2045, 2189,
    2405, 2621, 2837, 3053, 3269, 3485, 3701, 3917, 4133, 4349, 4565, 4877, 5189,
    5501, 5813, 6125, 6437,
)
_WB_MAX_BASKET = 40


def _wildberries_nm_id(url: str) -> Optional[int]:
    parsed = urlparse(url)
    if not _WB_HOST_RE.search((parsed.hostname or "").lower()):
        return None
    m = re.search(r"/catalog/(\d{4,12})(?:/|$)", parsed.path)
    return int(m.group(1)) if m else None


def _wb_basket_guess(vol: int) -> int:
    for i, limit in enumerate(_WB_BASKET_VOL_LIMITS, start=1):
        if vol <= limit:
            return i
    return len(_WB_BASKET_VOL_LIMITS) + 1


def _wb_base_url(basket: int, nm_id: int) -> str:
    return f"https://basket-{basket:02d}.wbbasket.ru/vol{nm_id // 100000}/part{nm_id // 1000}/{nm_id}"


async def _fetch_json(url: str, headers: Optional[dict] = None, timeout: float = 5) -> Optional[Any]:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=timeout), headers={**_BROWSER_HEADERS, **(headers or {})},
            ) as resp:
                if resp.status != 200:
                    return None
                return json.loads(await resp.text(errors="ignore"))
    except Exception:
        return None


async def _fetch_wildberries(nm_id: int) -> Optional[dict]:
    """Tovar nomi (brend bilan), tavsifi va asosiy rasmi. Savat (basket)
    raqami jadvaldan taxmin qilinadi, bo'lmasa hammasi parallel sinaladi."""
    guess = _wb_basket_guess(nm_id // 100000)
    base, card = _wb_base_url(guess, nm_id), None
    card = await _fetch_json(base + "/info/ru/card.json")
    if not isinstance(card, dict):
        baskets = [b for b in range(1, _WB_MAX_BASKET + 1) if b != guess]
        results = await asyncio.gather(*(_fetch_json(_wb_base_url(b, nm_id) + "/info/ru/card.json") for b in baskets))
        for basket, result in zip(baskets, results):
            if isinstance(result, dict):
                base, card = _wb_base_url(basket, nm_id), result
                break
    if not isinstance(card, dict) or not card.get("imt_name"):
        return None
    brand = ((card.get("selling") or {}).get("brand_name") or "").strip()
    name = str(card["imt_name"]).strip()
    title = f"{brand} / {name}" if brand and brand.lower() not in name.lower() else name
    return {
        "platform": "website",
        "title": title[:120],
        "description": str(card.get("description") or "").strip()[:200],
        "photo_url": base + "/images/big/1.webp",
    }


# Qisqa havola xizmatlari — ular boshqa domenga yo'naltirishi tabiiy.
_SHORTENER_DOMAINS = {
    "bit.ly", "t.co", "goo.gl", "tinyurl.com", "cutt.ly", "is.gd", "clck.ru", "vk.cc",
    "rb.gy", "shorturl.at", "ow.ly", "buff.ly", "lnkd.in", "s.id", "tiny.cc", "linktr.ee",
}


def _base_domain(host: str) -> str:
    parts = host.lower().split(".")
    if len(parts) >= 3 and parts[-2] in {"com", "co", "org", "net", "gov", "edu"}:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _redirected_away(requested_url: str, final_url: str) -> bool:
    """Anti-bot himoyasi so'rovni butunlay boshqa saytga (masalan Uzum →
    ya.ru) yuborganmi. Qisqa havolalar uchun boshqa domen — tabiiy."""
    requested = _base_domain(urlparse(requested_url).hostname or "")
    final = _base_domain(urlparse(final_url).hostname or "")
    return bool(final) and requested != final and requested not in _SHORTENER_DOMAINS


async def _fetch_best_html(
    url: str, platform: str, on_blocked: Optional[Any] = None,
) -> Optional[tuple[str, str]]:
    """Avval oddiy brauzer sifatida; sahifa bloklangan ko'rinsa (captcha,
    og: yo'q, boshqa saytga yo'naltirilgan) — havola-preview botlari sifatida.
    Tezlik uchun: brauzer 1.2 soniyada javob bermasa yoki bloklansa, botlar
    bilan so'rovlar parallel yuboriladi (ketma-ket 4×6 soniya emas).
    on_blocked() — sayt bizni to'sganini birinchi sezganda (Microlink'ni
    oldindan boshlash uchun). Yaroqli sahifa bo'lmasa None."""
    def genuine(result: Optional[tuple[str, str]]) -> bool:
        return bool(result) and not _is_challenge(result[0]) and not _redirected_away(url, result[1])

    def good(result: Optional[tuple[str, str]]) -> bool:
        return genuine(result) and _has_rich_meta(result[0])

    browser = asyncio.create_task(_fetch_site_html(url, platform))
    done, _ = await asyncio.wait({browser}, timeout=1.2)
    if done and good(browser.result()):
        return browser.result()
    if done and not genuine(browser.result()) and on_blocked:
        on_blocked()
    agents = [
        asyncio.create_task(_fetch_site_html(url, platform, user_agent=agent))
        for agent in _PREVIEW_BOT_AGENTS
    ]
    pending = set(agents) | ({browser} if not done else set())
    # og: tag'lari bo'lmagan oddiy sahifa (Google, Mail.ru bosh sahifasi)
    # ham yaroqli — <title> va description ishlatiladi.
    fallback = browser.result() if done and genuine(browser.result()) else None
    try:
        # Qaysi so'rov birinchi to'liq sahifa bersa — shu (sekin brauzer
        # so'rovini kutib o'tirmasdan).
        while pending:
            finished, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in finished:
                result = task.result()
                if good(result):
                    return result
                if genuine(result):
                    fallback = fallback or result
                elif task is browser and on_blocked:
                    on_blocked()
        return fallback
    finally:
        for task in pending:
            task.cancel()


# --- Uzum Market: tovar ma'lumoti saytning o'z API'sidan -----------------------
_UZUM_HOST_RE = re.compile(r"(^|\.)uzum\.uz$")
_UZUM_API_BASES = ("https://api.uzum.uz/api/v2/product/", "https://api.umarket.uz/api/v2/product/")


def _uzum_product_id(url: str) -> Optional[int]:
    """uzum.uz/product/2833011, uzum.uz/ru/product/smartfon-...-2833011."""
    parsed = urlparse(url)
    if not _UZUM_HOST_RE.search((parsed.hostname or "").lower()) or (parsed.hostname or "").startswith("api."):
        return None
    m = re.search(r"/product/(?:[^/?#]*?-)?(\d{3,12})(?:[/?#]|$)", parsed.path + "/")
    return int(m.group(1)) if m else None


def _strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


async def _fetch_uzum(product_id: int) -> Optional[dict]:
    """Uzum veb-ilovasi ishlatadigan ochiq mahsulot API'si: nom, tavsif, rasm."""
    headers = {
        "Authorization": "Basic YjJjLWZyb250OmNsaWVudFNlY3JldA==",  # veb-ilovaning ochiq kaliti
        "x-iid": str(uuid.uuid4()),
        "Accept": "application/json",
        "Accept-Language": "uz-UZ,ru;q=0.9",
    }
    for base in _UZUM_API_BASES:
        payload = await _fetch_json(base + str(product_id), headers)
        data = ((payload or {}).get("payload") or {}).get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict) or not data.get("title"):
            continue
        photo_url = None
        for photo in data.get("photos") or []:
            if not isinstance(photo, dict):
                continue
            sizes = photo.get("photo") or {}
            for size in ("800", "720", "540", "480"):
                high = (sizes.get(size) or {}).get("high") if isinstance(sizes, dict) else None
                if high:
                    photo_url = high
                    break
            if not photo_url and photo.get("photoKey"):
                photo_url = f"https://images.uzum.uz/{photo['photoKey']}/t_product_540_high.jpg"
            if photo_url:
                break
        return {
            "platform": "website",
            "title": str(data["title"]).strip()[:120],
            "description": _strip_html(str(data.get("description") or ""))[:200],
            "photo_url": photo_url,
        }
    return None


def _is_content_page(url: str, html_text: str) -> bool:
    """Mahsulot/maqola sahifasimi (og:image — aynan shu narsaning rasmi) yoki
    saytning bosh sahifasimi (og:image ko'pincha banner — logotip afzal)."""
    og_type = _extract_meta(html_text, "og:type").lower()
    if og_type.startswith(("product", "article", "video", "music", "book")) or _json_ld_product(html_text):
        return True
    segments = [seg for seg in urlparse(url).path.split("/") if seg]
    return len(segments) >= 2 or any(re.search(r"\d{3,}", seg) for seg in segments)


_LOGO_MAX_BYTES = 512 * 1024


# Oxirgi muvaffaqiyatsiz rasm so'rovlarining sababi (tashxis uchun: /logo).
_IMAGE_ERRORS: dict[str, str] = {}


def _image_error(url: str, reason: str) -> None:
    if len(_IMAGE_ERRORS) > 500:
        _IMAGE_ERRORS.clear()
    _IMAGE_ERRORS[url] = reason


async def _fetch_image(url: str) -> Optional[tuple[bytes, str]]:
    """Rasmni yuklab oladi va haqiqiy rasm ekanini tekshiradi: 200 status,
    rasm turi (yoki .ico/PNG/JPEG/SVG imzosi), bo'sh emas. data: URI ham.
    (bayt, content_type) yoki None."""
    if url.startswith("data:image/"):
        m = re.match(r"data:(image/[\w.+-]+);base64,(.+)$", url, re.S)
        if not m:
            return None
        try:
            body = base64.b64decode(m.group(2), validate=False)
        except (ValueError, binascii.Error):
            return None
        return (body, m.group(1)) if len(body) >= 100 else None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=5), max_redirects=3,
                headers={**_BROWSER_HEADERS, "Accept": "image/avif,image/webp,image/png,image/svg+xml,image/*,*/*;q=0.8"},
            ) as resp:
                if resp.status != 200:
                    _image_error(url, f"HTTP {resp.status}")
                    return None
                # content.read(n) faqat kelgan birinchi bo'lakni qaytaradi —
                # rasm to'liq o'qiladi (aks holda buzuq rasm beriladi).
                chunks, size = [], 0
                async for chunk in resp.content.iter_chunked(64 * 1024):
                    size += len(chunk)
                    if size > _LOGO_MAX_BYTES:
                        _image_error(url, "juda katta")
                        return None
                    chunks.append(chunk)
                body = b"".join(chunks)
                ctype = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
    except Exception as e:
        _image_error(url, type(e).__name__)
        return None
    if len(body) < 100:
        _image_error(url, f"juda kichik ({len(body)} bayt)")
        return None
    if ctype.startswith("image/"):
        return body, ctype
    head = body[:256].lstrip().lower()
    if body[:4] == b"\x00\x00\x01\x00":
        return body, "image/x-icon"
    if body[:8] == b"\x89PNG\r\n\x1a\n":
        return body, "image/png"
    if body[:3] == b"\xff\xd8\xff":
        return body, "image/jpeg"
    if head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in body[:1024].lower()):
        return body, "image/svg+xml"
    _image_error(url, f"rasm emas ({ctype or 'turi yo`q'})")
    return None


# Topilgan logotipning o'zi (baytlari) keshlanadi va sahifaga serverdan
# beriladi — telefon boshqa saytga umuman murojaat qilmaydi (hotlink
# himoyasi, geo-bloklash, Telegram brauzerini to'sish muammo bo'lmaydi).
_LOGO_CACHE: dict[str, tuple[Optional[tuple[bytes, str]], float]] = {}
_LOGO_CACHE_MAX = 400


def _logo_cache_get(key: str):
    cached = _LOGO_CACHE.get(key)
    if cached and time.monotonic() < cached[1]:
        return True, cached[0]
    return False, None


def _logo_cache_put(key: str, logo: Optional[tuple[bytes, str]]) -> None:
    if len(_LOGO_CACHE) >= _LOGO_CACHE_MAX:
        _LOGO_CACHE.clear()
    _LOGO_CACHE[key] = (logo, time.monotonic() + (86400 if logo else 1800))


def _logo_fallback_urls(host: str) -> list[str]:
    """Saytning o'zidan topilmasa — ommaviy ikonka xizmatlari (topilmasa
    404 qaytaradi, shuning uchun tekshirib bo'ladi)."""
    return [
        "https://t1.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON"
        f"&fallback_opts=TYPE,SIZE,URL&url=https://{host}&size=128",
        f"https://www.google.com/s2/favicons?domain={host}&sz=128",
        f"https://icons.duckduckgo.com/ip3/{host}.ico",
    ]


async def _manifest_icons(html_text: str, base_url: str) -> list[str]:
    """<link rel="manifest"> (manifest.json) dagi ikonkalar, kattasi birinchi."""
    m = re.search(r"<link\b[^>]*rel=[\"']manifest[\"'][^>]*>", html_text, re.I)
    href = re.search(r'href=[\"\']([^\"\']+)[\"\']', m.group(0), re.I) if m else None
    if not href:
        return []
    manifest_url = urljoin(base_url, unescape(href.group(1)))
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                manifest_url, timeout=aiohttp.ClientTimeout(total=5), headers=_BROWSER_HEADERS,
            ) as resp:
                data = json.loads(await resp.text(errors="ignore"))
    except Exception:
        return []
    icons = []
    for icon in data.get("icons") or []:
        if not isinstance(icon, dict) or not icon.get("src"):
            continue
        sizes = [int(n) for n in re.findall(r"(\d+)x\d+", str(icon.get("sizes", "")))]
        full = _absolute_image_url(manifest_url, icon["src"])
        if full:
            icons.append((max(sizes) if sizes else 0, full))
    icons.sort(key=lambda item: -item[0])
    return [url for _, url in icons[:3]]


async def _resolve_brand_logo(host: str, trace: Optional[list] = None) -> Optional[tuple[bytes, str]]:
    """Brend logotipini universal qidiradi, birinchi ishlaydiganini qaytaradi:
    1) sahifadagi apple-touch-icon / katta icon / SVG (data: ham),
    2) manifest.json ikonkalari, 3) /apple-touch-icon.png,
    4) Google (gstatic, s2), DuckDuckGo, 5) kichik favicon.
    Natija xost bo'yicha keshlanadi."""
    if trace is None:
        hit, cached = _logo_cache_get("host:" + host)
        if hit:
            return cached

    origin = f"https://{host}"
    site_allowed = await _resolve_is_public_host(host)
    touch_icons = [f"{origin}/apple-touch-icon.png", f"{origin}/apple-touch-icon-precomposed.png"]
    fallbacks = _logo_fallback_urls(host)
    probe_urls = (touch_icons if site_allowed else []) + fallbacks

    async def no_html():
        return None

    html_result, *probe_results = await asyncio.gather(
        _fetch_site_html(origin + "/") if site_allowed else no_html(),
        *(_fetch_image(u) for u in probe_urls),
    )
    fetched = dict(zip(probe_urls, probe_results))

    big_icons: list[str] = []
    small_icons: list[str] = []
    manifest: list[str] = []
    # Himoya sahifasining ikonkasi (masalan Vercel uchburchagi) sayt logotipi emas.
    if html_result and _is_challenge(html_result[0]):
        html_result = None
    if html_result:
        for score, url in _site_icon_candidates(*html_result):
            (big_icons if score >= 96 else small_icons).append(url)
        manifest = await _manifest_icons(*html_result)
    if site_allowed:
        small_icons.append(f"{origin}/favicon.ico")

    ordered = big_icons[:3] + manifest + (touch_icons if site_allowed else []) + fallbacks + small_icons[:3]
    # Sayt bizni to'sgan bo'lsa — Microlink (haqiqiy brauzer). Sahifadagi
    # logotip topilsa Google/DuckDuckGo ikonkasidan oldin; sayt faviconi
    # Next.js standarti bo'lsa, ular (o'sha uchburchak) umuman olinmaydi.
    if site_allowed and not html_result:
        microlink = await _fetch_microlink(origin + "/")
        if microlink:
            if microlink.get("favicon_default"):
                ordered = [u for u in ordered if u not in fallbacks]
            if microlink.get("logo"):
                if microlink.get("logo_strong"):
                    ordered.insert(len(touch_icons), microlink["logo"])
                else:
                    ordered.append(microlink["logo"])
    # Qolgan nomzodlar parallel yuklanadi (ketma-ket 5 soniyadan kutilmaydi),
    # tartib bo'yicha birinchi ishlagani olinadi.
    missing = [u for u in dict.fromkeys(ordered) if u not in fetched]
    for u, r in zip(missing, await asyncio.gather(*(_fetch_image(u) for u in missing))):
        fetched[u] = r
    logo: Optional[tuple[bytes, str]] = None
    tried: list[str] = []
    for url in ordered:
        result = fetched[url]
        tried.append(f"{url[:80]} = {'ok' if result else _IMAGE_ERRORS.get(url, 'no')}")
        if result:
            logo = result
            break
    if not logo:
        logging.info("Logotip topilmadi: %s (html=%s) %s", host, bool(html_result), "; ".join(tried))
    if trace is not None:
        trace.append({"host": host, "site_allowed": site_allowed, "html": bool(html_result), "tried": tried})
    _logo_cache_put("host:" + host, logo)
    return logo


def _valid_host(host: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", host)) and len(host) <= 253


async def _resolve_logo_for_url(url: str, trace: Optional[list] = None) -> Optional[tuple[bytes, str]]:
    """Istalgan havola uchun logotip:
    - Telegram/Instagram/YouTube/App Store/Google Play — sahifaning og:image'i
      (profil/kanal/ilova rasmi), bo'lmasa platformaning o'z logotipi;
    - oddiy sayt — redirectdan keyingi (bit.ly kabi qisqa havolalar ham)
      yakuniy domen bo'yicha universal qidiruv."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not _valid_host(host):
        return None
    platform = _derive_ad_platform(url)
    key = "url:" + url
    if trace is None:
        hit, cached = _logo_cache_get(key)
        if hit:
            return cached

    logo: Optional[tuple[bytes, str]] = None
    wb_nm_id, uzum_id = _wildberries_nm_id(url), _uzum_product_id(url)
    product = (
        await _fetch_wildberries(wb_nm_id) if wb_nm_id
        else await _fetch_uzum(uzum_id) if uzum_id
        else None
    )
    if product and product.get("photo_url"):
        logo = await _fetch_image(product["photo_url"])
        if logo:
            _logo_cache_put(key, logo)
            return logo
    fetched = await _fetch_site_html(url, platform) if await _resolve_is_public_host(host) else None
    if platform != "website":
        if fetched:
            og_image = _absolute_image_url(fetched[1], _extract_meta(fetched[0], "og:image", "twitter:image"))
            if og_image:
                logo = await _fetch_image(og_image)
        if not logo:
            logo = await _resolve_brand_logo(host.removeprefix("www.").removeprefix("m."), trace)
    else:
        # Anti-bot boshqa saytga (masalan ya.ru) yuborgan bo'lsa — o'sha saytning
        # logotipi emas, asl domenniki olinadi.
        final_host = (
            (urlparse(fetched[1]).hostname or host).lower()
            if fetched and not _redirected_away(url, fetched[1]) else host
        )
        if trace is not None:
            trace.append({"url": url, "final_url": fetched[1] if fetched else None})
        logo = await _resolve_brand_logo(final_host.removeprefix("www."), trace)

    _logo_cache_put(key, logo)
    return logo


async def _db_cached_logo(key: str) -> Optional[tuple[bytes, str]]:
    """Xotirada yo'q bo'lsa — bazadagi logotip (server qayta ishga tushgandan
    keyin ham saytlarni qayta qidirmasdan darhol)."""
    hit, logo = _logo_cache_get(key)
    if hit:
        return logo
    try:
        logo = await get_ad_logo_cache(key)
    except Exception:
        logging.exception("ad_logo_cache o'qilmadi")
        return None
    if logo:
        _logo_cache_put(key, logo)
    return logo


async def _save_logo_db(key: str, logo: tuple[bytes, str]) -> None:
    try:
        await put_ad_logo_cache(key, logo[0], logo[1])
    except Exception:
        logging.exception("ad_logo_cache yozilmadi")


def _spawn(coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


async def api_ads_logo(request: web.Request) -> web.Response:
    """<img src="/api/ads/logo?url=..."> (yoki ?host=...) — logotip rasmining
    o'zi (server orqali), topilmasa 404 (sahifa emoji ko'rsatadi). Img so'rovi
    sarlavha yubora olmagani uchun autentifikatsiyasiz."""
    raw_url = (request.query.get("url") or "").strip()
    # ?debug=1 — keshsiz qidirib, har bir manba natijasini JSON'da ko'rsatadi.
    trace: Optional[list] = [] if request.query.get("debug") == "1" else None
    if raw_url:
        if not re.match(r"^https?://", raw_url, re.I):
            raw_url = "https://" + raw_url
        if len(raw_url) > 2000 or not _valid_host((urlparse(raw_url).hostname or "").lower()):
            raise web.HTTPBadRequest(text="invalid url")
        key = "url:" + raw_url
        resolve = lambda: _resolve_logo_for_url(raw_url, trace)  # noqa: E731
    else:
        host = (request.query.get("host") or "").strip().lower().removeprefix("www.")
        if not _valid_host(host):
            raise web.HTTPBadRequest(text="invalid host")
        key = "host:" + host
        resolve = lambda: _resolve_brand_logo(host, trace)  # noqa: E731
    logo = await _db_cached_logo(key) if trace is None else None
    if logo is None:
        logo = await resolve()
        if logo and trace is None:
            _spawn(_save_logo_db(key, logo))
    if trace is not None:
        return web.json_response({
            "found": bool(logo), "bytes": len(logo[0]) if logo else 0,
            "content_type": logo[1] if logo else None, "trace": trace,
        })
    if not logo:
        raise web.HTTPNotFound(headers={"Cache-Control": "public, max-age=1800"})
    body, ctype = logo
    return web.Response(
        body=body, content_type=ctype,
        # SVG bizning domenda skript ishga tushira olmasin.
        headers={
            "Cache-Control": "public, max-age=86400",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
        },
    )


# --- Microlink: sayt serverimizni to'sganda (Vercel/Cloudflare himoyasi,
# geo-bloklash) sahifani haqiqiy brauzerda ochib, nom/tavsif/logotip beradi.
# Bepul tarif kuniga ~50 so'rov — faqat kerak bo'lganda va keshlanib ishlatiladi.
_MICROLINK_CACHE: dict[str, tuple[Optional[dict], float]] = {}


# Microlink MQL qoidasi: sahifadagi birinchi logotip rasmi (odatda sarlavhada).
_MICROLINK_LOGO_RULES = "&" + "&".join(
    k + "=" + quote(v, safe="")
    for k, v in (
        ("data.brandLogo.selector",
         'header img[src*="logo" i], header img[alt*="logo" i], [class*="logo" i] img, '
         'img[class*="logo" i], img[src*="logo" i], img[alt*="logo" i], header a[href="/"] img'),
        ("data.brandLogo.attr", "src"),
        ("data.brandLogo.type", "url"),
        # Logotip ko'pincha sahifaga to'g'ridan-to'g'ri chizilgan <svg> bo'ladi.
        ("data.svgLogo.selector",
         '[class*="logo" i]:has(svg), [id*="logo" i]:has(svg), '
         'header a[href="/"]:has(svg), a[href="/"]:has(svg)'),
        ("data.svgLogo.attr", "html"),
        # Barcha rasmlar: fayl nomida brend nomi bor rasm (masalan /img/islom.png).
        ("data.imgs.selectorAll", "img"),
        ("data.imgs.attr", "src"),
    )
)

_NOT_LOGO_IMG_RE = re.compile(r"banner|header_|/bg|background|slide|cover|poster|hero", re.I)


def _svg_data_uri(markup: Any) -> Optional[str]:
    """Sahifadagi <svg> logotipni data: URI'ga aylantiradi (/api/ads/logo beradi)."""
    if not isinstance(markup, str):
        return None
    m = re.search(r"<svg\b[\s\S]*?</svg>", markup, re.I)
    if not m:
        return None
    svg = m.group(0)
    if len(svg) > 200_000 or not re.search(r"<(path|circle|rect|polygon|ellipse|text|image)\b", svg, re.I):
        return None   # bo'sh yoki faqat <use href="#sprite"> — alohida ko'rsatib bo'lmaydi
    if "xmlns=" not in svg[:300]:
        svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def _brand_named_img(imgs: Any, page_url: str) -> Optional[str]:
    """Fayl nomida sayt nomi (islom.uz → "islom") bo'lgan birinchi rasm."""
    host = (urlparse(page_url).hostname or "").lower().removeprefix("www.")
    label = host.split(".")[0]
    if len(label) < 3:
        return None
    for src in imgs if isinstance(imgs, list) else [imgs]:
        if not isinstance(src, str) or not src.strip() or src.startswith("data:"):
            continue
        full = urljoin(page_url, src.strip())
        name = urlparse(full).path.rsplit("/", 1)[-1].lower()
        if label in name and not _NOT_LOGO_IMG_RE.search(name) and not _is_default_favicon(full):
            return full
    return None


_MICROLINK_INFLIGHT: dict[str, "asyncio.Future[Optional[dict]]"] = {}


def _microlink_key(url: str) -> str:
    """https://Islom.uz, https://islom.uz/ — bitta kalit (bitta so'rov, bitta kesh)."""
    parsed = urlparse(url)
    path = parsed.path if parsed.path not in ("", "/") else ""
    return f"https://{(parsed.hostname or '').lower()}{path}" + (f"?{parsed.query}" if parsed.query else "")


async def _fetch_microlink(url: str) -> Optional[dict]:
    url = _microlink_key(url)
    cached = _MICROLINK_CACHE.get(url)
    if cached and time.monotonic() < cached[1]:
        _microlink_trace(cached[0], cached=True)
        return cached[0]
    # Preview va logotip bir vaqtda so'rasa — bitta Microlink so'rovi.
    inflight = _MICROLINK_INFLIGHT.get(url)
    if inflight:
        result = await asyncio.shield(inflight)
        _microlink_trace(result, cached=True)
        return result
    task = asyncio.ensure_future(_fetch_microlink_uncached(url))
    _MICROLINK_INFLIGHT[url] = task
    try:
        return await asyncio.shield(task)
    finally:
        if task.done():
            _MICROLINK_INFLIGHT.pop(url, None)
        else:
            task.add_done_callback(lambda _t: _MICROLINK_INFLIGHT.pop(url, None))


async def _fetch_microlink_uncached(url: str) -> Optional[dict]:
    now = time.monotonic()
    # Microlink sahifani haqiqiy brauzerda ochadi — 5–10 soniya ketishi mumkin.
    # Qo'shimcha qoida: sayt sarlavhasidagi logotip rasmi (<img ...logo...>) —
    # favicon standart/kichik, og:image esa keng banner bo'lgan saytlar uchun.
    base = "https://api.microlink.io/?url=" + quote(url, safe="")
    payload = await _fetch_json(base + _MICROLINK_LOGO_RULES, timeout=20)
    if not (isinstance(payload, dict) and payload.get("status") == "success"):
        payload = await _fetch_json(base, timeout=20)
    result: Optional[dict] = None
    if isinstance(payload, dict) and payload.get("status") == "success" and isinstance(payload.get("data"), dict):
        data = payload["data"]
        title = str(data.get("title") or "").strip()
        if not _CHALLENGE_TITLE_RE.search(title):
            logo = data.get("logo") if isinstance(data.get("logo"), dict) else {}
            image = data.get("image") if isinstance(data.get("image"), dict) else {}
            # Logotip kichik/.ico favicon yoki Next.js standart ikonkasi bo'lsa —
            # sahifaning asosiy rasmi (odatda katta logotip) afzal; rasm
            # kartada "contain" bilan ko'rsatilgani uchun kesilmaydi.
            logo_url = logo.get("url") or None
            weak_logo = (
                not logo_url
                or _is_default_favicon(logo_url)
                or (logo.get("width") or 0) < 96
                or urlparse(logo_url).path.lower().endswith(".ico")
            )
            if _is_default_favicon(logo_url):
                logo_url = None
            image_url = image.get("url") or None
            iw, ih = image.get("width") or 0, image.get("height") or 0
            wide_image = bool(iw and ih and iw / ih > 2)   # keng banner — logotip emas
            page_url = str(data.get("url") or url)
            header_logo = data.get("brandLogo")
            if isinstance(header_logo, dict):
                header_logo = header_logo.get("url")
            header_logo = header_logo.strip() if isinstance(header_logo, str) else ""
            if header_logo and not header_logo.startswith("data:"):
                header_logo = urljoin(page_url, header_logo)
            if not header_logo.startswith(("http://", "https://")) or _is_default_favicon(header_logo):
                header_logo = None
            page_logo = (header_logo or _svg_data_uri(data.get("svgLogo"))
                         or _brand_named_img(data.get("imgs"), page_url))
            if not weak_logo:
                best_logo = logo_url
            else:
                # Keng banner logotip sifatida olinmaydi — u holda kartadagi
                # rasm /api/ads/logo universal qidiruvidan (Google ikonkasi...).
                best_logo = page_logo or (None if wide_image else image_url) or logo_url
            result = {
                "title": title,
                "description": str(data.get("description") or "").strip(),
                "logo": best_logo,
                "logo_strong": bool(not weak_logo or page_logo),
                # Sayt faviconi Next.js standarti — Google/DuckDuckGo ham shu
                # uchburchakni qaytaradi, ular ishlatilmaydi.
                "favicon_default": _is_default_favicon(logo.get("url")),
                "image": image_url,
                "image_wide": wide_image,
                "diag": (
                    f"microlink: logo={str(logo.get('url') or '-')[:60]} ({logo.get('width')}px) · "
                    f"sarlavha_logo={str(header_logo or '-')[:60]} · "
                    f"svg={'bor' if _svg_data_uri(data.get('svgLogo')) else 'yoq'} · "
                    f"rasmlar={len(data['imgs']) if isinstance(data.get('imgs'), list) else 0} · "
                    f"image={str(image_url or '-')[:60]} ({iw}x{ih}) → {str(best_logo or '-')[:60]}"
                ),
            }
    if len(_MICROLINK_CACHE) > 500:
        _MICROLINK_CACHE.clear()
    # Muvaffaqiyatsiz natija qisqa keshlanadi (vaqtinchalik xato bo'lishi mumkin).
    _MICROLINK_CACHE[url] = (result, now + (86400 if result else 600))
    _microlink_trace(result)
    return result


def _microlink_trace(result: Optional[dict], cached: bool = False) -> None:
    trace = _FETCH_TRACE.get()
    if trace is not None:
        line = result["diag"] if result else "microlink: natija yo'q"
        trace.append(line + (" (kesh)" if cached else ""))


def _microlink_photo(microlink: dict) -> Optional[str]:
    """Kartadagi rasm: logotip, bo'lmasa keng bo'lmagan asosiy rasm. None —
    frontend /api/ads/logo universal qidiruvini ishlatadi."""
    logo = microlink["logo"]
    if logo and logo.startswith("data:"):
        return None   # sahifadagi <svg> — /api/ads/logo orqali beriladi
    return logo or (None if microlink.get("image_wide") else microlink["image"])


class _AdPreviewError(Exception):
    def __init__(self, status: int, reason: str):
        super().__init__(reason)
        self.status = status
        self.reason = reason


_PREVIEW_CACHE: dict[str, tuple[dict, float]] = {}
_PREVIEW_INFLIGHT: dict[str, "asyncio.Future[dict]"] = {}


async def _fetch_ad_preview(bot: Bot, url: str) -> dict:
    """Keshlangan preview: bir havola qayta yozilsa/ochilsa darhol javob;
    bir vaqtdagi bir xil so'rovlar birlashtiriladi. /preview (tashxis) keshsiz."""
    if _FETCH_TRACE.get() is not None:
        return await _fetch_ad_preview_uncached(bot, url)
    key = url.strip().rstrip("/").lower()
    key = key if re.match(r"^https?://", key) else "https://" + key
    cached = _PREVIEW_CACHE.get(key)
    if cached and time.monotonic() < cached[1]:
        return dict(cached[0])
    inflight = _PREVIEW_INFLIGHT.get(key)
    if inflight:
        return dict(await asyncio.shield(inflight))
    task = asyncio.ensure_future(_fetch_ad_preview_uncached(bot, url))
    _PREVIEW_INFLIGHT[key] = task
    task.add_done_callback(lambda _t: _PREVIEW_INFLIGHT.pop(key, None))
    preview = await asyncio.shield(task)
    if len(_PREVIEW_CACHE) > 500:
        _PREVIEW_CACHE.clear()
    _PREVIEW_CACHE[key] = (preview, time.monotonic() + (3600 if preview.get("title") else 300))
    return dict(preview)


async def _fetch_ad_preview_uncached(bot: Bot, url: str) -> dict:
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
        if not username:
            raise _AdPreviewError(400, "invalid telegram link")
        if not username.startswith("+") and username.lower() != "joinchat":
            try:
                chat = await bot.get_chat("@" + username)
            except TelegramAPIError:
                chat = None
            if chat:
                title = chat.title or " ".join(filter(None, [chat.first_name, chat.last_name])) or username
                description = chat.description or chat.bio or ""
                photo_url = f"/api/photo/{chat.photo.small_file_id}" if chat.photo else None
                return {"platform": "telegram", "title": title, "description": description, "photo_url": photo_url}
        # Bot ko'ra olmaydigan foydalanuvchilar, yopiq guruh taklif havolalari:
        # ochiq t.me sahifasidagi nom, bio va avatar.
        fetched = await _fetch_site_html(f"https://t.me/{parsed.path.strip('/')}", "telegram")
        title = _extract_meta(fetched[0], "og:title") if fetched else ""
        if not title:
            raise _AdPreviewError(404, "chat_not_found")
        return {
            "platform": "telegram",
            "title": title[:120],
            "description": _extract_meta(fetched[0], "og:description")[:200],
            "photo_url": _absolute_image_url(fetched[1], _extract_meta(fetched[0], "og:image")),
        }

    if not await _resolve_is_public_host(host):
        raise _AdPreviewError(400, "host_not_allowed")

    wb_nm_id = _wildberries_nm_id(url)
    if wb_nm_id:
        wb = await _fetch_wildberries(wb_nm_id)
        if wb:
            return wb
    uzum_id = _uzum_product_id(url)
    if uzum_id:
        uzum = await _fetch_uzum(uzum_id)
        if uzum:
            return uzum

    # Sayt bizni to'sgani sezilishi bilan Microlink parallel boshlanadi
    # (botlar bilan qayta urinishlarni kutmasdan).
    microlink_task: Optional[asyncio.Task] = None

    def start_microlink() -> None:
        nonlocal microlink_task
        if platform == "website" and microlink_task is None:
            microlink_task = _spawn(_fetch_microlink(url))

    async def get_microlink() -> Optional[dict]:
        start_microlink()
        return await microlink_task if microlink_task else None

    fetched = await _fetch_best_html(url, platform, start_microlink)
    if not fetched:
        # Sayt serverimizni to'sdi (captcha, "Верификация", Vercel himoyasi...):
        # Microlink orqali urinib ko'riladi. Bo'lmasa bo'sh — sahifa domen
        # nomini, logotipni esa /api/ads/logo'dan ko'rsatadi.
        microlink = await get_microlink()
        if microlink and microlink["title"]:
            return {
                "platform": platform,
                "title": microlink["title"][:120],
                "description": microlink["description"][:200],
                "photo_url": microlink["image"] if _is_content_page(url, "") else _microlink_photo(microlink),
            }
        return {"platform": platform, "title": "", "description": "", "photo_url": None}
    html_text, base_url = fetched
    product = _json_ld_product(html_text) or {}

    title = (
        _extract_meta(html_text, "og:title", "twitter:title")
        or str(product.get("name") or "").strip()
        or _html_title(html_text)
    )
    description = (
        _extract_meta(html_text, "og:description", "twitter:description")
        or unescape(str(product.get("description") or "")).strip()
        or _extract_meta(html_text, "description")
    )
    og_image = _absolute_image_url(
        base_url, _extract_meta(html_text, "og:image", "twitter:image") or _json_ld_image(product)
    )
    icon = _extract_site_icon(html_text, base_url)
    # Bosh sahifada og:image ko'pincha keng banner — logotip afzal. Mahsulot/
    # maqola sahifasida (marketplace tovari) va Instagram/YouTube/do'konlarda
    # esa og:image aynan shu narsaning rasmi.
    if platform == "website" and not _is_content_page(base_url, html_text):
        photo_url = icon or og_image
    else:
        photo_url = og_image or icon

    # Tavsif yo'q (ko'pincha JS bilan yig'iladigan saytlar) — Microlink'dan.
    if platform == "website" and not description:
        microlink = await get_microlink()
        if microlink:
            description = microlink["description"]
            title = title or microlink["title"]
            photo_url = photo_url or _microlink_photo(microlink)

    return {
        "platform": platform,
        "title": title[:120],
        "description": description[:200],
        "photo_url": photo_url,
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
        "payment": {
            "enabled": _ad_payments_enabled(),
            "card": AD_CARD_NUMBER,
            "holder": AD_CARD_HOLDER,
        },
        "my_pending": [
            {
                "kind": p["kind"], "amount": p["amount"], "brand_name": p["brand_name"],
                "rank": _projected_ad_rank(bids, p),
            }
            for p in await get_pending_ad_payments(telegram_id)
        ],
        "my_rejected": await _my_rejected_payments(telegram_id),
    })


async def _my_rejected_payments(telegram_id: int) -> list[dict]:
    """Rad etilgan to'lovlar sababi bilan; tayyor sabablar (ad_reject_*)
    foydalanuvchi tiliga o'giriladi, admin yozgan matn o'zgarishsiz."""
    rejected = await get_recent_rejected_ad_payments(telegram_id)
    if not rejected:
        return []
    lang = await _lang_for(telegram_id)
    result = []
    for p in rejected:
        reason = p["reject_reason"] or ""
        if reason.startswith("ad_reject_"):
            reason = t(lang, reason)
        result.append({
            "id": p["id"], "kind": p["kind"], "amount": p["amount"],
            "brand_name": p["brand_name"], "reason": reason,
        })
    return result


async def api_ads_dismiss_rejection(request: web.Request) -> web.Response:
    """"Rad etildi" blokini yopish (×) — keyin ko'rsatilmaydi."""
    telegram_id = await _require_user_id(request)
    if not await dismiss_ad_payment_rejection(int(request.match_info["id"]), telegram_id):
        raise web.HTTPNotFound()
    return web.json_response({"ok": True})


def _projected_ad_rank(approved_bids: list[dict], pending: dict) -> int:
    """To'lov tasdiqlansa reklama nechanchi o'ringa chiqadi — "#N reyting
    uchun". Teng summada avvalgi takliflar oldinda turadi."""
    target = pending["amount"] if pending["kind"] == "new" else pending["bid_amount"] + pending["amount"]
    ahead = sum(1 for b in approved_bids if b["id"] != pending["bid_id"] and b["bid_amount"] >= target)
    return ahead + 1


def _ad_payments_enabled() -> bool:
    return bool(AD_CARD_NUMBER and AD_ADMIN_IDS)


async def api_ads_payment(request: web.Request) -> web.Response:
    """Reklama to'lovi cheki: yangi reklama (kind=new) yoki "Taklifni
    oshirish" (kind=raise). Chek adminlarga yuboriladi; admin tasdiqlaguncha
    reklama reytingda ko'rinmaydi / summa oshmaydi."""
    telegram_id = await _require_user_id(request)
    if not _ad_payments_enabled():
        raise web.HTTPServiceUnavailable(text="payments_not_configured")
    fields, photo_bytes, filename = await _read_multipart_photo(request)
    kind = fields.get("kind")

    if kind == "new":
        brand_name = (fields.get("brand_name") or "").strip()
        url = (fields.get("url") or "").strip()
        if not brand_name or not url:
            raise web.HTTPBadRequest(text="missing fields")
        if not re.match(r"^https?://", url):
            url = "https://" + url
        try:
            bid_amount = int(fields.get("bid_amount") or 0)
        except ValueError:
            raise web.HTTPBadRequest(text="invalid bid_amount")
        if bid_amount < AD_MIN_STARTING_BID:
            raise web.HTTPConflict(text="bid_too_low")
        # Platforma URL manzilidan serverda aniqlanadi (klientga ishonilmaydi).
        category = fields.get("category")
        bid_id, payment_id = await create_ad_payment_new(
            telegram_id, brand_name[:80], url, bid_amount, _derive_ad_platform(url),
            _sanitize_ad_photo_url(fields.get("photo_url")),
            category if category in _AD_CATEGORY_KEYS else None,
            _sanitize_ad_description(fields.get("description")),
        )
        amount = bid_amount
    elif kind == "raise":
        try:
            bid_id = int(fields.get("bid_id") or 0)
        except ValueError:
            raise web.HTTPBadRequest(text="invalid bid_id")
        existing = await get_ad_bid(bid_id)
        if not existing or existing["status"] != "approved":
            raise web.HTTPNotFound()
        if existing["telegram_id"] != telegram_id:
            raise web.HTTPForbidden(text="not_owner")
        amount = AD_MIN_INCREMENT
        payment_id = await create_ad_payment_raise(bid_id, telegram_id, amount)
    else:
        raise web.HTTPBadRequest(text="invalid kind")

    bid = await get_ad_bid(bid_id)
    caption = admin_caption(payment_id, kind, amount, bid, telegram_id)
    file_id = await send_receipt_to_admins(request.app["bot"], photo_bytes, filename, caption, payment_id)
    if not file_id:
        await delete_ad_payment(payment_id)
        raise web.HTTPBadGateway(text="admin_unreachable")
    await set_ad_payment_receipt(payment_id, file_id)
    return web.json_response({"ok": True, "payment_id": payment_id})


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
    app.router.add_get("/api/ads/logo", api_ads_logo)
    app.router.add_get("/api/ads/leaderboard", api_ads_leaderboard)
    app.router.add_post("/api/ads/payment", api_ads_payment)
    app.router.add_post("/api/ads/payments/{id:\\d+}/dismiss", api_ads_dismiss_rejection)
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
