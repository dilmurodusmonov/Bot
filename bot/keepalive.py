import os
from pathlib import Path

from aiogram import Bot
from aiohttp import web

from bot.webapp_api import setup_api_routes
from bot.webpanel import dashboard_handler

WEBAPP_INDEX = Path(__file__).parent / "static" / "webapp" / "index.html"
# Mini App uchun statik fayllar (masalan, animatsion emoji .webp).
WEBAPP_ASSETS = Path(__file__).parent / "static" / "webapp" / "assets"


async def _health(request: web.Request) -> web.Response:
    return web.Response(text="Ehson bot ishlayapti ✅")


async def _webapp_index(request: web.Request) -> web.Response:
    html = WEBAPP_INDEX.read_text(encoding="utf-8")
    return web.Response(
        text=html,
        content_type="text/html",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


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


async def start_webserver(bot: Bot) -> None:
    """Bepul hosting (masalan Render) uchun engil HTTP server.

    Bunday xizmatlar processni "web xizmat" sifatida ko'radi va $PORT
    portini tinglashni talab qiladi; aks holda ishga tushmaydi yoki
    uxlab qoladi. Shu server ustiga /admin (statistika paneli) va
    /webapp + /api/* (Telegram Mini App) ham qo'shilgan.
    """
    app = web.Application(client_max_size=10 * 1024 * 1024)
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
