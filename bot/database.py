from typing import Any, Optional

import asyncpg

from bot.config import DATABASE_URL

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    telegram_id BIGINT PRIMARY KEY,
    language TEXT,
    role TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS donations (
    id SERIAL PRIMARY KEY,
    donor_id BIGINT NOT NULL REFERENCES users(telegram_id),
    category TEXT NOT NULL,
    photo_file_id TEXT NOT NULL,
    photo_file_id_2 TEXT,
    photo_file_id_3 TEXT,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'available',
    share_count INTEGER NOT NULL DEFAULT 0,
    channel_message_ids TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS reservations (
    id SERIAL PRIMARY KEY,
    donation_id INTEGER NOT NULL REFERENCES donations(id),
    needy_id BIGINT NOT NULL REFERENCES users(telegram_id),
    full_name TEXT NOT NULL,
    address TEXT NOT NULL,
    phone TEXT NOT NULL,
    receipt_photo_file_id TEXT,
    receipt_note TEXT,
    dua_text TEXT,
    status TEXT NOT NULL DEFAULT 'reserved',
    donor_notify_message_id BIGINT,
    needy_notify_message_id BIGINT,
    donor_reminder_count INTEGER NOT NULL DEFAULT 0,
    donor_last_reminder_at TIMESTAMPTZ,
    needy_reminder_count INTEGER NOT NULL DEFAULT 0,
    needy_last_reminder_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    shipped_at TIMESTAMPTZ,
    received_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS ad_stats (
    slide INTEGER PRIMARY KEY,
    views BIGINT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS donation_likes (
    donation_id INTEGER NOT NULL REFERENCES donations(id),
    telegram_id BIGINT NOT NULL REFERENCES users(telegram_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (donation_id, telegram_id)
);

CREATE TABLE IF NOT EXISTS ad_bids (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT NOT NULL REFERENCES users(telegram_id),
    brand_name TEXT NOT NULL,
    url TEXT NOT NULL,
    bid_amount BIGINT NOT NULL,
    platform TEXT,
    photo_url TEXT,
    category TEXT,
    description TEXT,
    description_checked BOOLEAN NOT NULL DEFAULT FALSE,
    clicks INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'approved',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

_pool: Optional[asyncpg.Pool] = None


def _get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool ishga tushmagan — avval init_db() chaqiring.")
    return _pool


async def init_db() -> None:
    global _pool
    _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    async with _pool.acquire() as conn:
        await conn.execute(SCHEMA)
        await _migrate_ad_stats(conn)
        await _migrate_donation_photos(conn)
        await _migrate_donation_share_count(conn)
        await _migrate_donation_channel_message(conn)
        await _migrate_reservation_notify_messages(conn)
        await _migrate_ad_bids_multi(conn)
        await _migrate_ad_bids_platform(conn)
        await _migrate_ad_bids_category(conn)
        await _migrate_ad_bids_description(conn)
        await _migrate_ad_bids_clicks(conn)
        await _migrate_ad_payments(conn)


async def _migrate_ad_stats(conn: asyncpg.Connection) -> None:
    """Eski ad_stats jadvali bitta umumiy hisoblagich edi (id, doim id=1).
    Endi har bir banner slaydi o'z hisobiga ega bo'lishi uchun 'slide'
    ustuniga o'tkaziladi — mavjud son slide=1 sifatida saqlanib qoladi."""
    has_old_column = await conn.fetchval(
        """SELECT EXISTS (
               SELECT 1 FROM information_schema.columns
               WHERE table_name = 'ad_stats' AND column_name = 'id'
           )"""
    )
    if has_old_column:
        await conn.execute("ALTER TABLE ad_stats RENAME COLUMN id TO slide")
        await conn.execute("ALTER TABLE ad_stats DROP CONSTRAINT IF EXISTS ad_stats_id_check")
        await conn.execute("ALTER TABLE ad_stats ALTER COLUMN slide DROP DEFAULT")


async def _migrate_donation_photos(conn: asyncpg.Connection) -> None:
    """Bitta ehsonga bir nechta (max 3) rasm biriktirish imkoniyati uchun ustunlar."""
    await conn.execute("ALTER TABLE donations ADD COLUMN IF NOT EXISTS photo_file_id_2 TEXT")
    await conn.execute("ALTER TABLE donations ADD COLUMN IF NOT EXISTS photo_file_id_3 TEXT")


async def _migrate_donation_share_count(conn: asyncpg.Connection) -> None:
    await conn.execute(
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS share_count INTEGER NOT NULL DEFAULT 0"
    )


async def _migrate_donation_channel_message(conn: asyncpg.Connection) -> None:
    """Ehson kanalga e'lon qilinganda post id'lari shu ustunda saqlanadi —
    keyinchalik holat o'zgarsa post tahrirlanadi yoki o'chiriladi.

    Bir nechta rasmli ehson albom bo'lib chiqadi, ya'ni bir nechta xabar
    hosil bo'ladi. Shuning uchun id'lar vergul bilan ajratilgan matn
    sifatida saqlanadi. Avvalgi bitta butun sonli ustun ko'chiriladi."""
    await conn.execute(
        "ALTER TABLE donations ADD COLUMN IF NOT EXISTS channel_message_ids TEXT"
    )


async def _migrate_reservation_notify_messages(conn: asyncpg.Connection) -> None:
    """Bot chatida holat almashganda eskirgan bildirishnoma xabari
    o'chirilishi uchun, oxirgi yuborilgan xabar id'si saqlanadi."""
    await conn.execute(
        "ALTER TABLE reservations ADD COLUMN IF NOT EXISTS donor_notify_message_id BIGINT"
    )
    await conn.execute(
        "ALTER TABLE reservations ADD COLUMN IF NOT EXISTS needy_notify_message_id BIGINT"
    )
    await conn.execute(
        "ALTER TABLE reservations ADD COLUMN IF NOT EXISTS donor_reminder_count INTEGER NOT NULL DEFAULT 0"
    )
    await conn.execute(
        "ALTER TABLE reservations ADD COLUMN IF NOT EXISTS donor_last_reminder_at TIMESTAMPTZ"
    )
    await conn.execute(
        "ALTER TABLE reservations ADD COLUMN IF NOT EXISTS needy_reminder_count INTEGER NOT NULL DEFAULT 0"
    )
    await conn.execute(
        "ALTER TABLE reservations ADD COLUMN IF NOT EXISTS needy_last_reminder_at TIMESTAMPTZ"
    )
    has_old = await conn.fetchval(
        """SELECT EXISTS (
               SELECT 1 FROM information_schema.columns
               WHERE table_name = 'donations' AND column_name = 'channel_message_id'
           )"""
    )
    if has_old:
        await conn.execute(
            """UPDATE donations
               SET channel_message_ids = channel_message_id::text
               WHERE channel_message_id IS NOT NULL
                 AND channel_message_ids IS NULL"""
        )
        await conn.execute("ALTER TABLE donations DROP COLUMN channel_message_id")


async def _migrate_ad_bids_multi(conn: asyncpg.Connection) -> None:
    """Dastlab ad_bids'da telegram_id PRIMARY KEY edi — bitta foydalanuvchi
    faqat bitta taklif berishi mumkin edi, yangi brend qo'shsa eskisi
    almashtirilib ketardi. Endi bitta foydalanuvchi bir nechta mustaqil
    brend/taklif joylashi mumkin — har biri o'z qatoriga ega bo'lishi
    uchun avtomatik o'sadigan 'id' PRIMARY KEY'ga o'tkaziladi."""
    has_id_column = await conn.fetchval(
        """SELECT EXISTS (
               SELECT 1 FROM information_schema.columns
               WHERE table_name = 'ad_bids' AND column_name = 'id'
           )"""
    )
    if not has_id_column:
        await conn.execute("ALTER TABLE ad_bids DROP CONSTRAINT IF EXISTS ad_bids_pkey")
        await conn.execute("ALTER TABLE ad_bids ADD COLUMN id SERIAL PRIMARY KEY")
        await conn.execute("ALTER TABLE ad_bids DROP COLUMN IF EXISTS updated_at")


async def _migrate_ad_bids_platform(conn: asyncpg.Connection) -> None:
    """Top 10 reytingda ham brend rasmi/platforma belgisi chiqishi uchun,
    preview'da aniqlangan platforma va rasm URL'i endi taklif bilan birga
    saqlanadi."""
    await conn.execute("ALTER TABLE ad_bids ADD COLUMN IF NOT EXISTS platform TEXT")
    await conn.execute("ALTER TABLE ad_bids ADD COLUMN IF NOT EXISTS photo_url TEXT")


async def _migrate_ad_bids_category(conn: asyncpg.Connection) -> None:
    """Taklif yuborishda foydalanuvchi brend kategoriyasini (masalan
    'Texnologiya va startaplar') tanlashi mumkin — buning uchun ustun."""
    await conn.execute("ALTER TABLE ad_bids ADD COLUMN IF NOT EXISTS category TEXT")


async def _migrate_ad_bids_description(conn: asyncpg.Connection) -> None:
    """Reyting ro'yxatida brend nomi ostida qisqa tavsif chiqishi uchun —
    URL preview'dan olingan tavsif shu ustunda saqlanadi."""
    await conn.execute("ALTER TABLE ad_bids ADD COLUMN IF NOT EXISTS description TEXT")


async def _migrate_ad_payments(conn: asyncpg.Connection) -> None:
    """Reklama to'lovi kartaga o'tkazma + chek orqali: taklif admin chekni
    tasdiqlaguncha 'pending' holatda turadi va reytingda ko'rinmaydi.
    Avvaldan mavjud takliflar 'approved' bo'lib qoladi."""
    await conn.execute("ALTER TABLE ad_bids ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'approved'")
    await conn.execute(
        """CREATE TABLE IF NOT EXISTS ad_payments (
               id SERIAL PRIMARY KEY,
               bid_id INTEGER NOT NULL REFERENCES ad_bids(id) ON DELETE CASCADE,
               telegram_id BIGINT NOT NULL,
               kind TEXT NOT NULL,
               amount BIGINT NOT NULL,
               receipt_file_id TEXT,
               status TEXT NOT NULL DEFAULT 'pending',
               decided_by BIGINT,
               decided_at TIMESTAMPTZ,
               created_at TIMESTAMPTZ NOT NULL DEFAULT now()
           )"""
    )
    await conn.execute("ALTER TABLE ad_payments ADD COLUMN IF NOT EXISTS reject_reason TEXT")
    await conn.execute(
        "ALTER TABLE ad_payments ADD COLUMN IF NOT EXISTS rejection_seen BOOLEAN NOT NULL DEFAULT FALSE"
    )


async def _migrate_ad_bids_clicks(conn: asyncpg.Connection) -> None:
    """Reytingdagi har bir brendga necha marta bosilgani hisoblanadi.
    description_checked — tavsifi yo'q eski takliflar uchun preview bir
    marta qayta so'ralganini belgilaydi (har safar qayta so'ramaslik uchun)."""
    await conn.execute("ALTER TABLE ad_bids ADD COLUMN IF NOT EXISTS clicks INTEGER NOT NULL DEFAULT 0")
    await conn.execute(
        "ALTER TABLE ad_bids ADD COLUMN IF NOT EXISTS description_checked BOOLEAN NOT NULL DEFAULT FALSE"
    )


# --- users -----------------------------------------------------------------

async def get_user(telegram_id: int) -> Optional[dict[str, Any]]:
    row = await _get_pool().fetchrow(
        "SELECT * FROM users WHERE telegram_id = $1", telegram_id
    )
    return dict(row) if row else None


async def create_user_if_missing(telegram_id: int) -> dict[str, Any]:
    user = await get_user(telegram_id)
    if user:
        return user
    await _get_pool().execute(
        "INSERT INTO users (telegram_id) VALUES ($1) ON CONFLICT (telegram_id) DO NOTHING",
        telegram_id,
    )
    return await get_user(telegram_id)


async def set_user_language(telegram_id: int, language: str) -> None:
    await _get_pool().execute(
        "UPDATE users SET language = $1 WHERE telegram_id = $2", language, telegram_id
    )


async def set_user_role(telegram_id: int, role: str) -> None:
    await _get_pool().execute(
        "UPDATE users SET role = $1 WHERE telegram_id = $2", role, telegram_id
    )


# --- donations ---------------------------------------------------------------

async def create_donation(
    donor_id: int, category: str, photo_file_ids: list[str], description: str
) -> int:
    photo_file_ids = photo_file_ids[:3]
    return await _get_pool().fetchval(
        """INSERT INTO donations
           (donor_id, category, photo_file_id, photo_file_id_2, photo_file_id_3, description, status)
           VALUES ($1, $2, $3, $4, $5, $6, 'available') RETURNING id""",
        donor_id,
        category,
        photo_file_ids[0],
        photo_file_ids[1] if len(photo_file_ids) > 1 else None,
        photo_file_ids[2] if len(photo_file_ids) > 2 else None,
        description,
    )


async def get_donation(donation_id: int) -> Optional[dict[str, Any]]:
    row = await _get_pool().fetchrow(
        "SELECT * FROM donations WHERE id = $1", donation_id
    )
    return dict(row) if row else None


async def get_available_donations(category: str) -> list[dict[str, Any]]:
    rows = await _get_pool().fetch(
        """SELECT * FROM donations WHERE category = $1 AND status = 'available'
           ORDER BY created_at DESC""",
        category,
    )
    return [dict(row) for row in rows]


async def get_donations_by_donor(donor_id: int) -> list[dict[str, Any]]:
    rows = await _get_pool().fetch(
        """SELECT * FROM donations WHERE donor_id = $1
           ORDER BY (status = 'reserved') DESC, created_at DESC""",
        donor_id,
    )
    return [dict(row) for row in rows]


async def set_donation_status(donation_id: int, status: str) -> None:
    await _get_pool().execute(
        "UPDATE donations SET status = $1 WHERE id = $2", status, donation_id
    )


async def set_donation_channel_messages(
    donation_id: int, message_ids: Optional[list[int]]
) -> None:
    await _get_pool().execute(
        "UPDATE donations SET channel_message_ids = $2 WHERE id = $1",
        donation_id,
        ",".join(str(mid) for mid in message_ids) if message_ids else None,
    )


async def delete_donation(donation_id: int) -> None:
    """Ehsonni o'chirish.

    donation_likes va reservations jadvallari donations(id) ga ON DELETE
    CASCADE'siz bog'langan, shuning uchun ularni oldin o'chirmasak, like
    bosilgan ehsonni o'chirishda tashqi kalit xatosi chiqadi.
    """
    pool = _get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            status = await conn.fetchval(
                "SELECT status FROM donations WHERE id = $1 FOR UPDATE", donation_id
            )
            if status != "available":
                return
            await conn.execute(
                "DELETE FROM donation_likes WHERE donation_id = $1", donation_id
            )
            await conn.execute(
                "DELETE FROM reservations WHERE donation_id = $1", donation_id
            )
            await conn.execute("DELETE FROM donations WHERE id = $1", donation_id)


# --- reservations -------------------------------------------------------------

async def create_reservation(
    donation_id: int, needy_id: int, full_name: str, address: str, phone: str
) -> int:
    return await _get_pool().fetchval(
        """INSERT INTO reservations
           (donation_id, needy_id, full_name, address, phone, status)
           VALUES ($1, $2, $3, $4, $5, 'reserved') RETURNING id""",
        donation_id,
        needy_id,
        full_name,
        address,
        phone,
    )


async def get_reservation(reservation_id: int) -> Optional[dict[str, Any]]:
    row = await _get_pool().fetchrow(
        "SELECT * FROM reservations WHERE id = $1", reservation_id
    )
    return dict(row) if row else None


async def get_active_reservation_for_donation(
    donation_id: int,
) -> Optional[dict[str, Any]]:
    row = await _get_pool().fetchrow(
        """SELECT * FROM reservations WHERE donation_id = $1
           ORDER BY created_at DESC LIMIT 1""",
        donation_id,
    )
    return dict(row) if row else None


async def get_reservations_by_needy(needy_id: int) -> list[dict[str, Any]]:
    rows = await _get_pool().fetch(
        """SELECT * FROM reservations WHERE needy_id = $1
           ORDER BY (status = 'shipped') DESC, created_at DESC""",
        needy_id,
    )
    return [dict(row) for row in rows]


async def get_reservations_pending_ship() -> list[dict[str, Any]]:
    """Saxiy hali yo'lga chiqarmagan bronlar — eslatma yuborish uchun."""
    rows = await _get_pool().fetch("SELECT * FROM reservations WHERE status = 'reserved'")
    return [dict(row) for row in rows]


async def get_reservations_pending_receive() -> list[dict[str, Any]]:
    """Muhtoj hali qabul qilganini tasdiqlamagan bronlar — eslatma yuborish uchun."""
    rows = await _get_pool().fetch("SELECT * FROM reservations WHERE status = 'shipped'")
    return [dict(row) for row in rows]


async def record_donor_reminder(reservation_id: int, message_id: int) -> None:
    await _get_pool().execute(
        """UPDATE reservations
           SET donor_notify_message_id = $1, donor_reminder_count = donor_reminder_count + 1,
               donor_last_reminder_at = now()
           WHERE id = $2""",
        message_id, reservation_id,
    )


async def record_needy_reminder(reservation_id: int, message_id: int) -> None:
    await _get_pool().execute(
        """UPDATE reservations
           SET needy_notify_message_id = $1, needy_reminder_count = needy_reminder_count + 1,
               needy_last_reminder_at = now()
           WHERE id = $2""",
        message_id, reservation_id,
    )


async def set_donor_notify_message(reservation_id: int, message_id: Optional[int]) -> None:
    await _get_pool().execute(
        "UPDATE reservations SET donor_notify_message_id = $1 WHERE id = $2",
        message_id, reservation_id,
    )


async def set_needy_notify_message(reservation_id: int, message_id: Optional[int]) -> None:
    await _get_pool().execute(
        "UPDATE reservations SET needy_notify_message_id = $1 WHERE id = $2",
        message_id, reservation_id,
    )


async def set_reservation_shipped(
    reservation_id: int, receipt_photo_file_id: str, receipt_note: Optional[str]
) -> None:
    await _get_pool().execute(
        """UPDATE reservations
           SET status = 'shipped', receipt_photo_file_id = $1, receipt_note = $2,
               shipped_at = now()
           WHERE id = $3""",
        receipt_photo_file_id,
        receipt_note,
        reservation_id,
    )


async def set_reservation_received(reservation_id: int, dua_text: str) -> None:
    await _get_pool().execute(
        """UPDATE reservations
           SET status = 'received', dua_text = $1, received_at = now()
           WHERE id = $2""",
        dua_text,
        reservation_id,
    )


async def cancel_reservation(reservation_id: int) -> None:
    await _get_pool().execute(
        "DELETE FROM reservations WHERE id = $1 AND status = 'reserved'", reservation_id
    )


async def count_pending_ship(donor_id: int) -> int:
    return await _get_pool().fetchval(
        """SELECT COUNT(*) FROM reservations r
           JOIN donations d ON d.id = r.donation_id
           WHERE d.donor_id = $1 AND r.status = 'reserved'""",
        donor_id,
    )


async def count_pending_receive(needy_id: int) -> int:
    return await _get_pool().fetchval(
        "SELECT COUNT(*) FROM reservations WHERE needy_id = $1 AND status = 'shipped'",
        needy_id,
    )


# --- statistika (admin panel uchun) ------------------------------------------

async def get_stats() -> dict[str, Any]:
    pool = _get_pool()
    stats: dict[str, Any] = {}

    stats["total_users"] = await pool.fetchval("SELECT COUNT(*) FROM users")
    stats["total_donors"] = await pool.fetchval(
        "SELECT COUNT(*) FROM users WHERE role = 'donor'"
    )
    stats["total_needy"] = await pool.fetchval(
        "SELECT COUNT(*) FROM users WHERE role = 'needy'"
    )
    stats["total_donations"] = await pool.fetchval("SELECT COUNT(*) FROM donations")

    rows = await pool.fetch("SELECT status, COUNT(*) AS count FROM donations GROUP BY status")
    stats["donations_by_status"] = {row["status"]: row["count"] for row in rows}

    rows = await pool.fetch(
        "SELECT category, COUNT(*) AS count FROM donations GROUP BY category"
    )
    stats["donations_by_category"] = {row["category"]: row["count"] for row in rows}

    stats["completed_donations"] = await pool.fetchval(
        "SELECT COUNT(*) FROM reservations WHERE status = 'received'"
    )

    return stats


async def get_reminder_stats() -> dict[str, Any]:
    """Admin panel uchun — javob berilmagan tranzaksion xabarlarga
    yuborilgan eslatmalar bo'yicha statistika."""
    pool = _get_pool()
    stats: dict[str, Any] = {}

    stats["donor_reminders_sent"] = await pool.fetchval(
        "SELECT COALESCE(SUM(donor_reminder_count), 0) FROM reservations"
    )
    stats["needy_reminders_sent"] = await pool.fetchval(
        "SELECT COALESCE(SUM(needy_reminder_count), 0) FROM reservations"
    )
    stats["pending_ship_total"] = await pool.fetchval(
        "SELECT COUNT(*) FROM reservations WHERE status = 'reserved'"
    )
    stats["pending_ship_reminded"] = await pool.fetchval(
        "SELECT COUNT(*) FROM reservations WHERE status = 'reserved' AND donor_reminder_count > 0"
    )
    stats["pending_receive_total"] = await pool.fetchval(
        "SELECT COUNT(*) FROM reservations WHERE status = 'shipped'"
    )
    stats["pending_receive_reminded"] = await pool.fetchval(
        "SELECT COUNT(*) FROM reservations WHERE status = 'shipped' AND needy_reminder_count > 0"
    )

    return stats


async def get_category_stats() -> dict[str, dict[str, int]]:
    rows = await _get_pool().fetch(
        """SELECT category,
                  COUNT(*) AS total,
                  COUNT(*) FILTER (WHERE status = 'received') AS delivered,
                  COUNT(*) FILTER (WHERE status = 'available') AS available,
                  COUNT(*) FILTER (WHERE created_at > now() - interval '24 hours') AS new_last_24h
           FROM donations
           GROUP BY category"""
    )
    return {
        row["category"]: {
            "total": row["total"],
            "delivered": row["delivered"],
            "available": row["available"],
            "new_last_24h": row["new_last_24h"],
        }
        for row in rows
    }


async def get_recent_donations(limit: int = 10) -> list[dict[str, Any]]:
    rows = await _get_pool().fetch(
        "SELECT * FROM donations ORDER BY created_at DESC LIMIT $1", limit
    )
    return [dict(row) for row in rows]


# --- reklama banneri ko'rishlar soni -----------------------------------------

async def increment_ad_views(slide: int) -> int:
    return await _get_pool().fetchval(
        """INSERT INTO ad_stats (slide, views) VALUES ($1, 1)
           ON CONFLICT (slide) DO UPDATE SET views = ad_stats.views + 1
           RETURNING views""",
        slide,
    )


async def count_new_donations_last_24h() -> int:
    return await _get_pool().fetchval(
        "SELECT COUNT(*) FROM donations WHERE created_at > now() - interval '24 hours'"
    )


# --- "Reklama berish" reyting/taklif tizimi ----------------------------------

async def get_ad_bids_ranked() -> list[dict[str, Any]]:
    """Faqat to'lovi tasdiqlangan takliflar reytingda ko'rinadi."""
    rows = await _get_pool().fetch(
        "SELECT * FROM ad_bids WHERE status = 'approved' ORDER BY bid_amount DESC, created_at ASC"
    )
    return [dict(row) for row in rows]


async def get_ad_bid(bid_id: int) -> Optional[dict[str, Any]]:
    row = await _get_pool().fetchrow("SELECT * FROM ad_bids WHERE id = $1", bid_id)
    return dict(row) if row else None


async def create_ad_payment_new(
    telegram_id: int, brand_name: str, url: str, bid_amount: int,
    platform: Optional[str], photo_url: Optional[str],
    category: Optional[str], description: Optional[str],
) -> tuple[int, int]:
    """Yangi reklama: taklif 'pending' holatda yaratiladi va unga to'lov
    yozuvi bog'lanadi. (bid_id, payment_id) qaytaradi."""
    async with _get_pool().acquire() as conn:
        async with conn.transaction():
            bid_id = await conn.fetchval(
                """INSERT INTO ad_bids (telegram_id, brand_name, url, bid_amount, platform,
                                        photo_url, category, description, status)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'pending') RETURNING id""",
                telegram_id, brand_name, url, bid_amount, platform, photo_url, category, description,
            )
            payment_id = await conn.fetchval(
                """INSERT INTO ad_payments (bid_id, telegram_id, kind, amount)
                   VALUES ($1, $2, 'new', $3) RETURNING id""",
                bid_id, telegram_id, bid_amount,
            )
    return bid_id, payment_id


async def create_ad_payment_raise(bid_id: int, telegram_id: int, amount: int) -> int:
    """"Taklifni oshirish": summa admin tasdiqlagandan keyingina qo'shiladi."""
    return await _get_pool().fetchval(
        """INSERT INTO ad_payments (bid_id, telegram_id, kind, amount)
           VALUES ($1, $2, 'raise', $3) RETURNING id""",
        bid_id, telegram_id, amount,
    )


async def set_ad_payment_receipt(payment_id: int, receipt_file_id: str) -> None:
    await _get_pool().execute(
        "UPDATE ad_payments SET receipt_file_id = $2 WHERE id = $1", payment_id, receipt_file_id
    )


async def delete_ad_payment(payment_id: int) -> None:
    """Chek adminga yetib bormasa — yarim qolgan to'lov (va yangi reklama
    bo'lsa, uning 'pending' taklifi) o'chiriladi."""
    async with _get_pool().acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "DELETE FROM ad_payments WHERE id = $1 RETURNING bid_id, kind", payment_id
            )
            if row and row["kind"] == "new":
                await conn.execute(
                    "DELETE FROM ad_bids WHERE id = $1 AND status = 'pending'", row["bid_id"]
                )


async def decide_ad_payment(
    payment_id: int, approve: bool, admin_id: int, reject_reason: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Admin qarori — atomik: faqat 'pending' to'lov bir marta hal qilinadi.
    Tasdiqlansa yangi reklama reytingga chiqadi yoki taklif summasi oshadi.
    Allaqachon hal qilingan bo'lsa None qaytadi."""
    async with _get_pool().acquire() as conn:
        async with conn.transaction():
            payment = await conn.fetchrow(
                """UPDATE ad_payments SET status = $2, decided_by = $3, decided_at = now(),
                                          reject_reason = $4
                   WHERE id = $1 AND status = 'pending' RETURNING *""",
                payment_id, "approved" if approve else "rejected", admin_id,
                None if approve else reject_reason,
            )
            if not payment:
                return None
            if payment["kind"] == "new":
                await conn.execute(
                    "UPDATE ad_bids SET status = $2, created_at = now() WHERE id = $1",
                    payment["bid_id"], "approved" if approve else "rejected",
                )
            elif approve:
                await conn.execute(
                    "UPDATE ad_bids SET bid_amount = bid_amount + $2 WHERE id = $1",
                    payment["bid_id"], payment["amount"],
                )
            bid = await conn.fetchrow("SELECT * FROM ad_bids WHERE id = $1", payment["bid_id"])
    return {"payment": dict(payment), "bid": dict(bid) if bid else None}


async def get_ad_payment(payment_id: int) -> Optional[dict[str, Any]]:
    row = await _get_pool().fetchrow("SELECT * FROM ad_payments WHERE id = $1", payment_id)
    return dict(row) if row else None


async def get_pending_ad_payments(telegram_id: int) -> list[dict[str, Any]]:
    rows = await _get_pool().fetch(
        """SELECT p.id, p.kind, p.amount, p.bid_id, b.brand_name, b.bid_amount
           FROM ad_payments p JOIN ad_bids b ON b.id = p.bid_id
           WHERE p.telegram_id = $1 AND p.status = 'pending' AND p.receipt_file_id IS NOT NULL
           ORDER BY p.created_at DESC""",
        telegram_id,
    )
    return [dict(row) for row in rows]


async def get_recent_rejected_ad_payments(telegram_id: int) -> list[dict[str, Any]]:
    """Oxirgi 7 kunda rad etilgan, foydalanuvchi hali yopmagan to'lovlar —
    ilovada "Rad etildi · Sabab" bloki uchun."""
    rows = await _get_pool().fetch(
        """SELECT p.id, p.kind, p.amount, p.reject_reason, b.brand_name
           FROM ad_payments p JOIN ad_bids b ON b.id = p.bid_id
           WHERE p.telegram_id = $1 AND p.status = 'rejected' AND NOT p.rejection_seen
             AND p.decided_at > now() - interval '7 days'
           ORDER BY p.decided_at DESC
           LIMIT 5""",
        telegram_id,
    )
    return [dict(row) for row in rows]


async def dismiss_ad_payment_rejection(payment_id: int, telegram_id: int) -> bool:
    result = await _get_pool().execute(
        """UPDATE ad_payments SET rejection_seen = TRUE
           WHERE id = $1 AND telegram_id = $2 AND status = 'rejected'""",
        payment_id, telegram_id,
    )
    return result != "UPDATE 0"


async def increment_ad_bid_clicks(bid_id: int) -> Optional[int]:
    return await _get_pool().fetchval(
        "UPDATE ad_bids SET clicks = clicks + 1 WHERE id = $1 RETURNING clicks", bid_id
    )


async def claim_ad_bids_for_description(bid_ids: list[int]) -> list[dict[str, Any]]:
    """Tavsifi yo'q, hali tekshirilmagan takliflarni tekshirildi deb belgilab
    qaytaradi — bir vaqtda kelgan so'rovlar bir xil taklifni ikki marta olmaydi."""
    rows = await _get_pool().fetch(
        """UPDATE ad_bids SET description_checked = TRUE
           WHERE id = ANY($1::int[]) AND description IS NULL AND NOT description_checked
           RETURNING id, url, photo_url""",
        bid_ids,
    )
    return [dict(row) for row in rows]


async def fill_ad_bid_preview(bid_id: int, description: Optional[str], photo_url: Optional[str]) -> None:
    await _get_pool().execute(
        """UPDATE ad_bids
           SET description = COALESCE(description, $2), photo_url = COALESCE(photo_url, $3)
           WHERE id = $1""",
        bid_id, description, photo_url,
    )


# --- ehsonlarni yoqtirish (like) ----------------------------------------------

async def toggle_donation_like(donation_id: int, telegram_id: int) -> tuple[bool, int]:
    pool = _get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            deleted = await conn.execute(
                "DELETE FROM donation_likes WHERE donation_id = $1 AND telegram_id = $2",
                donation_id,
                telegram_id,
            )
            if deleted == "DELETE 0":
                await conn.execute(
                    """INSERT INTO donation_likes (donation_id, telegram_id)
                       VALUES ($1, $2) ON CONFLICT DO NOTHING""",
                    donation_id,
                    telegram_id,
                )
                liked = True
            else:
                liked = False
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM donation_likes WHERE donation_id = $1", donation_id
            )
            return liked, count


async def get_like_info(donation_ids: list[int], telegram_id: int) -> dict[int, dict[str, Any]]:
    if not donation_ids:
        return {}
    rows = await _get_pool().fetch(
        """SELECT donation_id, COUNT(*) AS count,
                  COUNT(*) FILTER (WHERE telegram_id = $2) > 0 AS liked
           FROM donation_likes WHERE donation_id = ANY($1::int[])
           GROUP BY donation_id""",
        donation_ids,
        telegram_id,
    )
    return {row["donation_id"]: {"count": row["count"], "liked": row["liked"]} for row in rows}


# --- ehsonlarni ulashish (share) ---------------------------------------------

async def increment_donation_share(donation_id: int) -> int:
    return await _get_pool().fetchval(
        "UPDATE donations SET share_count = share_count + 1 WHERE id = $1 RETURNING share_count",
        donation_id,
    )
