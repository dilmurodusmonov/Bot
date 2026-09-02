from bot.database import get_user
from bot.texts import LANGUAGES, TEXTS


async def get_lang(telegram_id: int) -> str:
    user = await get_user(telegram_id)
    if user and user.get("language"):
        return user["language"]
    return "uz"


def button_variants(key: str) -> set[str]:
    return {TEXTS[lang][key] for lang in LANGUAGES if key in TEXTS[lang]}
