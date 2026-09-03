import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "data/ehson.db")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN topilmadi. .env faylini yarating (.env.example asosida) "
        "va BOT_TOKEN qiymatini kiriting."
    )
