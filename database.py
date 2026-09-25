import aiosqlite
import logging
from datetime import date, datetime

DB_PATH = "bookmaster.db"
logger = logging.getLogger(__name__)


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA foreign_keys=ON;")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL DEFAULT 60,
                price REAL NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS masters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                specialization TEXT NOT NULL DEFAULT '',
                is_active INTEGER NOT NULL DEFAULT 1
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS master_services (
                master_id INTEGER NOT NULL,
                service_id INTEGER NOT NULL,
                PRIMARY KEY (master_id, service_id),
                FOREIGN KEY (master_id) REFERENCES masters(id) ON DELETE CASCADE,
                FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS schedule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                master_id INTEGER NOT NULL,
                weekday INTEGER NOT NULL CHECK(weekday BETWEEN 0 AND 6),
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                FOREIGN KEY (master_id) REFERENCES masters(id) ON DELETE CASCADE
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT DEFAULT '',
                master_id INTEGER NOT NULL,
                service_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'confirmed',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (master_id) REFERENCES masters(id),
                FOREIGN KEY (service_id) REFERENCES services(id)
            )
        """)

        # ──────────────── Reviews ────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_id INTEGER NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                master_id INTEGER NOT NULL,
                rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
                comment TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (booking_id) REFERENCES bookings(id),
                FOREIGN KEY (master_id) REFERENCES masters(id)
            )
        """)

        # ──────────────── Loyalty ────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS loyalty (
                user_id INTEGER PRIMARY KEY,
                total_visits INTEGER NOT NULL DEFAULT 0,
                discount_available INTEGER NOT NULL DEFAULT 0
            )
        """)

        # ──────────────── Days off ────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS days_off (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                master_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                reason TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (master_id) REFERENCES masters(id) ON DELETE CASCADE
            )
        """)

        # ──────────────── Client notes ────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS client_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                note TEXT NOT NULL,
                created_by INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        await db.commit()
        logger.info("Database initialized successfully")


# ──────────────────── Services ────────────────────

async def add_service(name: str, duration: int, price: float) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO services (name, duration_minutes, price) VALUES (?, ?, ?)",
            (name, duration, price),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore


async def get_active_services() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            "SELECT * FROM services WHERE is_active = 1"
        )
        return [dict(r) for r in rows]


async def get_all_services() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall("SELECT * FROM services ORDER BY id")
        return [dict(r) for r in rows]


async def get_service(service_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM services WHERE id = ?", (service_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def toggle_service(service_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE services SET is_active = 1 - is_active WHERE id = ?",
            (service_id,),
        )
        await db.commit()


async def delete_service(service_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM services WHERE id = ?", (service_id,))
        await db.commit()


async def search_services(query: str) -> list[dict]:
    """Fuzzy search services by name (case-insensitive partial match)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            "SELECT * FROM services WHERE is_active = 1 AND LOWER(name) LIKE ?",
            (f"%{query.lower()}%",),
        )
        return [dict(r) for r in rows]


# ──────────────────── Masters ────────────────────

async def add_master(name: str, specialization: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO masters (name, specialization) VALUES (?, ?)",
            (name, specialization),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore


async def get_active_masters() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            "SELECT * FROM masters WHERE is_active = 1"
        )
        return [dict(r) for r in rows]


async def get_all_masters() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall("SELECT * FROM masters ORDER BY id")
        return [dict(r) for r in rows]


async def get_master(master_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM masters WHERE id = ?", (master_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def toggle_master(master_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE masters SET is_active = 1 - is_active WHERE id = ?",
            (master_id,),
        )
        await db.commit()


async def delete_master(master_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM masters WHERE id = ?", (master_id,))
        await db.commit()


# ──────────────────── Master ↔ Services ────────────────────

async def link_master_service(master_id: int, service_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO master_services (master_id, service_id) VALUES (?, ?)",
            (master_id, service_id),
        )
        await db.commit()


async def unlink_master_service(master_id: int, service_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM master_services WHERE master_id = ? AND service_id = ?",
            (master_id, service_id),
        )
        await db.commit()


async def get_masters_for_service(service_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            """
            SELECT m.* FROM masters m
            JOIN master_services ms ON m.id = ms.master_id
            WHERE ms.service_id = ? AND m.is_active = 1
            """,
            (service_id,),
        )
        return [dict(r) for r in rows]


async def get_services_for_master(master_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            """
            SELECT s.* FROM services s
            JOIN master_services ms ON s.id = ms.service_id
            WHERE ms.master_id = ? AND s.is_active = 1
            """,
            (master_id,),
        )
        return [dict(r) for r in rows]


# ──────────────────── Schedule ────────────────────

async def set_schedule(master_id: int, weekday: int, start_time: str, end_time: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM schedule WHERE master_id = ? AND weekday = ?",
            (master_id, weekday),
        )
        await db.execute(
            "INSERT INTO schedule (master_id, weekday, start_time, end_time) VALUES (?, ?, ?, ?)",
            (master_id, weekday, start_time, end_time),
        )
        await db.commit()


async def get_schedule(master_id: int, weekday: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM schedule WHERE master_id = ? AND weekday = ?",
            (master_id, weekday),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_full_schedule(master_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            "SELECT * FROM schedule WHERE master_id = ? ORDER BY weekday",
            (master_id,),
        )
        return [dict(r) for r in rows]


async def delete_schedule(master_id: int, weekday: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM schedule WHERE master_id = ? AND weekday = ?",
            (master_id, weekday),
        )
        await db.commit()


# ──────────────────── Bookings ────────────────────

async def create_booking(
    user_id: int,
    username: str,
    master_id: int,
    service_id: int,
    book_date: str,
    book_time: str,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO bookings (user_id, username, master_id, service_id, date, time, status)
            VALUES (?, ?, ?, ?, ?, ?, 'confirmed')
            """,
            (user_id, username, master_id, service_id, book_date, book_time),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore


async def get_bookings_for_date(master_id: int, book_date: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            """
            SELECT b.*, s.duration_minutes FROM bookings b
            JOIN services s ON b.service_id = s.id
            WHERE b.master_id = ? AND b.date = ? AND b.status != 'cancelled'
            """,
            (master_id, book_date),
        )
        return [dict(r) for r in rows]


async def get_user_bookings(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            """
            SELECT b.*, s.name as service_name, m.name as master_name,
                   s.duration_minutes, s.price
            FROM bookings b
            JOIN services s ON b.service_id = s.id
            JOIN masters m ON b.master_id = m.id
            WHERE b.user_id = ?
            ORDER BY b.date DESC, b.time DESC
            """,
            (user_id,),
        )
        return [dict(r) for r in rows]


async def get_all_bookings(status: str | None = None) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if status:
            rows = await db.execute_fetchall(
                """
                SELECT b.*, s.name as service_name, m.name as master_name,
                       s.duration_minutes, s.price
                FROM bookings b
                JOIN services s ON b.service_id = s.id
                JOIN masters m ON b.master_id = m.id
                WHERE b.status = ?
                ORDER BY b.date DESC, b.time DESC
                """,
                (status,),
            )
        else:
            rows = await db.execute_fetchall(
                """
                SELECT b.*, s.name as service_name, m.name as master_name,
                       s.duration_minutes, s.price
                FROM bookings b
                JOIN services s ON b.service_id = s.id
                JOIN masters m ON b.master_id = m.id
                ORDER BY b.date DESC, b.time DESC
                """
            )
        return [dict(r) for r in rows]


async def get_bookings_in_date_range(date_from: str, date_to: str) -> list[dict]:
    """Get all bookings within a date range (inclusive)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            """
            SELECT b.*, s.name as service_name, m.name as master_name,
                   s.duration_minutes, s.price
            FROM bookings b
            JOIN services s ON b.service_id = s.id
            JOIN masters m ON b.master_id = m.id
            WHERE b.date >= ? AND b.date <= ?
            ORDER BY b.date, b.time
            """,
            (date_from, date_to),
        )
        return [dict(r) for r in rows]


async def get_master_bookings_in_range(master_id: int, date_from: str, date_to: str) -> list[dict]:
    """Get bookings for a specific master in a date range."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            """
            SELECT b.*, s.name as service_name, m.name as master_name,
                   s.duration_minutes, s.price
            FROM bookings b
            JOIN services s ON b.service_id = s.id
            JOIN masters m ON b.master_id = m.id
            WHERE b.master_id = ? AND b.date >= ? AND b.date <= ?
            ORDER BY b.date, b.time
            """,
            (master_id, date_from, date_to),
        )
        return [dict(r) for r in rows]


async def get_booking(booking_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT b.*, s.name as service_name, m.name as master_name,
                   s.duration_minutes, s.price
            FROM bookings b
            JOIN services s ON b.service_id = s.id
            JOIN masters m ON b.master_id = m.id
            WHERE b.id = ?
            """,
            (booking_id,),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def update_booking_status(booking_id: int, status: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE bookings SET status = ? WHERE id = ?",
            (status, booking_id),
        )
        await db.commit()


async def has_booking_today(user_id: int, service_id: int, book_date: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT COUNT(*) FROM bookings
            WHERE user_id = ? AND service_id = ? AND date = ? AND status != 'cancelled'
            """,
            (user_id, service_id, book_date),
        ) as cur:
            row = await cur.fetchone()
            return row[0] > 0 if row else False


async def get_upcoming_bookings_for_reminder(target_time_from: str, target_time_to: str, target_date: str) -> list[dict]:
    """Get confirmed bookings for a specific date within a time window for reminders."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            """
            SELECT b.*, s.name as service_name, m.name as master_name,
                   s.duration_minutes, s.price
            FROM bookings b
            JOIN services s ON b.service_id = s.id
            JOIN masters m ON b.master_id = m.id
            WHERE b.date = ? AND b.status = 'confirmed'
            ORDER BY b.time
            """,
            (target_date,),
        )
        return [dict(r) for r in rows]


async def get_confirmed_bookings_for_date(target_date: str) -> list[dict]:
    """Get all confirmed bookings for a given date."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            """
            SELECT b.*, s.name as service_name, m.name as master_name,
                   s.duration_minutes, s.price
            FROM bookings b
            JOIN services s ON b.service_id = s.id
            JOIN masters m ON b.master_id = m.id
            WHERE b.date = ? AND b.status = 'confirmed'
            ORDER BY b.time
            """,
            (target_date,),
        )
        return [dict(r) for r in rows]


# ──────────────────── Reviews ────────────────────

async def create_review(booking_id: int, user_id: int, master_id: int, rating: int, comment: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO reviews (booking_id, user_id, master_id, rating, comment)
            VALUES (?, ?, ?, ?, ?)
            """,
            (booking_id, user_id, master_id, rating, comment),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore


async def get_review_by_booking(booking_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM reviews WHERE booking_id = ?", (booking_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_reviews_for_master(master_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            """
            SELECT r.*, b.date, b.time, s.name as service_name
            FROM reviews r
            JOIN bookings b ON r.booking_id = b.id
            JOIN services s ON b.service_id = s.id
            WHERE r.master_id = ?
            ORDER BY r.created_at DESC
            """,
            (master_id,),
        )
        return [dict(r) for r in rows]


async def get_master_avg_rating(master_id: int) -> float | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT AVG(rating) FROM reviews WHERE master_id = ?", (master_id,)
        ) as cur:
            row = await cur.fetchone()
            return round(row[0], 1) if row and row[0] is not None else None


async def get_all_masters_avg_ratings() -> dict[int, float]:
    """Returns {master_id: avg_rating} for all masters that have reviews."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            "SELECT master_id, AVG(rating) as avg_rating FROM reviews GROUP BY master_id"
        )
        return {r["master_id"]: round(r["avg_rating"], 1) for r in rows}


# ──────────────────── Loyalty ────────────────────

async def get_loyalty(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM loyalty WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            if row:
                return dict(row)
            # Create new record
            await db.execute(
                "INSERT INTO loyalty (user_id, total_visits, discount_available) VALUES (?, 0, 0)",
                (user_id,),
            )
            await db.commit()
            return {"user_id": user_id, "total_visits": 0, "discount_available": 0}


async def increment_loyalty(user_id: int, every_n: int = 5) -> dict:
    """Increment visits counter and check if discount should be awarded."""
    loyalty = await get_loyalty(user_id)
    new_visits = loyalty["total_visits"] + 1
    discount = 1 if new_visits % every_n == 0 else loyalty["discount_available"]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE loyalty SET total_visits = ?, discount_available = ? WHERE user_id = ?",
            (new_visits, discount, user_id),
        )
        await db.commit()
    return {"user_id": user_id, "total_visits": new_visits, "discount_available": discount}


async def use_discount(user_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE loyalty SET discount_available = 0 WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()


# ──────────────────── Days off ────────────────────

async def add_day_off(master_id: int, off_date: str, reason: str = "") -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO days_off (master_id, date, reason) VALUES (?, ?, ?)",
            (master_id, off_date, reason),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore


async def get_days_off(master_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            "SELECT * FROM days_off WHERE master_id = ? AND date >= date('now') ORDER BY date",
            (master_id,),
        )
        return [dict(r) for r in rows]


async def is_day_off(master_id: int, check_date: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM days_off WHERE master_id = ? AND date = ?",
            (master_id, check_date),
        ) as cur:
            row = await cur.fetchone()
            return row[0] > 0 if row else False


async def delete_day_off(day_off_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM days_off WHERE id = ?", (day_off_id,))
        await db.commit()


# ──────────────────── Client notes ────────────────────

async def add_client_note(user_id: int, note: str, created_by: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO client_notes (user_id, note, created_by) VALUES (?, ?, ?)",
            (user_id, note, created_by),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore


async def get_client_notes(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            "SELECT * FROM client_notes WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        )
        return [dict(r) for r in rows]


async def delete_client_note(note_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM client_notes WHERE id = ?", (note_id,))
        await db.commit()


# ──────────────────── Analytics ────────────────────

async def get_stats_bookings_month(year: int, month: int) -> dict:
    """Stats for a given month: total, completed, cancelled, revenue."""
    month_str = f"{year}-{month:02d}"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            "SELECT COUNT(*) as cnt FROM bookings WHERE date LIKE ?",
            (f"{month_str}%",),
        ) as cur:
            total = (await cur.fetchone())["cnt"]

        async with db.execute(
            "SELECT COUNT(*) as cnt FROM bookings WHERE date LIKE ? AND status = 'completed'",
            (f"{month_str}%",),
        ) as cur:
            completed = (await cur.fetchone())["cnt"]

        async with db.execute(
            "SELECT COUNT(*) as cnt FROM bookings WHERE date LIKE ? AND status = 'cancelled'",
            (f"{month_str}%",),
        ) as cur:
            cancelled = (await cur.fetchone())["cnt"]

        async with db.execute(
            """
            SELECT COALESCE(SUM(s.price), 0) as revenue
            FROM bookings b
            JOIN services s ON b.service_id = s.id
            WHERE b.date LIKE ? AND b.status = 'completed'
            """,
            (f"{month_str}%",),
        ) as cur:
            revenue = (await cur.fetchone())["revenue"]

    return {
        "total": total,
        "completed": completed,
        "cancelled": cancelled,
        "revenue": revenue,
    }


async def get_popular_services(limit: int = 5) -> list[dict]:
    """Top N most booked services (completed only)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            """
            SELECT s.name, COUNT(*) as cnt
            FROM bookings b
            JOIN services s ON b.service_id = s.id
            WHERE b.status = 'completed'
            GROUP BY b.service_id
            ORDER BY cnt DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(r) for r in rows]


async def get_busiest_weekdays() -> list[dict]:
    """Weekday distribution of all non-cancelled bookings."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            """
            SELECT
                CAST(strftime('%w', date) AS INTEGER) as weekday_num,
                COUNT(*) as cnt
            FROM bookings
            WHERE status != 'cancelled'
            GROUP BY weekday_num
            ORDER BY cnt DESC
            """
        )
        return [dict(r) for r in rows]


async def get_master_utilization(year: int, month: int) -> list[dict]:
    """How many completed bookings per master this month."""
    month_str = f"{year}-{month:02d}"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            """
            SELECT m.name, COUNT(*) as cnt
            FROM bookings b
            JOIN masters m ON b.master_id = m.id
            WHERE b.date LIKE ? AND b.status = 'completed'
            GROUP BY b.master_id
            ORDER BY cnt DESC
            """,
            (f"{month_str}%",),
        )
        return [dict(r) for r in rows]


async def get_user_profile_stats(user_id: int) -> dict:
    """User profile stats: total bookings, upcoming, favorite master."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Total bookings
        async with db.execute(
            "SELECT COUNT(*) as cnt FROM bookings WHERE user_id = ? AND status != 'cancelled'",
            (user_id,),
        ) as cur:
            total = (await cur.fetchone())["cnt"]

        # Upcoming
        today = date.today().isoformat()
        async with db.execute(
            "SELECT COUNT(*) as cnt FROM bookings WHERE user_id = ? AND status = 'confirmed' AND date >= ?",
            (user_id, today),
        ) as cur:
            upcoming = (await cur.fetchone())["cnt"]

        # Favorite master
        async with db.execute(
            """
            SELECT m.name, COUNT(*) as cnt
            FROM bookings b
            JOIN masters m ON b.master_id = m.id
            WHERE b.user_id = ? AND b.status != 'cancelled'
            GROUP BY b.master_id
            ORDER BY cnt DESC LIMIT 1
            """,
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
            fav_master = row["name"] if row else None

    return {
        "total_bookings": total,
        "upcoming": upcoming,
        "favorite_master": fav_master,
    }
