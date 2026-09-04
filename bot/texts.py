LANGUAGES = ("uz", "ru", "en")

CATEGORIES = {
    "clothes": {"uz": "👕 Kiyim-kechaklar", "ru": "👕 Одежда", "en": "👕 Clothes"},
    "books": {"uz": "📚 Kitoblar", "ru": "📚 Книги", "en": "📚 Books"},
    "shoes": {"uz": "👟 Oyoq kiyimlar", "ru": "👟 Обувь", "en": "👟 Shoes"},
    "household": {"uz": "🏠 Uy-ro'zg'or buyumlari", "ru": "🏠 Хозтовары", "en": "🏠 Household items"},
    "toys": {"uz": "🧸 O'yinchoqlar", "ru": "🧸 Игрушки", "en": "🧸 Toys"},
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
        "role_donor": "🤲 Saxiy",
        "role_needy": "🙏 Muhtoj",
        "welcome_back": "Xush kelibsiz!",
        "btn_add_donation": "➕ Ehson qo'shish",
        "btn_my_donations": "📦 Mening ehsonlarim",
        "btn_browse_donations": "🔍 Ehsonlarni ko'rish",
        "btn_my_requests": "📋 Mening so'rovlarim",
        "btn_change_language": "🌐 Til",
        "btn_change_role": "🔄 Rolni almashtirish",
        "btn_kabinet": "🏠 Kabinet",
        "menu_donor_hint": "Saxiy sifatida ishlayapsiz. Quyidagi menyudan foydalaning:",
        "menu_needy_hint": "Muhtoj sifatida ishlayapsiz. Quyidagi menyudan foydalaning:",
        "choose_category": "Ehson bo'limini tanlang:",
        "ask_photo": "Ehsonning rasmini yuboring:",
        "ask_photo_retry": "Iltimos, rasm (foto) yuboring.",
        "ask_description": "Endi ehson haqida qisqacha ma'lumot (xarakteristikasi) yozing:",
        "donation_added": "✅ Ehsoningiz muvaffaqiyatli joylandi! Rahmat, savobli ish qilyapsiz.",
        "no_donations_in_category": "Ushbu bo'limda hozircha mavjud ehsonlar yo'q.",
        "donation_card": "{category}\n\n{description}",
        "btn_reserve": "✅ Qabul qilish",
        "already_reserved": "😔 Afsuski, bu ehson allaqachon boshqa birov tomonidan band qilingan.",
        "ask_full_name": "Ism va familiyangizni kiriting:",
        "ask_address": "Yashash manzilingizni to'liq kiriting:",
        "ask_phone": "Telefon raqamingizni kiriting (masalan: +998901234567):",
        "reservation_done_needy": "✅ So'rovingiz qabul qilindi! Saxiyga ma'lumotlaringiz yuborildi. Ehson yo'lga chiqishi bilan sizga xabar beramiz.",
        "new_reservation_for_donor": (
            "🔔 Ehsoningizga yangi so'rov!\n\n"
            "Bo'lim: {category}\n"
            "Ehson: {description}\n\n"
            "Muhtoj ma'lumotlari:\n"
            "👤 {full_name}\n"
            "📍 {address}\n"
            "📞 {phone}\n\n"
            "Iltimos, ehsonni ko'rsatilgan manzilga yaqin kuryerlik orqali yuboring va pastdagi tugma orqali pochta chekini yuklang."
        ),
        "btn_mark_shipped": "📦 Yuborildi (chek yuklash)",
        "ask_receipt_photo": "Pochta chekining rasmini yuboring (agar kerak bo'lsa, rasmga izoh sifatida qaysi kuryerlik ekanini yozing):",
        "shipped_saved_donor": "✅ Rahmat! Ehson yo'lga chiqqanligi tasdiqlandi va Muhtojga xabar berildi.",
        "shipped_notify_needy": (
            "📦 Xushxabar! Sizning ehsoningiz yo'lga chiqdi.\n\n"
            "Pochta cheki quyida biriktirilgan. Ehson qo'lingizga tegishi bilan pastdagi tugmani bosing."
        ),
        "btn_confirm_received": "✅ Qabul qildim",
        "ask_dua": "Ehsonni qabul qilganingizni tasdiqlaysiz. Endi Saxiyga bir og'iz duo/minnatdorchilik so'zlaringizni yozib qoldiring:",
        "received_confirmed_needy": "✅ Rahmat! Sizning javobingiz Saxiyga yetkazildi. Ehson yetib borganini tasdiqladingiz.",
        "received_notify_donor": (
            "🎉 Ehsoningiz muvaffaqiyatli yetib bordi!\n\n"
            "Muhtojning duosi/minnatdorchiligi:\n\"{dua_text}\""
        ),
        "my_donations_empty": "Sizda hali joylangan ehsonlar yo'q.",
        "my_requests_empty": "Sizda hali so'rovlar yo'q. Ehsonlarni ko'rish uchun menyudan foydalaning.",
        "reservation_info_for_donor_card": "\n\n👤 {full_name}\n📍 {address}\n📞 {phone}",
        "dua_info_card": "\n\n💬 \"{dua_text}\"",
        "waiting_shipment_needy": "Ehson hali yo'lga chiqarilmagan. Iltimos, kuting.",
        "cancel_hint": "Amalni bekor qilish uchun /cancel buyrug'ini yuboring.",
        "cancelled": "❌ Amal bekor qilindi.",
        "unknown_command": "Iltimos, menyudagi tugmalardan foydalaning.",
    },
    "ru": {
        "choose_language": "🌐 Выберите язык:",
        "language_set": "✅ Язык изменён на русский.",
        "choose_role": "Здравствуйте! Добро пожаловать в бот пожертвований.\n\nПожалуйста, выберите свой статус:",
        "role_donor": "🤲 Благотворитель",
        "role_needy": "🙏 Нуждающийся",
        "welcome_back": "С возвращением!",
        "btn_add_donation": "➕ Добавить пожертвование",
        "btn_my_donations": "📦 Мои пожертвования",
        "btn_browse_donations": "🔍 Посмотреть пожертвования",
        "btn_my_requests": "📋 Мои заявки",
        "btn_change_language": "🌐 Язык",
        "btn_change_role": "🔄 Сменить статус",
        "btn_kabinet": "🏠 Кабинет",
        "menu_donor_hint": "Вы работаете как Благотворитель. Используйте меню ниже:",
        "menu_needy_hint": "Вы работаете как Нуждающийся. Используйте меню ниже:",
        "choose_category": "Выберите раздел пожертвования:",
        "ask_photo": "Отправьте фото пожертвования:",
        "ask_photo_retry": "Пожалуйста, отправьте фотографию.",
        "ask_description": "Теперь напишите краткое описание (характеристику) пожертвования:",
        "donation_added": "✅ Ваше пожертвование успешно добавлено! Спасибо за доброе дело.",
        "no_donations_in_category": "В этом разделе пока нет доступных пожертвований.",
        "donation_card": "{category}\n\n{description}",
        "btn_reserve": "✅ Забрать",
        "already_reserved": "😔 К сожалению, это пожертвование уже забронировано другим человеком.",
        "ask_full_name": "Введите ваше полное имя:",
        "ask_address": "Введите ваш полный адрес проживания:",
        "ask_phone": "Введите ваш номер телефона (например: +998901234567):",
        "reservation_done_needy": "✅ Ваша заявка принята! Ваши данные отправлены Благотворителю. Мы сообщим вам, когда пожертвование будет отправлено.",
        "new_reservation_for_donor": (
            "🔔 Новая заявка на ваше пожертвование!\n\n"
            "Раздел: {category}\n"
            "Пожертвование: {description}\n\n"
            "Данные нуждающегося:\n"
            "👤 {full_name}\n"
            "📍 {address}\n"
            "📞 {phone}\n\n"
            "Пожалуйста, отправьте пожертвование по указанному адресу через ближайшую курьерскую службу и загрузите чек кнопкой ниже."
        ),
        "btn_mark_shipped": "📦 Отправлено (загрузить чек)",
        "ask_receipt_photo": "Отправьте фото почтового чека (при необходимости укажите в подписи название курьерской службы):",
        "shipped_saved_donor": "✅ Спасибо! Подтверждена отправка пожертвования, нуждающийся уведомлён.",
        "shipped_notify_needy": (
            "📦 Хорошая новость! Ваше пожертвование в пути.\n\n"
            "Почтовый чек прикреплён ниже. Когда получите посылку, нажмите кнопку ниже."
        ),
        "btn_confirm_received": "✅ Я получил(а)",
        "ask_dua": "Вы подтверждаете получение пожертвования. Напишите несколько слов благодарности/пожелания для Благотворителя:",
        "received_confirmed_needy": "✅ Спасибо! Ваш ответ передан Благотворителю. Вы подтвердили получение пожертвования.",
        "received_notify_donor": (
            "🎉 Ваше пожертвование успешно доставлено!\n\n"
            "Слова благодарности от нуждающегося:\n\"{dua_text}\""
        ),
        "my_donations_empty": "У вас пока нет добавленных пожертвований.",
        "my_requests_empty": "У вас пока нет заявок. Используйте меню, чтобы посмотреть пожертвования.",
        "reservation_info_for_donor_card": "\n\n👤 {full_name}\n📍 {address}\n📞 {phone}",
        "dua_info_card": "\n\n💬 \"{dua_text}\"",
        "waiting_shipment_needy": "Пожертвование ещё не отправлено. Пожалуйста, подождите.",
        "cancel_hint": "Чтобы отменить действие, отправьте /cancel.",
        "cancelled": "❌ Действие отменено.",
        "unknown_command": "Пожалуйста, используйте кнопки меню.",
    },
    "en": {
        "choose_language": "🌐 Choose your language:",
        "language_set": "✅ Language set to English.",
        "choose_role": "Hello! Welcome to the Charity Sharing bot.\n\nPlease choose your status:",
        "role_donor": "🤲 Donor",
        "role_needy": "🙏 In need",
        "welcome_back": "Welcome back!",
        "btn_add_donation": "➕ Add donation",
        "btn_my_donations": "📦 My donations",
        "btn_browse_donations": "🔍 Browse donations",
        "btn_my_requests": "📋 My requests",
        "btn_change_language": "🌐 Language",
        "btn_change_role": "🔄 Switch status",
        "btn_kabinet": "🏠 Cabinet",
        "menu_donor_hint": "You are working as a Donor. Use the menu below:",
        "menu_needy_hint": "You are working as a person In need. Use the menu below:",
        "choose_category": "Choose a donation category:",
        "ask_photo": "Send a photo of the donation:",
        "ask_photo_retry": "Please send a photo.",
        "ask_description": "Now write a short description (characteristics) of the donation:",
        "donation_added": "✅ Your donation has been posted successfully! Thank you for your kindness.",
        "no_donations_in_category": "There are no available donations in this category yet.",
        "donation_card": "{category}\n\n{description}",
        "btn_reserve": "✅ Take it",
        "already_reserved": "😔 Sorry, this donation has already been reserved by someone else.",
        "ask_full_name": "Enter your full name:",
        "ask_address": "Enter your full home address:",
        "ask_phone": "Enter your phone number (e.g. +998901234567):",
        "reservation_done_needy": "✅ Your request has been accepted! Your details were sent to the Donor. We'll notify you once the donation is shipped.",
        "new_reservation_for_donor": (
            "🔔 New request for your donation!\n\n"
            "Category: {category}\n"
            "Donation: {description}\n\n"
            "Recipient details:\n"
            "👤 {full_name}\n"
            "📍 {address}\n"
            "📞 {phone}\n\n"
            "Please ship the donation to the given address via a nearby courier and upload the receipt using the button below."
        ),
        "btn_mark_shipped": "📦 Shipped (upload receipt)",
        "ask_receipt_photo": "Send a photo of the shipping receipt (optionally add the courier name as a caption):",
        "shipped_saved_donor": "✅ Thank you! Shipment confirmed and the recipient has been notified.",
        "shipped_notify_needy": (
            "📦 Good news! Your donation is on the way.\n\n"
            "The shipping receipt is attached below. Press the button below once you receive the package."
        ),
        "btn_confirm_received": "✅ I received it",
        "ask_dua": "You're confirming receipt of the donation. Please write a few words of thanks/blessing for the Donor:",
        "received_confirmed_needy": "✅ Thank you! Your message was delivered to the Donor. You confirmed receipt of the donation.",
        "received_notify_donor": (
            "🎉 Your donation was successfully delivered!\n\n"
            "Words of thanks from the recipient:\n\"{dua_text}\""
        ),
        "my_donations_empty": "You haven't posted any donations yet.",
        "my_requests_empty": "You don't have any requests yet. Use the menu to browse donations.",
        "reservation_info_for_donor_card": "\n\n👤 {full_name}\n📍 {address}\n📞 {phone}",
        "dua_info_card": "\n\n💬 \"{dua_text}\"",
        "waiting_shipment_needy": "The donation hasn't been shipped yet. Please wait.",
        "cancel_hint": "Send /cancel to cancel the current action.",
        "cancelled": "❌ Action cancelled.",
        "unknown_command": "Please use the menu buttons.",
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
