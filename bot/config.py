import os
import time

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

_base_url = (os.getenv("WEBAPP_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")
_deploy_version = os.getenv("RENDER_GIT_COMMIT", "")[:8] or str(int(time.time()))
BASE_URL = _base_url
WEBAPP_URL = f"{_base_url}/webapp?v={_deploy_version}" if _base_url else None

# @BotFather'da /newapp orqali ro'yxatdan o'tkazilgan Mini App'ning qisqa nomi
# (https://t.me/<bot>/<MINI_APP_SHORT_NAME>?startapp=... havolasi shu orqali
# botning chatiga kirmasdan, to'g'ridan-to'g'ri ilovaning o'ziga olib boradi).
MINI_APP_SHORT_NAME = os.getenv("MINI_APP_SHORT_NAME", "app")

# Joylangan ehsonlar e'lon qilinadigan kanal. Bot o'sha kanalda admin
# bo'lishi kerak ("Post messages" huquqi bilan). Bo'sh qoldirilsa
# kanalga e'lon qilish butunlay o'chiriladi.
CHANNEL_ID = os.getenv("CHANNEL_ID", "@ehsonli_qollar").strip()

# Reklama to'lovi (hozircha kartaga o'tkazma + chek, admin qo'lda tasdiqlaydi).
# Karta ma'lumotlari kodda saqlanmaydi — hosting Environment Variables'da:
#   AD_CARD_NUMBER=8600...   AD_CARD_HOLDER=ISM FAMILIYA
#   AD_ADMIN_IDS=123456789,987654321  (chekni tasdiqlovchi adminlarning
#   Telegram ID'lari; ular botga /start bosgan bo'lishi kerak)
AD_CARD_NUMBER = "".join(ch for ch in os.getenv("AD_CARD_NUMBER", "") if ch.isdigit())
AD_CARD_HOLDER = os.getenv("AD_CARD_HOLDER", "").strip()
AD_ADMIN_IDS = [
    int(part) for part in os.getenv("AD_ADMIN_IDS", "").replace(" ", "").split(",")
    if part.lstrip("-").isdigit()
]

# Instagram rasmiy API (Business Discovery): reklama beruvchining Instagram
# Business/Creator profili (ism, bio, rasm) instagram.com'ni bloklamasdan
# olinadi. Ikkalasi ham bo'lmasa — o'chiq.
#   IG_GRAPH_TOKEN=uzoq muddatli Facebook user/page access token
#   IG_BUSINESS_ID=sizning Instagram Business akkauntingiz ID'si (1784...)
IG_GRAPH_TOKEN = os.getenv("IG_GRAPH_TOKEN", "").strip()
IG_BUSINESS_ID = os.getenv("IG_BUSINESS_ID", "").strip()

# Instagram so'rovlari uchun proksi(lar) — server IP'si cheklansa ham ishlashi
# uchun (uy/mobil internet proksisi eng yaxshi). Vergul bilan bir nechta:
#   INSTAGRAM_PROXY=http://user:pass@1.2.3.4:8080,http://5.6.7.8:3128
INSTAGRAM_PROXIES = [p.strip() for p in os.getenv("INSTAGRAM_PROXY", "").split(",") if p.strip()]

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
