import os

from aiohttp import web

from bot.webpanel import dashboard_handler


async def _health(request: web.Request) -> web.Response:
    return web.Response(text="Ehson bot ishlayapti ✅")


async def start_webserver() -> None:
    """Bepul hosting (masalan Render) uchun engil HTTP server.

    Bunday xizmatlar processni "web xizmat" sifatida ko'radi va $PORT
    portini tinglashni talab qiladi; aks holda ishga tushmaydi yoki
    uxlab qoladi. Shu server ustiga /admin — statistika paneli ham
    qo'shilgan.
    """
    app = web.Application()
    app.router.add_get("/", _health)
    app.router.add_get("/admin", dashboard_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
