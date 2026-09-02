import os
from datetime import datetime, timezone
from typing import Any, Optional

import aiosqlite

from bot.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    language TEXT,
    role TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS donations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    donor_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    photo_file_id TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'available',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (donor_id) REFERENCES users(telegram_id)
);

CREATE TABLE IF NOT EXISTS reservations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    donation_id INTEGER NOT NULL,
    needy_id INTEGER NOT NULL,
    full_name TEXT NOT NULL,
    address TEXT NOT NULL,
    phone TEXT NOT NULL,
    receipt_photo_file_id TEXT,
    receipt_note TEXT,
    dua_text TEXT,
    status TEXT NOT NULL DEFAULT 'reserved',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    shipped_at TEXT,
    received_at TEXT,
    FOREIGN KEY (donation_id) REFERENCES donations(id),
    FOREIGN KEY (needy_id) REFERENCES users(telegram_id)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


async def _row_to_dict(cursor: aiosqlite.Cursor, row) -> Optional[dict[str, Any]]:
    if row is None:
        return None
    columns = [c[0] for c in cursor.description]
    return dict(zip(columns, row))


# --- users -----------------------------------------------------------------

async def get_user(telegram_id: int) -> Optional[dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        row = await cursor.fetchone()
        return await _row_to_dict(cursor, row)


async def create_user_if_missing(telegram_id: int) -> dict[str, Any]:
    user = await get_user(telegram_id)
    if user:
        return user
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users (telegram_id, created_at) VALUES (?, ?)",
            (telegram_id, _now()),
        )
        await db.commit()
    return await get_user(telegram_id)


async def set_user_language(telegram_id: int, language: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET language = ? WHERE telegram_id = ?",
            (language, telegram_id),
        )
        await db.commit()


async def set_user_role(telegram_id: int, role: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET role = ? WHERE telegram_id = ?",
            (role, telegram_id),
        )
        await db.commit()


# --- donations ---------------------------------------------------------------

async def create_donation(
    donor_id: int, category: str, photo_file_id: str, description: str
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO donations (donor_id, category, photo_file_id, description, status, created_at)
               VALUES (?, ?, ?, ?, 'available', ?)""",
            (donor_id, category, photo_file_id, description, _now()),
        )
        await db.commit()
        return cursor.lastrowid


async def get_donation(donation_id: int) -> Optional[dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM donations WHERE id = ?", (donation_id,)
        )
        row = await cursor.fetchone()
        return await _row_to_dict(cursor, row)


async def get_available_donations(category: str) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT * FROM donations WHERE category = ? AND status = 'available'
               ORDER BY created_at DESC""",
            (category,),
        )
        rows = await cursor.fetchall()
        columns = [c[0] for c in cursor.description]
        return [dict(zip(columns, row)) for row in rows]


async def get_donations_by_donor(donor_id: int) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM donations WHERE donor_id = ? ORDER BY created_at DESC",
            (donor_id,),
        )
        rows = await cursor.fetchall()
        columns = [c[0] for c in cursor.description]
        return [dict(zip(columns, row)) for row in rows]


async def set_donation_status(donation_id: int, status: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE donations SET status = ? WHERE id = ?", (status, donation_id)
        )
        await db.commit()


# --- reservations -------------------------------------------------------------

async def create_reservation(
    donation_id: int, needy_id: int, full_name: str, address: str, phone: str
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO reservations
               (donation_id, needy_id, full_name, address, phone, status, created_at)
               VALUES (?, ?, ?, ?, ?, 'reserved', ?)""",
            (donation_id, needy_id, full_name, address, phone, _now()),
        )
        await db.commit()
        return cursor.lastrowid


async def get_reservation(reservation_id: int) -> Optional[dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM reservations WHERE id = ?", (reservation_id,)
        )
        row = await cursor.fetchone()
        return await _row_to_dict(cursor, row)


async def get_active_reservation_for_donation(
    donation_id: int,
) -> Optional[dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT * FROM reservations WHERE donation_id = ?
               ORDER BY created_at DESC LIMIT 1""",
            (donation_id,),
        )
        row = await cursor.fetchone()
        return await _row_to_dict(cursor, row)


async def get_reservations_by_needy(needy_id: int) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM reservations WHERE needy_id = ? ORDER BY created_at DESC",
            (needy_id,),
        )
        rows = await cursor.fetchall()
        columns = [c[0] for c in cursor.description]
        return [dict(zip(columns, row)) for row in rows]


async def set_reservation_shipped(
    reservation_id: int, receipt_photo_file_id: str, receipt_note: Optional[str]
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE reservations
               SET status = 'shipped', receipt_photo_file_id = ?, receipt_note = ?, shipped_at = ?
               WHERE id = ?""",
            (receipt_photo_file_id, receipt_note, _now(), reservation_id),
        )
        await db.commit()


async def set_reservation_received(reservation_id: int, dua_text: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE reservations
               SET status = 'received', dua_text = ?, received_at = ?
               WHERE id = ?""",
            (dua_text, _now(), reservation_id),
        )
        await db.commit()
