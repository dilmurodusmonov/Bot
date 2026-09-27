import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import MenuButtonWebApp, WebAppInfo

from bot.config import BOT_TOKEN, SUPPORT_BOT_TOKENS, WEBAPP_URL
from bot.database import init_db
from bot import support
from bot.handlers import ads, start
from bot.keepalive import start_webserver
from bot.reminders import run_reminder_loop


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    await init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # ads birinchi: start.router'dagi umumiy matn javobi (fallback) /logo kabi
    # admin buyruqlarini tutib qolmasin.
    dp.include_router(ads.router)
    dp.include_router(start.router)

    await start_webserver(bot)

    await bot.delete_webhook(drop_pending_updates=True)

    if WEBAPP_URL:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Ehson App", web_app=WebAppInfo(url=WEBAPP_URL))
        )

    asyncio.create_task(run_reminder_loop(bot))

    # Aloqa botlari (ixtiyoriy, bir yoki bir nechta): shu jarayonda, alohida dispatcher bilan.
    support_task = None
    if SUPPORT_BOT_TOKENS:
        support_bots = [
            Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            for token in SUPPORT_BOT_TOKENS
        ]
        # Aloqa botidagi javoblar ostidagi "🤖 Ehson App" tugmasi asosiy
        # botning Mini App'ini ochadi — buning uchun asosiy bot nomi kerak.
        # support_bots — xabar barcha aloqa botlaridagi adminlarga boradi.
        support_dp = Dispatcher(
            main_bot_username=(await bot.get_me()).username,
            support_bots={b.id: b for b in support_bots},
        )
        support_dp.include_router(support.router)
        # Livegram kabi oldingi xizmat qo'ygan webhook olib tashlanadi —
        # aks holda xabarlar bizga kelmaydi.
        for support_bot in support_bots:
            await support_bot.delete_webhook(drop_pending_updates=False)
        support_task = asyncio.create_task(support_dp.start_polling(*support_bots, handle_signals=False))

    await dp.start_polling(bot)
    if support_task:
        support_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
