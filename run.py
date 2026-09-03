import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import ADMIN_PASSWORD, ADMIN_USERNAME, BOT_TOKEN
from bot.database import init_db
from bot.handlers import donor, needy, start
from bot.keepalive import start_webserver


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logging.info(
        "ADMIN PANEL DEBUG: ADMIN_USERNAME=%r ADMIN_PASSWORD=%r",
        ADMIN_USERNAME,
        ADMIN_PASSWORD,
    )
    await init_db()
    await start_webserver()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start.router)
    dp.include_router(donor.router)
    dp.include_router(needy.router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
