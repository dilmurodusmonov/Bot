import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

_base_url = (os.getenv("WEBAPP_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")
WEBAPP_URL = f"{_base_url}/webapp" if _base_url else None

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN topilmadi. .env faylini yarating (.env.example asosida) "
        "va BOT_TOKEN qiymatini kiriting."
    )

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL topilmadi. Postgres bazasi manzilini .env fayliga "
        "(yoki hosting Environment Variables bo'limiga) qo'shing."
    )
