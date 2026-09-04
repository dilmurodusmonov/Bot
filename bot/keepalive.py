import os
from pathlib import Path

from aiogram import Bot
from aiohttp import web

from bot.webapp_api import setup_api_routes
from bot.webpanel import dashboard_handler

WEBAPP_INDEX = Path(__file__).parent / "static" / "webapp" / "index.html"


async def _health(request: web.Request) -> web.Response:
    return web.Response(text="Ehson bot ishlayapti ✅")


async def _webapp_index(request: web.Request) -> web.Response:
    return web.FileResponse(WEBAPP_INDEX)


async def start_webserver(bot: Bot) -> None:
    """Bepul hosting (masalan Render) uchun engil HTTP server.

    Bunday xizmatlar processni "web xizmat" sifatida ko'radi va $PORT
    portini tinglashni talab qiladi; aks holda ishga tushmaydi yoki
    uxlab qoladi. Shu server ustiga /admin (statistika paneli) va
    /webapp + /api/* (Telegram Mini App) ham qo'shilgan.
    """
    app = web.Application(client_max_size=10 * 1024 * 1024)
    app["bot"] = bot
    app.router.add_get("/", _health)
    app.router.add_get("/admin", dashboard_handler)
    app.router.add_get("/webapp", _webapp_index)
    setup_api_routes(app)

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
