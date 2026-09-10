from html import escape
from typing import Optional

from aiogram import Bot
from aiogram.types import BufferedInputFile, InputMediaPhoto
from aiohttp import web

from bot.config import BASE_URL
from bot.database import (
    cancel_reservation,
    count_pending_receive,
    count_pending_ship,
    create_donation,
    create_reservation,
    create_user_if_missing,
    count_new_donations_last_24h,
    delete_donation,
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
    set_donation_status,
    set_reservation_received,
    set_reservation_shipped,
    set_user_language,
    set_user_role,
    toggle_donation_like,
)
from bot.texts import CATEGORIES, LANGUAGES, category_name, status_label, t
from bot.webapp_auth import validate_init_data


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


def _donation_json(d: dict, lang: str, like_count: int = 0, liked_by_me: bool = False) -> dict:
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
            )
            for d in donations
        ]
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
                "receipt_photo_url": (
                    f"/api/photo/{r['receipt_photo_file_id']}"
                    if r["receipt_photo_file_id"]
                    else None
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

    reservation_id = await create_reservation(
        donation_id, telegram_id, full_name, address, phone
    )
    await set_donation_status(donation_id, "reserved")

    donor_lang = await _lang_for(donation["donor_id"])
    bot: Bot = request.app["bot"]
    await bot.send_message(
        donation["donor_id"],
        t(
            donor_lang,
            "new_reservation_for_donor",
            category=category_name(donation["category"], donor_lang),
            description=donation["description"],
            full_name=full_name,
            address=address,
            phone=phone,
        ),
    )
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

    await set_reservation_received(reservation_id, dua_text)
    donation = await get_donation(reservation["donation_id"])
    await set_donation_status(donation["id"], "received")

    donor_lang = await _lang_for(donation["donor_id"])
    bot: Bot = request.app["bot"]
    await bot.send_message(
        donation["donor_id"],
        t(donor_lang, "received_notify_donor", dua_text=dua_text),
    )
    return web.json_response({"ok": True})


async def api_ad_view(request: web.Request) -> web.Response:
    await _require_user_id(request)
    body = await request.json()
    slide = body.get("slide")
    if slide not in (1, 2, 3, 4, 5, 6, 7, 8):
        raise web.HTTPBadRequest(text="invalid slide")
    views = await increment_ad_views(slide)
    return web.json_response({"slide": slide, "views": views})


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

    donation = await get_donation(reservation["donation_id"])
    await cancel_reservation(reservation_id)
    await set_donation_status(reservation["donation_id"], "available")

    if donation:
        donor_lang = await _lang_for(donation["donor_id"])
        bot: Bot = request.app["bot"]
        await bot.send_message(
            donation["donor_id"],
            t(donor_lang, "reservation_cancelled_notify_donor", description=donation["description"]),
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
    lang = await _lang_for(telegram_id)
    bot: Bot = request.app["bot"]

    if len(photos) == 1:
        photo_bytes, filename = photos[0]
        sent = await bot.send_photo(
            chat_id=telegram_id,
            photo=BufferedInputFile(photo_bytes, filename=filename),
            caption=t(lang, "donation_added"),
        )
        photo_file_ids = [sent.photo[-1].file_id]
    else:
        media = [
            InputMediaPhoto(
                media=BufferedInputFile(photo_bytes, filename=filename),
                caption=t(lang, "donation_added") if i == 0 else None,
            )
            for i, (photo_bytes, filename) in enumerate(photos)
        ]
        sent_messages = await bot.send_media_group(chat_id=telegram_id, media=media)
        photo_file_ids = [msg.photo[-1].file_id for msg in sent_messages]

    donation_id = await create_donation(
        donor_id=telegram_id,
        category=category,
        photo_file_ids=photo_file_ids,
        description=description,
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

    sent = await bot.send_photo(
        chat_id=telegram_id,
        photo=BufferedInputFile(photo_bytes, filename=filename),
        caption=t(lang, "shipped_saved_donor"),
    )
    photo_file_id = sent.photo[-1].file_id

    await set_reservation_shipped(reservation_id, photo_file_id, receipt_note)
    await set_donation_status(donation["id"], "shipped")

    needy_lang = await _lang_for(reservation["needy_id"])
    await bot.send_photo(
        chat_id=reservation["needy_id"],
        photo=photo_file_id,
        caption=t(needy_lang, "shipped_notify_needy"),
    )
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


async def donation_share_page(request: web.Request) -> web.Response:
    """Ehsonni Telegram'da 'post' ko'rinishida (rasm + sarlavha bilan)
    ulashish uchun statik sahifa — Telegram link preview shu OG teglarni
    o'qib, rasmli karta ko'rsatadi."""
    donation_id = int(request.match_info["id"])
    donation = await get_donation(donation_id)
    if not donation:
        raise web.HTTPNotFound()

    title = category_name(donation["category"], "uz")
    description = donation["description"] or ""
    image_url = f"{BASE_URL}/api/photo/{donation['photo_file_id']}"
    page_url = f"{BASE_URL}/d/{donation_id}"
    bot_username = request.app.get("bot_username")
    bot_url = f"https://t.me/{bot_username}" if bot_username else BASE_URL

    html = f"""<!doctype html>
<html lang="uz">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta property="og:type" content="article">
<meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(description)}">
<meta property="og:image" content="{escape(image_url)}">
<meta property="og:url" content="{escape(page_url)}">
<meta name="twitter:card" content="summary_large_image">
<title>{escape(title)}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; background:#F2F3F5; margin:0; padding:24px; text-align:center; color:#111; }}
  img {{ max-width: 320px; width: 100%; border-radius: 16px; margin-top: 16px; }}
  h1 {{ font-size: 18px; margin: 0; }}
  p {{ color:#555; font-size: 15px; }}
  a.btn {{ display:inline-block; margin-top: 20px; background:#2AABEE; color:#fff; text-decoration:none; padding: 12px 28px; border-radius: 24px; font-weight:600; }}
</style>
</head>
<body>
  <h1>{escape(title)}</h1>
  <p>{escape(description)}</p>
  <img src="{escape(image_url)}" alt="">
  <div><a class="btn" href="{escape(bot_url)}">Botni ochish</a></div>
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
    app.router.add_get("/api/categories", api_categories)
    app.router.add_get("/api/donations", api_donations)
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
