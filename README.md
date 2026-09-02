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
└── handlers/
    ├── start.py    # Til, rol tanlash, asosiy menyu
    ├── donor.py    # Saxiy oqimi: ehson qo'shish, yuborish
    └── needy.py    # Muhtoj oqimi: ehson tanlash, qabul qilish
run.py              # Botni ishga tushirish nuqtasi
```
