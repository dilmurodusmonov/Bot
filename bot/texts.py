LANGUAGES = ("uz", "ru", "en")

CATEGORIES = {
    "clothes": {"uz": "👕 Kiyim-kechaklar", "ru": "👕 Одежда", "en": "👕 Clothes"},
    "shoes": {"uz": "👟 Oyoq kiyimlar", "ru": "👟 Обувь", "en": "👟 Shoes"},
    "household": {"uz": "🏠 Uy-ro'zg'or buyumlari", "ru": "🏠 Хозтовары", "en": "🏠 Household items"},
    "toys": {"uz": "🧸 O'yinchoqlar", "ru": "🧸 Игрушки", "en": "🧸 Toys"},
    "books": {"uz": "📚 Kitoblar", "ru": "📚 Книги", "en": "📚 Books"},
    "appliances": {"uz": "🔌 Maishiy texnikalar", "ru": "🔌 Бытовая техника", "en": "🔌 Home appliances"},
}

STATUS_LABELS = {
    "available": {"uz": "⏳ Kutilmoqda", "ru": "⏳ Ожидает", "en": "⏳ Waiting"},
    "reserved": {"uz": "🤝 Band qilingan", "ru": "🤝 Забронировано", "en": "🤝 Reserved"},
    "shipped": {"uz": "🚚 Yo'lda", "ru": "🚚 В пути", "en": "🚚 On the way"},
    "received": {"uz": "✅ Yetib bordi", "ru": "✅ Доставлено", "en": "✅ Delivered"},
}

TEXTS = {
    "uz": {
        "choose_language": "🌐 Tilni tanlang:",
        "language_set": "✅ Til o'zbekcha qilib o'rnatildi.",
        "choose_role": "Assalomu alaykum! Ehson ulashish botiga xush kelibsiz.\n\nIltimos, o'z statusingizni tanlang:",
        "role_donor": "🫴 Saxiy",
        "role_needy": "🤲 Muhtoj",
        "welcome_back": "Xush kelibsiz!",
        "open_app_hint": "📱 Barcha amallar (ehson qo'shish, ko'rish, kabinet) pastdagi menyu tugmasi — \"Kabinet\" orqali ochiladigan ilova ichida bajariladi.\n\nBu yerda esa faqat muhim yangiliklar va bildirishnomalar yuboriladi.",
        "donation_added": "✅ Ehsoningiz muvaffaqiyatli joylandi! Rahmat, savobli ish qilyapsiz.",
        "new_reservation_for_donor": (
            "🔔 Ehsoningizga yangi so'rov!\n\n"
            "Bo'lim: {category}\n"
            "Ehson: {description}\n\n"
            "Muhtoj ma'lumotlari:\n"
            "👤 {full_name}\n"
            "📍 {address}\n"
            "📞 {phone}\n\n"
            "Iltimos, ehsonni ko'rsatilgan manzilga yaqin kuryerlik orqali yuboring va \"Kabinet\" ilovasi orqali pochta chekini yuklang."
        ),
        "shipped_saved_donor": "✅ Rahmat! Ehson yo'lga chiqqanligi tasdiqlandi va Muhtojga xabar berildi.",
        "shipped_notify_needy": (
            "📦 Xushxabar! Sizning ehsoningiz yo'lga chiqdi.\n\n"
            "Pochta cheki quyida biriktirilgan. Ehson qo'lingizga tegishi bilan \"Kabinet\" ilovasida qabul qilganingizni tasdiqlang."
        ),
        "received_notify_donor": (
            "🎉 Ehsoningiz muvaffaqiyatli yetib bordi!\n\n"
            "Muhtojning duosi/minnatdorchiligi:\n\"{dua_text}\""
        ),
        "unknown_command": "Iltimos, \"Kabinet\" ilovasidan foydalaning.",
    },
    "ru": {
        "choose_language": "🌐 Выберите язык:",
        "language_set": "✅ Язык изменён на русский.",
        "choose_role": "Здравствуйте! Добро пожаловать в бот пожертвований.\n\nПожалуйста, выберите свой статус:",
        "role_donor": "🫴 Благотворитель",
        "role_needy": "🤲 Нуждающийся",
        "welcome_back": "С возвращением!",
        "open_app_hint": "📱 Все действия (добавление, просмотр, кабинет) выполняются внутри приложения, которое открывается кнопкой меню — \"Kabinet\".\n\nЗдесь же вы будете получать только важные уведомления.",
        "donation_added": "✅ Ваше пожертвование успешно добавлено! Спасибо за доброе дело.",
        "new_reservation_for_donor": (
            "🔔 Новая заявка на ваше пожертвование!\n\n"
            "Раздел: {category}\n"
            "Пожертвование: {description}\n\n"
            "Данные нуждающегося:\n"
            "👤 {full_name}\n"
            "📍 {address}\n"
            "📞 {phone}\n\n"
            "Пожалуйста, отправьте пожертвование по указанному адресу через ближайшую курьерскую службу и загрузите чек в приложении \"Kabinet\"."
        ),
        "shipped_saved_donor": "✅ Спасибо! Подтверждена отправка пожертвования, нуждающийся уведомлён.",
        "shipped_notify_needy": (
            "📦 Хорошая новость! Ваше пожертвование в пути.\n\n"
            "Почтовый чек прикреплён ниже. Когда получите посылку, подтвердите получение в приложении \"Kabinet\"."
        ),
        "received_notify_donor": (
            "🎉 Ваше пожертвование успешно доставлено!\n\n"
            "Слова благодарности от нуждающегося:\n\"{dua_text}\""
        ),
        "unknown_command": "Пожалуйста, используйте приложение \"Kabinet\".",
    },
    "en": {
        "choose_language": "🌐 Choose your language:",
        "language_set": "✅ Language set to English.",
        "choose_role": "Hello! Welcome to the Charity Sharing bot.\n\nPlease choose your status:",
        "role_donor": "🫴 Donor",
        "role_needy": "🤲 In need",
        "welcome_back": "Welcome back!",
        "open_app_hint": "📱 All actions (adding, browsing, your cabinet) happen inside the app opened via the \"Kabinet\" menu button.\n\nHere in chat you'll only receive important notifications.",
        "donation_added": "✅ Your donation has been posted successfully! Thank you for your kindness.",
        "new_reservation_for_donor": (
            "🔔 New request for your donation!\n\n"
            "Category: {category}\n"
            "Donation: {description}\n\n"
            "Recipient details:\n"
            "👤 {full_name}\n"
            "📍 {address}\n"
            "📞 {phone}\n\n"
            "Please ship the donation to the given address via a nearby courier and upload the receipt in the \"Kabinet\" app."
        ),
        "shipped_saved_donor": "✅ Thank you! Shipment confirmed and the recipient has been notified.",
        "shipped_notify_needy": (
            "📦 Good news! Your donation is on the way.\n\n"
            "The shipping receipt is attached below. Confirm receipt in the \"Kabinet\" app once you get the package."
        ),
        "received_notify_donor": (
            "🎉 Your donation was successfully delivered!\n\n"
            "Words of thanks from the recipient:\n\"{dua_text}\""
        ),
        "unknown_command": "Please use the \"Kabinet\" app.",
    },
}


def t(lang: str, key: str, **kwargs) -> str:
    lang = lang if lang in TEXTS else "uz"
    template = TEXTS[lang].get(key) or TEXTS["uz"].get(key, key)
    return template.format(**kwargs) if kwargs else template


def category_name(category: str, lang: str) -> str:
    lang = lang if lang in LANGUAGES else "uz"
    return CATEGORIES.get(category, {}).get(lang, category)


def status_label(status: str, lang: str) -> str:
    lang = lang if lang in LANGUAGES else "uz"
    return STATUS_LABELS.get(status, {}).get(lang, status)
