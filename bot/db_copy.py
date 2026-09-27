"""Bir martalik ko'chirish: eski bazadagi barcha ma'lumotlar yangi bazaga.

Serverni boshqa mintaqaga (masalan Frankfurt) ko'chirganda Render'da
MIGRATE_FROM_DATABASE_URL ga eski baza manzili qo'yiladi. Bot ishga tushganda
eski bazadagi hamma jadval yangi bazaga nusxalanadi va yangi bazada belgi
(db_migrations jadvali) qoldiriladi — keyingi ishga tushishlarda ko'chirish
takrorlanmaydi. Yangi bazada ko'chirishdan oldin paydo bo'lgan yozuvlar
(masalan manzil almashtirilgandan keyingi bir necha daqiqada) eski
ma'lumotlar bilan almashtiriladi. Tugagach o'zgaruvchini o'chirib qo'yish kifoya.
"""
import io
import logging
import re

from urllib.parse import urlsplit

import asyncpg

logger = logging.getLogger(__name__)


def _clean_url(url: str) -> str:
    # asyncpg channel_binding parametrini tanimaydi (Neon manzilida bo'ladi).
    url = re.sub(r"([?&])channel_binding=[^&]*&?", r"\1", url.strip())
    return url.rstrip("?&")


async def _tables_in_fk_order(conn: asyncpg.Connection) -> list[str]:
    """Jadvallar tashqi kalitlar tartibida: avval users, keyin donations..."""
    tables = [r["table_name"] for r in await conn.fetch(
        """SELECT table_name FROM information_schema.tables
           WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
           ORDER BY table_name"""
    )]
    deps = {t: set() for t in tables}
    for r in await conn.fetch(
        """SELECT tc.table_name AS child, ccu.table_name AS parent
           FROM information_schema.table_constraints tc
           JOIN information_schema.constraint_column_usage ccu
             ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
           WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'"""
    ):
        if r["child"] in deps and r["parent"] != r["child"]:
            deps[r["child"]].add(r["parent"])
    ordered: list[str] = []
    while deps:
        ready = sorted(t for t, parents in deps.items() if not parents - set(ordered))
        if not ready:  # aylanma bog'liqlik — qolganini alifbo tartibida
            ready = sorted(deps)
        for t in ready:
            ordered.append(t)
            del deps[t]
    return ordered


async def _columns(conn: asyncpg.Connection, table: str) -> list[str]:
    return [r["column_name"] for r in await conn.fetch(
        """SELECT column_name FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = $1 ORDER BY ordinal_position""",
        table,
    )]


def _same_database(url_a: str, url_b: str) -> bool:
    a, b = urlsplit(url_a), urlsplit(url_b)
    return (a.hostname, a.port, a.path) == (b.hostname, b.port, b.path)


async def copy_database(old_url: str, new_url: str, new: asyncpg.Connection) -> None:
    old_url = _clean_url(old_url)
    if _same_database(old_url, _clean_url(new_url)):
        logger.warning("MIGRATE_FROM_DATABASE_URL DATABASE_URL bilan bir xil — ko'chirish o'tkazib yuborildi.")
        return
    await new.execute(
        """CREATE TABLE IF NOT EXISTS db_migrations (
               id SERIAL PRIMARY KEY, done_at TIMESTAMPTZ NOT NULL DEFAULT now())"""
    )
    if await new.fetchval("SELECT EXISTS (SELECT 1 FROM db_migrations)"):
        logger.info("Ko'chirish avval bajarilgan — o'tkazib yuborildi. "
                    "MIGRATE_FROM_DATABASE_URL ni o'chirib qo'yishingiz mumkin.")
        return
    old = await asyncpg.connect(old_url, timeout=60)
    try:
        new_tables = set(await _tables_in_fk_order(new))
        plan = []
        for table in await _tables_in_fk_order(old):
            if table not in new_tables or table == "db_migrations":
                continue
            new_cols = set(await _columns(new, table))
            cols = [c for c in await _columns(old, table) if c in new_cols]
            if cols:
                plan.append((table, cols))
        async with new.transaction():
            # Yangi bazadagi mavjud yozuvlar eski ma'lumotlar bilan almashtiriladi
            # (hammasi birga — tashqi kalitlar xalaqit bermaydi).
            await new.execute("TRUNCATE " + ", ".join(f'"{t}"' for t, _ in plan) + " CASCADE")
            for table, cols in plan:
                buf = io.BytesIO()
                await old.copy_from_table(table, columns=cols, output=buf, format="binary")
                buf.seek(0)
                await new.copy_to_table(table, columns=cols, source=buf, format="binary")
                count = await new.fetchval(f'SELECT COUNT(*) FROM "{table}"')
                logger.info("Ko'chirildi: %s — %s ta yozuv", table, count)
            # SERIAL hisoblagichlari eng katta id'dan davom etsin.
            for r in await new.fetch(
                """SELECT table_name, column_name,
                          pg_get_serial_sequence(quote_ident(table_name), column_name) AS seq
                   FROM information_schema.columns
                   WHERE table_schema = 'public' AND column_default LIKE 'nextval(%'"""
            ):
                if r["seq"]:
                    await new.execute(
                        f"""SELECT setval($1, COALESCE((SELECT MAX("{r['column_name']}")
                                                        FROM "{r['table_name']}"), 0) + 1, false)""",
                        r["seq"],
                    )
            await new.execute("INSERT INTO db_migrations DEFAULT VALUES")
        logger.info("✅ Eski bazadan ko'chirish tugadi.")
    finally:
        await old.close()
