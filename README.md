# Ehson — Telegram bot

"Saxiy" (xayr-ehson qiluvchi) va "Muhtoj" (ehsonga muhtoj) foydalanuvchilarni
bog'lovchi Telegram bot. Python + [aiogram 3](https://docs.aiogram.dev/) va
SQLite (aiosqlite) asosida qurilgan, 3 tilni qo'llab-quvvatlaydi: o'zbek,
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

## O'rnatish

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# .env faylini oching va BOT_TOKEN qiymatini @BotFather'dan olingan token bilan almashtiring
```

## Ishga tushirish

```bash
python run.py
```

Bot polling rejimida ishga tushadi va ma'lumotlar `data/ehson.db` faylida
(SQLite) saqlanadi.

## Loyihaning tuzilishi

```
bot/
├── config.py       # .env dan sozlamalarni o'qish
├── database.py     # SQLite bilan ishlash (async)
├── texts.py        # 3 tildagi matnlar, bo'lim va status nomlari
├── states.py       # FSM holatlari
├── keyboards.py    # Inline/reply tugmalar
├── utils.py        # Yordamchi funksiyalar
├── keepalive.py    # Bepul hosting uchun mini health-check server
└── handlers/
    ├── start.py    # Til, rol tanlash, asosiy menyu
    ├── donor.py    # Saxiy oqimi: ehson qo'shish, yuborish
    └── needy.py    # Muhtoj oqimi: ehson tanlash, qabul qilish
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
5. **Environment Variables** bo'limida qo'shing: `BOT_TOKEN` = sizning
   tokeningiz (BotFather'dan olingan). `PORT`ni Render o'zi avtomatik beradi
   — qo'shish shart emas.
6. **"Create Web Service"** ni bosing — bir necha daqiqada bot deploy bo'ladi.

Render'ning bepul tarifi 15 daqiqa trafik bo'lmasa xizmatni "uxlatib"
qo'yadi. Buning oldini olish uchun:

7. [uptimerobot.com](https://uptimerobot.com) da bepul akkount oching.
8. **"Add New Monitor"** → **HTTP(s)** → Render bergan URL manzilingizni
   kiriting (masalan `https://ehson-bot.onrender.com`) → tekshirish
   oralig'ini **5 daqiqa** qilib belgilang.

Shu bilan bot 24/7 ishlab turadi, kompyuteringiz yoqilgan-o'chganiga
bog'liq bo'lmaydi.
