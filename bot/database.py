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
    description TEXT,
    status TEXT NOT NULL DEFAULT 'available',
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
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    shipped_at TIMESTAMPTZ,
    received_at TIMESTAMPTZ
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
    donor_id: int, category: str, photo_file_id: str, description: str
) -> int:
    return await _get_pool().fetchval(
        """INSERT INTO donations (donor_id, category, photo_file_id, description, status)
           VALUES ($1, $2, $3, $4, 'available') RETURNING id""",
        donor_id,
        category,
        photo_file_id,
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
        "SELECT * FROM donations WHERE donor_id = $1 ORDER BY created_at DESC", donor_id
    )
    return [dict(row) for row in rows]


async def set_donation_status(donation_id: int, status: str) -> None:
    await _get_pool().execute(
        "UPDATE donations SET status = $1 WHERE id = $2", status, donation_id
    )


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
        "SELECT * FROM reservations WHERE needy_id = $1 ORDER BY created_at DESC",
        needy_id,
    )
    return [dict(row) for row in rows]


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


async def get_category_stats() -> dict[str, dict[str, int]]:
    rows = await _get_pool().fetch(
        """SELECT category,
                  COUNT(*) AS total,
                  COUNT(*) FILTER (WHERE status = 'received') AS delivered
           FROM donations
           GROUP BY category"""
    )
    return {row["category"]: {"total": row["total"], "delivered": row["delivered"]} for row in rows}


async def get_recent_donations(limit: int = 10) -> list[dict[str, Any]]:
    rows = await _get_pool().fetch(
        "SELECT * FROM donations ORDER BY created_at DESC LIMIT $1", limit
    )
    return [dict(row) for row in rows]
