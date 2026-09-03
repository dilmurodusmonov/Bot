import os

from aiohttp import web


async def _health(request: web.Request) -> web.Response:
    return web.Response(text="Ehson bot ishlayapti ✅")


async def start_webserver() -> None:
    """Bepul hosting (masalan Render) uchun engil HTTP server.

    Bunday xizmatlar processni "web xizmat" sifatida ko'radi va $PORT
    portini tinglashni talab qiladi; aks holda ishga tushmaydi yoki
    uxlab qoladi.
    """
    app = web.Application()
    app.router.add_get("/", _health)

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
