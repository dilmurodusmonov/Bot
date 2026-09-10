LANGUAGES = ("uz", "ru", "en", "kk", "tg", "ky", "tk")

CATEGORIES = {
    "clothes": {
        "uz": "👕 Kiyim-kechaklar", "ru": "👕 Одежда", "en": "👕 Clothes",
        "kk": "👕 Киім-кешек", "tg": "👕 Либос", "ky": "👕 Кийим-кечек", "tk": "👕 Egin-eşik",
    },
    "shoes": {
        "uz": "👟 Oyoq kiyimlar", "ru": "👟 Обувь", "en": "👟 Shoes",
        "kk": "👟 Аяқ киім", "tg": "👟 Пойафзол", "ky": "👟 Бут кийим", "tk": "👟 Aýakgap",
    },
    "household": {
        "uz": "🏠 Uy-ro'zg'or buyumlari", "ru": "🏠 Хозтовары", "en": "🏠 Household items",
        "kk": "🏠 Тұрмыстық заттар", "tg": "🏠 Лавозимоти рӯзгор", "ky": "🏠 Тиричилик буюмдары", "tk": "🏠 Öý-hojalyk goşlary",
    },
    "toys": {
        "uz": "🧸 O'yinchoqlar", "ru": "🧸 Игрушки", "en": "🧸 Toys",
        "kk": "🧸 Ойыншықтар", "tg": "🧸 Бозичаҳо", "ky": "🧸 Оюнчуктар", "tk": "🧸 Oýunjaklar",
    },
    "books": {
        "uz": "📚 Kitoblar", "ru": "📚 Книги", "en": "📚 Books",
        "kk": "📚 Кітаптар", "tg": "📚 Китобҳо", "ky": "📚 Китептер", "tk": "📚 Kitaplar",
    },
    "appliances": {
        "uz": "🔌 Maishiy texnikalar", "ru": "🔌 Бытовая техника", "en": "🔌 Home appliances",
        "kk": "🔌 Тұрмыстық техника", "tg": "🔌 Техникаи рӯзгор", "ky": "🔌 Тиричилик техникасы", "tk": "🔌 Öý-hojalyk tehnikasy",
    },
    "phones": {
        "uz": "📱 Telefon va aksessuarlar", "ru": "📱 Телефоны и аксессуары", "en": "📱 Phones and accessories",
        "kk": "📱 Телефон және аксессуарлар", "tg": "📱 Телефон ва аксессуарҳо", "ky": "📱 Телефон жана аксессуарлар", "tk": "📱 Telefon we aksessuarlar",
    },
}

STATUS_LABELS = {
    "available": {
        "uz": "⏳ Kutilmoqda", "ru": "⏳ Ожидает", "en": "⏳ Waiting",
        "kk": "⏳ Күтілуде", "tg": "⏳ Дар интизорӣ", "ky": "⏳ Күтүлүүдө", "tk": "⏳ Garaşylýar",
    },
    "reserved": {
        "uz": "🤝 Band qilingan", "ru": "🤝 Забронировано", "en": "🤝 Reserved",
        "kk": "🤝 Брондалған", "tg": "🤝 Банд карда шуд", "ky": "🤝 Брондолгон", "tk": "🤝 Bronlandy",
    },
    "shipped": {
        "uz": "🚚 Yo'lda", "ru": "🚚 В пути", "en": "🚚 On the way",
        "kk": "🚚 Жолда", "tg": "🚚 Дар роҳ", "ky": "🚚 Жолдо", "tk": "🚚 Ýolda",
    },
    "received": {
        "uz": "✅ Yetib bordi", "ru": "✅ Доставлено", "en": "✅ Delivered",
        "kk": "✅ Жетті", "tg": "✅ Расид", "ky": "✅ Жетти", "tk": "✅ Gowuşdy",
    },
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
        "open_app_button": "📱 Ilovani ochish",
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
        "reservation_cancelled_notify_donor": (
            "ℹ️ Muhtoj \"{description}\" ehsoningizga bo'lgan so'rovini bekor qildi.\n\n"
            "Ehson yana \"mavjud\" holatiga qaytarildi."
        ),
    },
    "ru": {
        "choose_language": "🌐 Выберите язык:",
        "language_set": "✅ Язык изменён на русский.",
        "choose_role": "Здравствуйте! Добро пожаловать в бот пожертвований.\n\nПожалуйста, выберите свой статус:",
        "role_donor": "🫴 Благотворитель",
        "role_needy": "🤲 Нуждающийся",
        "welcome_back": "С возвращением!",
        "open_app_hint": "📱 Все действия (добавление, просмотр, кабинет) выполняются внутри приложения, которое открывается кнопкой меню — \"Kabinet\".\n\nЗдесь же вы будете получать только важные уведомления.",
        "open_app_button": "📱 Открыть приложение",
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
        "reservation_cancelled_notify_donor": (
            "ℹ️ Нуждающийся отменил заявку на пожертвование \"{description}\".\n\n"
            "Пожертвование снова доступно."
        ),
    },
    "en": {
        "choose_language": "🌐 Choose your language:",
        "language_set": "✅ Language set to English.",
        "choose_role": "Hello! Welcome to the Charity Sharing bot.\n\nPlease choose your status:",
        "role_donor": "🫴 Donor",
        "role_needy": "🤲 In need",
        "welcome_back": "Welcome back!",
        "open_app_hint": "📱 All actions (adding, browsing, your cabinet) happen inside the app opened via the \"Kabinet\" menu button.\n\nHere in chat you'll only receive important notifications.",
        "open_app_button": "📱 Open the app",
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
        "reservation_cancelled_notify_donor": (
            "ℹ️ The recipient cancelled their request for \"{description}\".\n\n"
            "The donation is available again."
        ),
    },
    "kk": {
        "choose_language": "🌐 Тілді таңдаңыз:",
        "language_set": "✅ Тіл қазақ тіліне орнатылды.",
        "choose_role": "Ассалаумағалейкум! Қайыр үлестіру ботына қош келдіңіз.\n\nМәртебеңізді таңдаңыз:",
        "role_donor": "🫴 Қайырымды",
        "role_needy": "🤲 Мұқтаж",
        "welcome_back": "Қош келдіңіз!",
        "open_app_hint": "📱 Барлық әрекеттер (қайыр қосу, көру, кабинет) төмендегі мәзір түймесі — \"Kabinet\" арқылы ашылатын қосымша ішінде орындалады.\n\nМұнда тек маңызды жаңалықтар мен хабарландырулар жіберіледі.",
        "open_app_button": "📱 Қосымшаны ашу",
        "donation_added": "✅ Қайырыңыз сәтті жарияланды! Рахмет, игі іс жасап жатырсыз.",
        "new_reservation_for_donor": (
            "🔔 Қайырыңызға жаңа сұрау!\n\n"
            "Бөлім: {category}\n"
            "Қайыр: {description}\n\n"
            "Мұқтаж мәліметтері:\n"
            "👤 {full_name}\n"
            "📍 {address}\n"
            "📞 {phone}\n\n"
            "Қайырды көрсетілген мекенжайға жақын жеткізу қызметі арқылы жіберіп, \"Kabinet\" қосымшасы арқылы чекті жүктеңіз."
        ),
        "shipped_saved_donor": "✅ Рахмет! Қайырдың жолға шыққаны расталды және мұқтажға хабарланды.",
        "shipped_notify_needy": (
            "📦 Қуанышты хабар! Сіздің қайырыңыз жолға шықты.\n\n"
            "Пошта чегі төменде тіркелген. Қайыр қолыңызға тигенде \"Kabinet\" қосымшасында қабылдағаныңызды растаңыз."
        ),
        "received_notify_donor": (
            "🎉 Қайырыңыз сәтті жетті!\n\n"
            "Мұқтаждың алғысы/тілегі:\n\"{dua_text}\""
        ),
        "unknown_command": "Өтінемін, \"Kabinet\" қосымшасын пайдаланыңыз.",
        "reservation_cancelled_notify_donor": (
            "ℹ️ Мұқтаж \"{description}\" қайырыңызға деген сұрауын бас тартты.\n\n"
            "Қайыр қайтадан \"қолжетімді\" күйіне қайтарылды."
        ),
    },
    "tg": {
        "choose_language": "🌐 Забонро интихоб кунед:",
        "language_set": "✅ Забон ба тоҷикӣ гузошта шуд.",
        "choose_role": "Ассалому алайкум! Ба боти тақсими хайрия хуш омадед.\n\nЛутфан, мақоми худро интихоб намоед:",
        "role_donor": "🫴 Саховатманд",
        "role_needy": "🤲 Ниёзманд",
        "welcome_back": "Хуш омадед!",
        "open_app_hint": "📱 Ҳамаи амалҳо (илова кардани хайрия, дидан, кабинет) дар дохили барномае, ки бо тугмаи меню — \"Kabinet\" кушода мешавад, иҷро мешаванд.\n\nДар ин ҷо бошад, танҳо огоҳиномаҳои муҳим фиристода мешаванд.",
        "open_app_button": "📱 Кушодани барнома",
        "donation_added": "✅ Хайрияи шумо бомуваффақият ҷойгир карда шуд! Ташаккур, кори савобе мекунед.",
        "new_reservation_for_donor": (
            "🔔 Дархости нав ба хайрияи шумо!\n\n"
            "Бахш: {category}\n"
            "Хайрия: {description}\n\n"
            "Маълумоти ниёзманд:\n"
            "👤 {full_name}\n"
            "📍 {address}\n"
            "📞 {phone}\n\n"
            "Лутфан, хайрияро ба суроғаи нишондодашуда тавассути хидмати расонии наздик фиристед ва тавассути барномаи \"Kabinet\" чекро бор кунед."
        ),
        "shipped_saved_donor": "✅ Ташаккур! Фиристодани хайрия тасдиқ шуд ва ба ниёзманд хабар дода шуд.",
        "shipped_notify_needy": (
            "📦 Хушхабар! Хайрияи шумо дар роҳ аст.\n\n"
            "Чеки почта дар поён замима шудааст. Ҳамин ки хайрия ба дастатон расид, дар барномаи \"Kabinet\" қабул карданатонро тасдиқ кунед."
        ),
        "received_notify_donor": (
            "🎉 Хайрияи шумо бомуваффақият расид!\n\n"
            "Дуо/суханони миннатдории ниёзманд:\n\"{dua_text}\""
        ),
        "unknown_command": "Лутфан, аз барномаи \"Kabinet\" истифода баред.",
        "reservation_cancelled_notify_donor": (
            "ℹ️ Ниёзманд дархости худро нисбат ба хайрияи \"{description}\" бекор кард.\n\n"
            "Хайрия дубора ба ҳолати \"дастрас\" баргашт."
        ),
    },
    "ky": {
        "choose_language": "🌐 Тилди тандаңыз:",
        "language_set": "✅ Тил кыргызчага орнотулду.",
        "choose_role": "Ассалому алейкум! Садага үлүштүрүү ботуна кош келиңиз.\n\nСтатусуңузду тандаңыз:",
        "role_donor": "🫴 Кайрымдуу",
        "role_needy": "🤲 Мукташ",
        "welcome_back": "Кош келиңиз!",
        "open_app_hint": "📱 Бардык аракеттер (садага кошуу, көрүү, кабинет) төмөнкү меню баскычы — \"Kabinet\" аркылуу ачылуучу колдонмонун ичинде аткарылат.\n\nБул жерде болсо, тек гана маанилүү жаңылыктар жана билдирүүлөр жөнөтүлөт.",
        "open_app_button": "📱 Колдонмону ачуу",
        "donation_added": "✅ Садагаңыз ийгиликтүү жайгаштырылды! Рахмат, сооп иш кылып жатасыз.",
        "new_reservation_for_donor": (
            "🔔 Садагаңызга жаңы сурам!\n\n"
            "Бөлүм: {category}\n"
            "Садага: {description}\n\n"
            "Мукташ маалыматтары:\n"
            "👤 {full_name}\n"
            "📍 {address}\n"
            "📞 {phone}\n\n"
            "Садаганы көрсөтүлгөн дарекке жакын жеткирүү кызматы аркылуу жөнөтүп, \"Kabinet\" колдонмосу аркылуу чекти жүктөңүз."
        ),
        "shipped_saved_donor": "✅ Рахмат! Садаганын жолго чыкканы тастыкталды жана мукташка билдирилди.",
        "shipped_notify_needy": (
            "📦 Кубанычтуу кабар! Сиздин садагаңыз жолдо.\n\n"
            "Почта чеги төмөндө тиркелген. Садага колуңузга тийери менен \"Kabinet\" колдонмосунда кабыл алганыңызды тастыктаңыз."
        ),
        "received_notify_donor": (
            "🎉 Садагаңыз ийгиликтүү жетти!\n\n"
            "Мукташтын дубасы/ыраазычылыгы:\n\"{dua_text}\""
        ),
        "unknown_command": "Сураныч, \"Kabinet\" колдонмосун колдонуңуз.",
        "reservation_cancelled_notify_donor": (
            "ℹ️ Мукташ \"{description}\" садагаңызга болгон суранычын жокко чыгарды.\n\n"
            "Садага кайра \"жеткиликтүү\" абалына кайтарылды."
        ),
    },
    "tk": {
        "choose_language": "🌐 Dili saýlaň:",
        "language_set": "✅ Dil türkmen diline sazlandy.",
        "choose_role": "Salam! Sadaka paýlaşyk botuna hoş geldiňiz.\n\nÝagdaýyňyzy saýlaň:",
        "role_donor": "🫴 Sahawatly",
        "role_needy": "🤲 Mätäç",
        "welcome_back": "Hoş geldiňiz!",
        "open_app_hint": "📱 Ähli hereketler (sadaka goşmak, görmek, kabinet) aşakdaky menýu düwmesi — \"Kabinet\" arkaly açylýan programmanyň içinde ýerine ýetirilýär.\n\nBu ýerde bolsa diňe möhüm täzelikler we bildirişler iberilýär.",
        "open_app_button": "📱 Programmany açmak",
        "donation_added": "✅ Sadakaňyz üstünlikli ýerleşdirildi! Sag boluň, sogap iş edýärsiňiz.",
        "new_reservation_for_donor": (
            "🔔 Sadakaňyza täze sorag!\n\n"
            "Bölüm: {category}\n"
            "Sadaka: {description}\n\n"
            "Mätäjiň maglumatlary:\n"
            "👤 {full_name}\n"
            "📍 {address}\n"
            "📞 {phone}\n\n"
            "Sadakany görkezilen salga golaý eltip beriş gullugy arkaly iberip, \"Kabinet\" programmasy arkaly çeki ýükläň."
        ),
        "shipped_saved_donor": "✅ Sag boluň! Sadakanyň ýola çykandygy tassyklandy we mätäje habar berildi.",
        "shipped_notify_needy": (
            "📦 Guwandyryjy habar! Siziň sadakaňyz ýolda.\n\n"
            "Poçta çeki aşakda goşulan. Sadaka eliňize gowşanda \"Kabinet\" programmasynda kabul edendigiňizi tassyklaň."
        ),
        "received_notify_donor": (
            "🎉 Sadakaňyz üstünlikli gowuşdy!\n\n"
            "Mätäjiň dogasy/minnetdarlygy:\n\"{dua_text}\""
        ),
        "unknown_command": "Haýyş, \"Kabinet\" programmasyny ulanyň.",
        "reservation_cancelled_notify_donor": (
            "ℹ️ Mätäç \"{description}\" sadakaňyza bolan soragyny ýatyrdy.\n\n"
            "Sadaka ýene-de \"elýeterli\" ýagdaýyna gaýtaryldy."
        ),
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
