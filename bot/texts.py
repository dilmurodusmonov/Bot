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
        "open_app_hint": "📱 Barcha amallar (ehson qo'shish, ko'rish, kabinet) pastdagi menyu tugmasi — \"Kabinet\" orqali ochiladigan ilova ichida bajariladi.\n\nBu yerda esa faqat muhim yangiliklar va bildirishnomalar yuboriladi.",
        "open_app_button": "📱 Ilovani ochish",
        "new_reservation_for_donor": (
            "🔔 Ehsoningizga yangi so'rov!\n\n"
            "Bo'lim: <b>{category}</b>\n"
            "Ehson: <b>{description}</b>\n\n"
            "Muhtoj ma'lumotlari:\n"
            "👤 <b>{full_name}</b>\n"
            "📍 <b>{address}</b>\n"
            "📞 <b>{phone}</b>\n\n"
            "Iltimos, ehsonni ko'rsatilgan manzilga yaqin kuryerlik orqali yuboring va \"Kabinet\" ilovasi orqali pochta chekini yuklang."
        ),
        "shipped_saved_donor": "✅ Rahmat! Ehson yo'lga chiqqanligi tasdiqlandi va Muhtojga xabar berildi. Muhtoj tasdiqlaganda sizga xabar beramiz.",
        "shipped_notify_needy": (
            "📦 Xushxabar! Sizning ehsoningiz yo'lga chiqdi.\n\n"
            "Pochta cheki quyida biriktirilgan. Ehson qo'lingizga tegishi bilan \"Kabinet\" ilovasida qabul qilganingizni tasdiqlang."
        ),
        "received_notify_donor": (
            "🎉 Ehsoningiz muvaffaqiyatli yetib bordi!\n\n"
            "Muhtojning duosi/minnatdorchiligi:\n<b>\"{dua_text}\"</b>"
        ),
        "unknown_command": "Iltimos, \"Kabinet\" ilovasidan foydalaning.",
        "reservation_cancelled_notify_donor": (
            "ℹ️ Muhtoj <b>\"{description}\"</b> ehsoningizga bo'lgan so'rovini bekor qildi.\n\n"
            "Ehson yana \"mavjud\" holatiga qaytarildi."
        ),
        "view_receipt_button": "🧾 Chekni ko'rish",
        "ship_reminder": (
            "⏰ Eslatma! <b>{description}</b> ehsoningizni hali yo'lga chiqarmadingiz. "
            "Iltimos, tezroq yuboring va \"Kabinet\" ilovasida chekni yuklang."
        ),
        "receive_reminder": (
            "⏰ Eslatma! Ehsoningiz yo'lda, lekin hali qabul qilganingizni tasdiqlamadingiz. "
            "Iltimos, \"Kabinet\" ilovasida tasdiqlang."
        ),
    },
    "ru": {
        "choose_language": "🌐 Выберите язык:",
        "language_set": "✅ Язык изменён на русский.",
        "choose_role": "Здравствуйте! Добро пожаловать в бот пожертвований.\n\nПожалуйста, выберите свой статус:",
        "role_donor": "🫴 Благотворитель",
        "role_needy": "🤲 Нуждающийся",
        "open_app_hint": "📱 Все действия (добавление, просмотр, кабинет) выполняются внутри приложения, которое открывается кнопкой меню — \"Kabinet\".\n\nЗдесь же вы будете получать только важные уведомления.",
        "open_app_button": "📱 Открыть приложение",
        "new_reservation_for_donor": (
            "🔔 Новая заявка на ваше пожертвование!\n\n"
            "Раздел: <b>{category}</b>\n"
            "Пожертвование: <b>{description}</b>\n\n"
            "Данные нуждающегося:\n"
            "👤 <b>{full_name}</b>\n"
            "📍 <b>{address}</b>\n"
            "📞 <b>{phone}</b>\n\n"
            "Пожалуйста, отправьте пожертвование по указанному адресу через ближайшую курьерскую службу и загрузите чек в приложении \"Kabinet\"."
        ),
        "shipped_saved_donor": "✅ Спасибо! Подтверждена отправка пожертвования, нуждающийся уведомлён. Как только он подтвердит получение, мы сообщим вам.",
        "shipped_notify_needy": (
            "📦 Хорошая новость! Ваше пожертвование в пути.\n\n"
            "Почтовый чек прикреплён ниже. Когда получите посылку, подтвердите получение в приложении \"Kabinet\"."
        ),
        "received_notify_donor": (
            "🎉 Ваше пожертвование успешно доставлено!\n\n"
            "Слова благодарности от нуждающегося:\n<b>\"{dua_text}\"</b>"
        ),
        "unknown_command": "Пожалуйста, используйте приложение \"Kabinet\".",
        "reservation_cancelled_notify_donor": (
            "ℹ️ Нуждающийся отменил заявку на пожертвование <b>\"{description}\"</b>.\n\n"
            "Пожертвование снова доступно."
        ),
        "view_receipt_button": "🧾 Посмотреть чек",
        "ship_reminder": (
            "⏰ Напоминание! Вы ещё не отправили пожертвование «<b>{description}</b>». "
            "Пожалуйста, отправьте его как можно скорее и загрузите чек в приложении \"Kabinet\"."
        ),
        "receive_reminder": (
            "⏰ Напоминание! Ваше пожертвование в пути, но вы ещё не подтвердили получение. "
            "Пожалуйста, подтвердите в приложении \"Kabinet\"."
        ),
    },
    "en": {
        "choose_language": "🌐 Choose your language:",
        "language_set": "✅ Language set to English.",
        "choose_role": "Hello! Welcome to the Charity Sharing bot.\n\nPlease choose your status:",
        "role_donor": "🫴 Donor",
        "role_needy": "🤲 In need",
        "open_app_hint": "📱 All actions (adding, browsing, your cabinet) happen inside the app opened via the \"Kabinet\" menu button.\n\nHere in chat you'll only receive important notifications.",
        "open_app_button": "📱 Open the app",
        "new_reservation_for_donor": (
            "🔔 New request for your donation!\n\n"
            "Category: <b>{category}</b>\n"
            "Donation: <b>{description}</b>\n\n"
            "Recipient details:\n"
            "👤 <b>{full_name}</b>\n"
            "📍 <b>{address}</b>\n"
            "📞 <b>{phone}</b>\n\n"
            "Please ship the donation to the given address via a nearby courier and upload the receipt in the \"Kabinet\" app."
        ),
        "shipped_saved_donor": "✅ Thank you! Shipment confirmed and the recipient has been notified. We'll let you know once they confirm receipt.",
        "shipped_notify_needy": (
            "📦 Good news! Your donation is on the way.\n\n"
            "The shipping receipt is attached below. Confirm receipt in the \"Kabinet\" app once you get the package."
        ),
        "received_notify_donor": (
            "🎉 Your donation was successfully delivered!\n\n"
            "Words of thanks from the recipient:\n<b>\"{dua_text}\"</b>"
        ),
        "unknown_command": "Please use the \"Kabinet\" app.",
        "reservation_cancelled_notify_donor": (
            "ℹ️ The recipient cancelled their request for <b>\"{description}\"</b>.\n\n"
            "The donation is available again."
        ),
        "view_receipt_button": "🧾 View receipt",
        "ship_reminder": (
            "⏰ Reminder! You haven't shipped your donation \"<b>{description}</b>\" yet. "
            "Please ship it soon and upload the receipt in the \"Kabinet\" app."
        ),
        "receive_reminder": (
            "⏰ Reminder! Your donation is on the way, but you haven't confirmed receipt yet. "
            "Please confirm in the \"Kabinet\" app."
        ),
    },
    "kk": {
        "choose_language": "🌐 Тілді таңдаңыз:",
        "language_set": "✅ Тіл қазақ тіліне орнатылды.",
        "choose_role": "Ассалаумағалейкум! Қайыр үлестіру ботына қош келдіңіз.\n\nМәртебеңізді таңдаңыз:",
        "role_donor": "🫴 Қайырымды",
        "role_needy": "🤲 Мұқтаж",
        "open_app_hint": "📱 Барлық әрекеттер (қайыр қосу, көру, кабинет) төмендегі мәзір түймесі — \"Kabinet\" арқылы ашылатын қосымша ішінде орындалады.\n\nМұнда тек маңызды жаңалықтар мен хабарландырулар жіберіледі.",
        "open_app_button": "📱 Қосымшаны ашу",
        "new_reservation_for_donor": (
            "🔔 Қайырыңызға жаңа сұрау!\n\n"
            "Бөлім: <b>{category}</b>\n"
            "Қайыр: <b>{description}</b>\n\n"
            "Мұқтаж мәліметтері:\n"
            "👤 <b>{full_name}</b>\n"
            "📍 <b>{address}</b>\n"
            "📞 <b>{phone}</b>\n\n"
            "Қайырды көрсетілген мекенжайға жақын жеткізу қызметі арқылы жіберіп, \"Kabinet\" қосымшасы арқылы чекті жүктеңіз."
        ),
        "shipped_saved_donor": "✅ Рахмет! Қайырдың жолға шыққаны расталды және мұқтажға хабарланды. Мұқтаж растаған кезде сізге хабарлаймыз.",
        "shipped_notify_needy": (
            "📦 Қуанышты хабар! Сіздің қайырыңыз жолға шықты.\n\n"
            "Пошта чегі төменде тіркелген. Қайыр қолыңызға тигенде \"Kabinet\" қосымшасында қабылдағаныңызды растаңыз."
        ),
        "received_notify_donor": (
            "🎉 Қайырыңыз сәтті жетті!\n\n"
            "Мұқтаждың алғысы/тілегі:\n<b>\"{dua_text}\"</b>"
        ),
        "unknown_command": "Өтінемін, \"Kabinet\" қосымшасын пайдаланыңыз.",
        "reservation_cancelled_notify_donor": (
            "ℹ️ Мұқтаж <b>\"{description}\"</b> қайырыңызға деген сұрауын бас тартты.\n\n"
            "Қайыр қайтадан \"қолжетімді\" күйіне қайтарылды."
        ),
        "view_receipt_button": "🧾 Чекті көру",
        "ship_reminder": (
            "⏰ Еске салу! Сіз әлі <b>«{description}»</b> қайырыңызды жолға шығармадыңыз. "
            "Өтінемін, жақын арада жіберіп, \"Kabinet\" қосымшасында чекті жүктеңіз."
        ),
        "receive_reminder": (
            "⏰ Еске салу! Қайырыңыз жолда, бірақ сіз әлі қабылдағаныңызды растамадыңыз. "
            "Өтінемін, \"Kabinet\" қосымшасында растаңыз."
        ),
    },
    "tg": {
        "choose_language": "🌐 Забонро интихоб кунед:",
        "language_set": "✅ Забон ба тоҷикӣ гузошта шуд.",
        "choose_role": "Ассалому алайкум! Ба боти тақсими хайрия хуш омадед.\n\nЛутфан, мақоми худро интихоб намоед:",
        "role_donor": "🫴 Саховатманд",
        "role_needy": "🤲 Ниёзманд",
        "open_app_hint": "📱 Ҳамаи амалҳо (илова кардани хайрия, дидан, кабинет) дар дохили барномае, ки бо тугмаи меню — \"Kabinet\" кушода мешавад, иҷро мешаванд.\n\nДар ин ҷо бошад, танҳо огоҳиномаҳои муҳим фиристода мешаванд.",
        "open_app_button": "📱 Кушодани барнома",
        "new_reservation_for_donor": (
            "🔔 Дархости нав ба хайрияи шумо!\n\n"
            "Бахш: <b>{category}</b>\n"
            "Хайрия: <b>{description}</b>\n\n"
            "Маълумоти ниёзманд:\n"
            "👤 <b>{full_name}</b>\n"
            "📍 <b>{address}</b>\n"
            "📞 <b>{phone}</b>\n\n"
            "Лутфан, хайрияро ба суроғаи нишондодашуда тавассути хидмати расонии наздик фиристед ва тавассути барномаи \"Kabinet\" чекро бор кунед."
        ),
        "shipped_saved_donor": "✅ Ташаккур! Фиристодани хайрия тасдиқ шуд ва ба ниёзманд хабар дода шуд. Ҳангоми тасдиқи қабули ниёзманд ба шумо хабар медиҳем.",
        "shipped_notify_needy": (
            "📦 Хушхабар! Хайрияи шумо дар роҳ аст.\n\n"
            "Чеки почта дар поён замима шудааст. Ҳамин ки хайрия ба дастатон расид, дар барномаи \"Kabinet\" қабул карданатонро тасдиқ кунед."
        ),
        "received_notify_donor": (
            "🎉 Хайрияи шумо бомуваффақият расид!\n\n"
            "Дуо/суханони миннатдории ниёзманд:\n<b>\"{dua_text}\"</b>"
        ),
        "unknown_command": "Лутфан, аз барномаи \"Kabinet\" истифода баред.",
        "reservation_cancelled_notify_donor": (
            "ℹ️ Ниёзманд дархости худро нисбат ба хайрияи <b>\"{description}\"</b> бекор кард.\n\n"
            "Хайрия дубора ба ҳолати \"дастрас\" баргашт."
        ),
        "view_receipt_button": "🧾 Дидани чек",
        "ship_reminder": (
            "⏰ Ёдоварӣ! Шумо ҳанӯз хайрияи <b>«{description}»</b>-ро нафиристодаед. "
            "Лутфан, наздиктар фиристед ва дар барномаи \"Kabinet\" чекро бор кунед."
        ),
        "receive_reminder": (
            "⏰ Ёдоварӣ! Хайрияи шумо дар роҳ аст, аммо шумо ҳанӯз қабул карданатонро тасдиқ накардаед. "
            "Лутфан, дар барномаи \"Kabinet\" тасдиқ кунед."
        ),
    },
    "ky": {
        "choose_language": "🌐 Тилди тандаңыз:",
        "language_set": "✅ Тил кыргызчага орнотулду.",
        "choose_role": "Ассалому алейкум! Садага үлүштүрүү ботуна кош келиңиз.\n\nСтатусуңузду тандаңыз:",
        "role_donor": "🫴 Кайрымдуу",
        "role_needy": "🤲 Мукташ",
        "open_app_hint": "📱 Бардык аракеттер (садага кошуу, көрүү, кабинет) төмөнкү меню баскычы — \"Kabinet\" аркылуу ачылуучу колдонмонун ичинде аткарылат.\n\nБул жерде болсо, тек гана маанилүү жаңылыктар жана билдирүүлөр жөнөтүлөт.",
        "open_app_button": "📱 Колдонмону ачуу",
        "new_reservation_for_donor": (
            "🔔 Садагаңызга жаңы сурам!\n\n"
            "Бөлүм: <b>{category}</b>\n"
            "Садага: <b>{description}</b>\n\n"
            "Мукташ маалыматтары:\n"
            "👤 <b>{full_name}</b>\n"
            "📍 <b>{address}</b>\n"
            "📞 <b>{phone}</b>\n\n"
            "Садаганы көрсөтүлгөн дарекке жакын жеткирүү кызматы аркылуу жөнөтүп, \"Kabinet\" колдонмосу аркылуу чекти жүктөңүз."
        ),
        "shipped_saved_donor": "✅ Рахмат! Садаганын жолго чыкканы тастыкталды жана мукташка билдирилди. Мукташ тастыктаганда сизге билдиребиз.",
        "shipped_notify_needy": (
            "📦 Кубанычтуу кабар! Сиздин садагаңыз жолдо.\n\n"
            "Почта чеги төмөндө тиркелген. Садага колуңузга тийери менен \"Kabinet\" колдонмосунда кабыл алганыңызды тастыктаңыз."
        ),
        "received_notify_donor": (
            "🎉 Садагаңыз ийгиликтүү жетти!\n\n"
            "Мукташтын дубасы/ыраазычылыгы:\n<b>\"{dua_text}\"</b>"
        ),
        "unknown_command": "Сураныч, \"Kabinet\" колдонмосун колдонуңуз.",
        "reservation_cancelled_notify_donor": (
            "ℹ️ Мукташ <b>\"{description}\"</b> садагаңызга болгон суранычын жокко чыгарды.\n\n"
            "Садага кайра \"жеткиликтүү\" абалына кайтарылды."
        ),
        "view_receipt_button": "🧾 Чекти көрүү",
        "ship_reminder": (
            "⏰ Эскертүү! Сиз әли <b>«{description}»</b> садагаңызды жолго чыгарган жоксуз. "
            "Сураныч, жакын арада жөнөтүп, \"Kabinet\" колдонмосунда чекти жүктөңүз."
        ),
        "receive_reminder": (
            "⏰ Эскертүү! Садагаңыз жолдо, бирок сиз әли кабыл алганыңызды тастыктаган жоксуз. "
            "Сураныч, \"Kabinet\" колдонмосунда тастыктаңыз."
        ),
    },
    "tk": {
        "choose_language": "🌐 Dili saýlaň:",
        "language_set": "✅ Dil türkmen diline sazlandy.",
        "choose_role": "Salam! Sadaka paýlaşyk botuna hoş geldiňiz.\n\nÝagdaýyňyzy saýlaň:",
        "role_donor": "🫴 Sahawatly",
        "role_needy": "🤲 Mätäç",
        "open_app_hint": "📱 Ähli hereketler (sadaka goşmak, görmek, kabinet) aşakdaky menýu düwmesi — \"Kabinet\" arkaly açylýan programmanyň içinde ýerine ýetirilýär.\n\nBu ýerde bolsa diňe möhüm täzelikler we bildirişler iberilýär.",
        "open_app_button": "📱 Programmany açmak",
        "new_reservation_for_donor": (
            "🔔 Sadakaňyza täze sorag!\n\n"
            "Bölüm: <b>{category}</b>\n"
            "Sadaka: <b>{description}</b>\n\n"
            "Mätäjiň maglumatlary:\n"
            "👤 <b>{full_name}</b>\n"
            "📍 <b>{address}</b>\n"
            "📞 <b>{phone}</b>\n\n"
            "Sadakany görkezilen salga golaý eltip beriş gullugy arkaly iberip, \"Kabinet\" programmasy arkaly çeki ýükläň."
        ),
        "shipped_saved_donor": "✅ Sag boluň! Sadakanyň ýola çykandygy tassyklandy we mätäje habar berildi. Mätäç tassyklanda size habar bereris.",
        "shipped_notify_needy": (
            "📦 Guwandyryjy habar! Siziň sadakaňyz ýolda.\n\n"
            "Poçta çeki aşakda goşulan. Sadaka eliňize gowşanda \"Kabinet\" programmasynda kabul edendigiňizi tassyklaň."
        ),
        "received_notify_donor": (
            "🎉 Sadakaňyz üstünlikli gowuşdy!\n\n"
            "Mätäjiň dogasy/minnetdarlygy:\n<b>\"{dua_text}\"</b>"
        ),
        "unknown_command": "Haýyş, \"Kabinet\" programmasyny ulanyň.",
        "reservation_cancelled_notify_donor": (
            "ℹ️ Mätäç <b>\"{description}\"</b> sadakaňyza bolan soragyny ýatyrdy.\n\n"
            "Sadaka ýene-de \"elýeterli\" ýagdaýyna gaýtaryldy."
        ),
        "view_receipt_button": "🧾 Çeki görmek",
        "ship_reminder": (
            "⏰ Ýatlatma! Siz entäk <b>«{description}»</b> sadakaňyzy ýola çykarmadyňyz. "
            "Haýyş, ýakyn wagtda iberiň we \"Kabinet\" programmasynda çeki ýükläň."
        ),
        "receive_reminder": (
            "⏰ Ýatlatma! Sadakaňyz ýolda, ýöne siz entäk kabul edendigiňizi tassyklamadyňyz. "
            "Haýyş, \"Kabinet\" programmasynda tassyklaň."
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


# --- kanal e'lonlari ---------------------------------------------------------
#
# Kanalning auditoriyasi aralash, shuning uchun e'lon matni foydalanuvchi
# tiliga bog'lanmaydi — bitta o'zbekcha shablon ishlatiladi.

CHANNEL_OPEN_BUTTON = "🤲 Ehsonni olish"

