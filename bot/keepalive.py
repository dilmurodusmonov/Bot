import asyncio
import gzip
import hashlib
import logging
import os
from pathlib import Path
from typing import Optional

import aiohttp
from aiogram import Bot
from aiohttp import web

from bot.webapp_api import setup_api_routes
from bot.webpanel import dashboard_handler

WEBAPP_INDEX = Path(__file__).parent / "static" / "webapp" / "index.html"
# Mini App uchun statik fayllar (masalan, animatsion emoji .webp).
WEBAPP_ASSETS = Path(__file__).parent / "static" / "webapp" / "assets"


async def _health(request: web.Request) -> web.Response:
    return web.Response(text="Ehson bot ishlayapti ✅")


# index.html (~280 KB) har so'rovda diskdan o'qilib siqilmasdan yuborilardi.
# Endi fayl o'zgargandagina qayta o'qiladi, oldindan gzip qilinadi (~5 marta
# kichik) va ETag bilan: o'zgarmagan bo'lsa telefon 304 oladi (hech narsa
# qayta yuklanmaydi), yangilangan bo'lsa darhol yangisini oladi.
_index_cache: dict = {}


def _load_index() -> dict:
    mtime = WEBAPP_INDEX.stat().st_mtime
    if _index_cache.get("mtime") != mtime:
        raw = WEBAPP_INDEX.read_bytes()
        _index_cache.update(
            mtime=mtime,
            raw=raw,
            gz=gzip.compress(raw, compresslevel=9),
            etag='"' + hashlib.sha1(raw).hexdigest()[:16] + '"',
        )
    return _index_cache


async def _webapp_index(request: web.Request) -> web.Response:
    index = _load_index()
    headers = {"Cache-Control": "no-cache", "ETag": index["etag"], "Vary": "Accept-Encoding"}
    if request.headers.get("If-None-Match") == index["etag"]:
        return web.Response(status=304, headers=headers)
    if "gzip" in request.headers.get("Accept-Encoding", ""):
        headers["Content-Encoding"] = "gzip"
        body = index["gz"]
    else:
        body = index["raw"]
    return web.Response(body=body, content_type="text/html", charset="utf-8", headers=headers)


async def _webapp_asset(request: web.Request) -> web.Response:
    # Faqat assets/ papkasidagi fayl nomi (yo'l emas) qabul qilinadi.
    name = request.match_info["name"]
    path = WEBAPP_ASSETS / name
    if "/" in name or name.startswith(".") or not path.is_file():
        raise web.HTTPNotFound()
    content_type = {".webp": "image/webp", ".png": "image/png", ".gif": "image/gif"}.get(
        path.suffix.lower(), "application/octet-stream"
    )
    return web.Response(
        body=path.read_bytes(),
        content_type=content_type,
        headers={"Cache-Control": "public, max-age=604800"},
    )


@web.middleware
async def _compress_middleware(request: web.Request, handler):
    """JSON/HTML javoblarni gzip bilan siqadi (rasmlar va oldindan
    siqilgan index.html bundan mustasno) — sekin internetda tezroq."""
    response = await handler(request)
    if (
        isinstance(response, web.Response)
        and not response.headers.get("Content-Encoding")
        and response.status == 200
        and response.body is not None
        and len(response.body) > 1024
        and (response.content_type or "").startswith(("application/json", "text/"))
        and "gzip" in request.headers.get("Accept-Encoding", "")
    ):
        response.enable_compression()
    return response


async def _self_ping_loop(url: str) -> None:
    """Render bepul tarifida 15 daqiqa kiruvchi so'rov bo'lmasa server
    uxlaydi va keyingi ochilish 30-60 soniya kutadi. Har 10 daqiqada o'ziga
    so'rov yuborib, server doim "uyg'oq" turadi."""
    await asyncio.sleep(60)
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
        while True:
            try:
                async with session.get(url) as resp:
                    await resp.read()
            except Exception:
                logging.getLogger(__name__).debug("Self-ping muvaffaqiyatsiz", exc_info=True)
            await asyncio.sleep(600)


async def start_webserver(bot: Bot) -> None:
    """Bepul hosting (masalan Render) uchun engil HTTP server.

    Bunday xizmatlar processni "web xizmat" sifatida ko'radi va $PORT
    portini tinglashni talab qiladi; aks holda ishga tushmaydi yoki
    uxlab qoladi. Shu server ustiga /admin (statistika paneli) va
    /webapp + /api/* (Telegram Mini App) ham qo'shilgan.
    """
    app = web.Application(client_max_size=10 * 1024 * 1024, middlewares=[_compress_middleware])
    app["bot"] = bot
    me = await bot.get_me()
    app["bot_username"] = me.username
    app.router.add_get("/", _health)
    app.router.add_get("/admin", dashboard_handler)
    app.router.add_get("/webapp", _webapp_index)
    app.router.add_get("/webapp-assets/{name}", _webapp_asset)
    setup_api_routes(app)

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    external: Optional[str] = os.getenv("RENDER_EXTERNAL_URL")
    if external:
        app["self_ping_task"] = asyncio.create_task(_self_ping_loop(external.rstrip("/") + "/"))
