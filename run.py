import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import MenuButtonWebApp, WebAppInfo

from bot.config import BOT_TOKEN, WEBAPP_URL
from bot.database import init_db
from bot.handlers import donor, needy, start, webapp
from bot.keepalive import start_webserver


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    await init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start.router)
    dp.include_router(donor.router)
    dp.include_router(needy.router)
    dp.include_router(webapp.router)

    await start_webserver(bot)

    await bot.delete_webhook(drop_pending_updates=True)

    if WEBAPP_URL:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Kabinet", web_app=WebAppInfo(url=WEBAPP_URL))
        )

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
