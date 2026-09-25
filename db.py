import aiosqlite

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS bookings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    client_name TEXT,
    phone       TEXT,
    service_id  TEXT NOT NULL,
    master_id   TEXT NOT NULL,
    day         TEXT NOT NULL,   -- YYYY-MM-DD
    start       TEXT NOT NULL,   -- HH:MM
    duration    INTEGER NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active',
    reminded    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_master_day ON bookings (master_id, day);
"""


def _connect():
    return aiosqlite.connect(DB_PATH)


async def init() -> None:
    async with _connect() as conn:
        await conn.executescript(SCHEMA)
        await conn.commit()


async def _fetch(sql: str, params: tuple = ()) -> list[aiosqlite.Row]:
    async with _connect() as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(sql, params) as cur:
            return list(await cur.fetchall())


async def busy_bookings(master_id: str, day: str) -> list[aiosqlite.Row]:
    return await _fetch(
        "SELECT start, duration FROM bookings WHERE master_id=? AND day=? AND status='active'",
        (master_id, day),
    )


async def add_booking(user_id: int, client_name: str, phone: str, service_id: str,
                      master_id: str, day: str, start: str, duration: int, reminded: bool) -> int:
    async with _connect() as conn:
        cur = await conn.execute(
            "INSERT INTO bookings (user_id, client_name, phone, service_id, master_id, day, start, duration, reminded) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, client_name, phone, service_id, master_id, day, start, duration, int(reminded)),
        )
        await conn.commit()
        return cur.lastrowid


async def get_booking(booking_id: int) -> aiosqlite.Row | None:
    rows = await _fetch("SELECT * FROM bookings WHERE id=?", (booking_id,))
    return rows[0] if rows else None


async def cancel_booking(booking_id: int) -> None:
    async with _connect() as conn:
        await conn.execute("UPDATE bookings SET status='cancelled' WHERE id=?", (booking_id,))
        await conn.commit()


async def user_upcoming(user_id: int, today: str, now_hhmm: str) -> list[aiosqlite.Row]:
    return await _fetch(
        "SELECT * FROM bookings WHERE user_id=? AND status='active' "
        "AND (day > ? OR (day = ? AND start >= ?)) ORDER BY day, start",
        (user_id, today, today, now_hhmm),
    )


async def bookings_between(day_from: str, day_to: str) -> list[aiosqlite.Row]:
    return await _fetch(
        "SELECT * FROM bookings WHERE status='active' AND day BETWEEN ? AND ? ORDER BY day, start",
        (day_from, day_to),
    )


async def not_reminded(day_from: str, day_to: str) -> list[aiosqlite.Row]:
    return await _fetch(
        "SELECT * FROM bookings WHERE status='active' AND reminded=0 AND day BETWEEN ? AND ?",
        (day_from, day_to),
    )


async def mark_reminded(booking_id: int) -> None:
    async with _connect() as conn:
        await conn.execute("UPDATE bookings SET reminded=1 WHERE id=?", (booking_id,))
        await conn.commit()
