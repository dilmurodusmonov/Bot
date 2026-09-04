from bot.database import get_user


async def get_lang(telegram_id: int) -> str:
    user = await get_user(telegram_id)
    if user and user.get("language"):
        return user["language"]
    return "uz"
