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
    bot_url = f"https://t.me/{bot_username}?start=d_{donation_id}" if bot_username else BASE_URL

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
        <span class="pill">{escape(status_emoji)} {escape(status_text)}</span>
        <div class="card-date">{escape(_format_date_uz(donation["created_at"]))}</div>
      </div>
    </div>
    <a class="btn" href="{escape(bot_url)}">Botni ochish</a>
  </div>
  <script>
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
