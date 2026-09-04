# Ehson — Telegram bot

"Saxiy" (xayr-ehson qiluvchi) va "Muhtoj" (ehsonga muhtoj) foydalanuvchilarni
bog'lovchi Telegram bot. Python + [aiogram 3](https://docs.aiogram.dev/) va
PostgreSQL (asyncpg) asosida qurilgan, 3 tilni qo'llab-quvvatlaydi: o'zbek,
rus, ingliz.

## Ishlash oqimi

1. Foydalanuvchi tilni va statusini (Saxiy / Muhtoj) tanlaydi.
2. **Saxiy** ehson bo'limini (kiyim-kechak, kitoblar, oyoq kiyim, uy-ro'zg'or
   buyumlari, o'yinchoqlar) tanlab, rasm va tavsif bilan ehson joylaydi.
3. **Muhtoj** bo'limlarni ko'rib, kerakli ehsonni tanlaydi, "Qabul qilish"ni
   bosib ism-familiya, manzil va telefon raqamini kiritadi.
4. Saxiyga Muhtojning ma'lumotlari yuboriladi. Saxiy ehsonni kuryerlik orqali
   jo'natib, pochta chekining rasmini botga yuklaydi.
5. Muhtojga chek rasmi va "Qabul qildim" tugmasi yuboriladi. Qabul qilingach,
   Muhtoj duo/minnatdorchilik yozadi.
6. Saxiyga Muhtojning duosi/minnatdorchiligi yetkaziladi — shu bilan ehson
   yetib borganiga ishonch hosil qilinadi.

## Ma'lumotlar bazasi (bepul, doimiy PostgreSQL — Neon.tech)

Bot ma'lumotlarni (foydalanuvchilar, ehsonlar, so'rovlar) saqlash uchun
PostgreSQL talab qiladi. [Neon.tech](https://neon.tech) bepul va doimiy
tarifni taklif qiladi (Render'ning bepul tarifidagi vaqtinchalik diskdan
farqli o'laroq, ma'lumotlar qayta deploy qilinganda ham yo'qolmaydi):

1. [neon.tech](https://neon.tech) saytida bepul ro'yxatdan o'ting.
2. Yangi loyiha (**"New Project"**) yarating — nomini xohlagancha qo'ying
   (masalan `ehson-bot`).
3. Loyiha yaratilgach, **"Connection string"** (yoki "Connection details")
   bo'limidan to'liq ulanish manzilini nusxalang — u
   `postgresql://user:password@host/dbname?sslmode=require` ko'rinishida
   bo'ladi.
4. Shu manzilni `.env` fayliga (yoki hosting'ning Environment Variables
   bo'limiga) `DATABASE_URL` sifatida qo'shing.

Jadval (schema) botni birinchi marta ishga tushirganda avtomatik
yaratiladi — qo'lda SQL yozish shart emas.

## O'rnatish

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# .env faylini oching:
# - BOT_TOKEN'ni @BotFather'dan olingan token bilan almashtiring
# - DATABASE_URL'ni Neon'dan olgan ulanish manzili bilan almashtiring
```

## Ishga tushirish

```bash
python run.py
```

Bot polling rejimida ishga tushadi, ma'lumotlar `DATABASE_URL`
ko'rsatgan PostgreSQL bazasida saqlanadi.

## Loyihaning tuzilishi

```
bot/
├── config.py       # .env dan sozlamalarni o'qish
├── database.py     # PostgreSQL bilan ishlash (async, asyncpg)
├── texts.py        # 3 tildagi matnlar, bo'lim va status nomlari
├── states.py       # FSM holatlari
├── keyboards.py    # Inline/reply tugmalar
├── utils.py        # Yordamchi funksiyalar
├── keepalive.py    # Bepul hosting uchun mini health-check server
├── webpanel.py     # /admin statistika paneli (login/parol bilan himoyalangan)
├── webapp_auth.py  # Telegram Mini App initData'ni tekshirish (HMAC)
├── webapp_api.py   # Mini App uchun /api/* REST endpointlari
├── static/webapp/  # Mini App'ning frontend fayli (index.html)
└── handlers/
    ├── start.py    # Til, rol tanlash, asosiy menyu
    ├── donor.py    # Saxiy oqimi: ehson qo'shish, yuborish
    ├── needy.py    # Muhtoj oqimi: ehson tanlash, qabul qilish
    └── webapp.py   # Mini App'dan kelgan ma'lumotni qabul qilish
run.py              # Botni ishga tushirish nuqtasi
```

## Bepul 24/7 hostga qo'yish (Render.com)

Botni doimiy ishlaydigan qilib qo'yish uchun kompyuter shart emas —
Render.com'ning bepul tarifidan foydalanish mumkin.

1. [render.com](https://render.com) saytida ro'yxatdan o'ting (GitHub
   akkountingiz bilan kiring — shunda repolaringiz avtomatik ko'rinadi).
2. Dashboard'da **"New +"** → **"Web Service"** ni tanlang.
3. Ushbu GitHub repoziyoriyani ulang (`dilmurodusmonov/Bot`), branch —
   `main` (yoki PR merge qilingandan keyin shu branch).
4. Quyidagi maydonlarni to'ldiring:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python run.py`
   - **Instance Type**: `Free`
5. **Environment Variables** bo'limida qo'shing:
   - `BOT_TOKEN` — BotFather'dan olingan tokeningiz
   - `DATABASE_URL` — Neon'dan olingan PostgreSQL ulanish manzili (yuqoridagi
     "Ma'lumotlar bazasi" bo'limiga qarang)

   `PORT`ni Render o'zi avtomatik beradi — qo'shish shart emas.
6. **"Create Web Service"** ni bosing — bir necha daqiqada bot deploy bo'ladi.

Render'ning bepul tarifi 15 daqiqa trafik bo'lmasa xizmatni "uxlatib"
qo'yadi. Buning oldini olish uchun:

7. [uptimerobot.com](https://uptimerobot.com) da bepul akkount oching.
8. **"Add New Monitor"** → **HTTP(s)** → Render bergan URL manzilingizni
   kiriting (masalan `https://ehson-bot.onrender.com`) → tekshirish
   oralig'ini **5 daqiqa** qilib belgilang.

Shu bilan bot 24/7 ishlab turadi, kompyuteringiz yoqilgan-o'chganiga
bog'liq bo'lmaydi.

## Admin panel (statistika)

Bot bilan bir xil manzilda `/admin` sahifasi mavjud — umumiy statistikani
(foydalanuvchilar, ehsonlar, status va bo'lim bo'yicha taqsimot, oxirgi
ehsonlar) ko'rsatadi. Login/parol bilan himoyalangan.

**Sozlash:**

1. `.env` fayliga (yoki Render'ning Environment Variables bo'limiga) qo'shing:
   - `ADMIN_USERNAME` — login (masalan `admin`)
   - `ADMIN_PASSWORD` — o'zingiz o'ylab topgan kuchli parol
2. Brauzerda `https://<sizning-render-manzilingiz>/admin` ni oching —
   login/parol so'raladi.

`ADMIN_PASSWORD` o'rnatilmagan bo'lsa, `/admin` sahifasi hech kimga
ochilmaydi (xavfsiz standart holat).

## Mini App (kabinet)

Botning asosiy menyusida **"Kabinet"** tugmasi (Telegram Menu Button)
orqali ochiladigan to'liq maxsus veb-interfeys (Telegram Mini App)
mavjud: til/rol tanlash, ehsonlarni chiroyli kartalar bilan ko'rish,
Saxiy/Muhtoj kabineti, band qilish, rasm yuklash (ehson surati, pochta
cheki) va "qabul qildim + duo" formalari — **barcha amallar shu yerda**,
chatga chiqishning hojati yo'q.

Bot chati endi faqat bildirishnomalar uchun ishlatiladi: yangi so'rov,
ehson yo'lga chiqqanligi va yetib borganligi haqidagi xabarlar shu yerga
keladi, amallarning o'zi esa Mini App ichida bajariladi.

**Sozlash:** hech narsa qilish shart emas — `WEBAPP_URL` Render'da
avtomatik aniqlanadi (`RENDER_EXTERNAL_URL` orqali). Faqat Render deploy
qilingandan keyin "🏠 Kabinet" tugmasi paydo bo'ladi. Boshqa hostingda
ishlatilsa, `WEBAPP_URL` environment variable'ni qo'lda kiriting (masalan
`https://sizning-domeningiz.com`) — Telegram Mini App uchun HTTPS shart.
