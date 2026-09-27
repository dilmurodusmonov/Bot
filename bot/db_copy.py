"""Bir martalik ko'chirish: eski bazadagi barcha ma'lumotlar yangi bazaga.

Serverni boshqa mintaqaga (masalan Frankfurt) ko'chirganda Render'da
MIGRATE_FROM_DATABASE_URL ga eski baza manzili qo'yiladi. Bot ishga tushganda
yangi baza bo'sh bo'lsa, hamma jadvallar shu yerdan nusxalanadi. Yangi bazada
allaqachon foydalanuvchilar bo'lsa hech narsa qilinmaydi — qayta ishga
tushganda ma'lumot ikki marta yozilmaydi. Ko'chirish tugagach o'zgaruvchini
o'chirib qo'yish kifoya.
"""
import io
import logging
import re

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


async def copy_database(old_url: str, new: asyncpg.Connection) -> None:
    if await new.fetchval("SELECT EXISTS (SELECT 1 FROM users)"):
        logger.info("Ko'chirish o'tkazib yuborildi: yangi bazada ma'lumot bor. "
                    "MIGRATE_FROM_DATABASE_URL ni o'chirib qo'yishingiz mumkin.")
        return
    old = await asyncpg.connect(_clean_url(old_url), timeout=60)
    try:
        new_tables = set(await _tables_in_fk_order(new))
        async with new.transaction():
            for table in await _tables_in_fk_order(old):
                if table not in new_tables:
                    continue
                new_cols = set(await _columns(new, table))
                cols = [c for c in await _columns(old, table) if c in new_cols]
                if not cols:
                    continue
                # Jadval sxemasi yangi bazada bor, eski boshlang'ich yozuvlar
                # (bo'lsa) almashtiriladi.
                await new.execute(f'DELETE FROM "{table}"')
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
        logger.info("✅ Eski bazadan ko'chirish tugadi.")
    finally:
        await old.close()
