import logging
from datetime import datetime, timedelta, date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot

import database as db

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def send_reminders(bot: Bot) -> None:
    """Check for bookings that need reminders (24h and 2h before)."""
    now = datetime.now()

    # 24h reminder: check bookings for tomorrow at roughly the same time
    reminder_24h = now + timedelta(hours=24)
    target_date_24 = reminder_24h.date().isoformat()

    # 2h reminder: check bookings for today in ~2 hours
    reminder_2h = now + timedelta(hours=2)
    target_date_2 = reminder_2h.date().isoformat()

    # Process 24h reminders
    bookings_24 = await db.get_confirmed_bookings_for_date(target_date_24)
    for b in bookings_24:
        try:
            booking_time = datetime.strptime(b["time"], "%H:%M")
            booking_dt = datetime.combine(reminder_24h.date(), booking_time.time())
            diff = abs((booking_dt - reminder_24h).total_seconds())
            # Send if within 30-minute window (scheduler runs every 30 min)
            if diff <= 1800:
                d = date.fromisoformat(b["date"])
                from keyboards.inline import WEEKDAYS_RU, MONTHS_RU
                wd = WEEKDAYS_RU[d.weekday()]
                month = MONTHS_RU[d.month]
                await bot.send_message(
                    b["user_id"],
                    f"🔔 <b>Напоминание: завтра у вас запись!</b>\n\n"
                    f"📋 Услуга: <b>{b['service_name']}</b>\n"
                    f"👤 Мастер: <b>{b['master_name']}</b>\n"
                    f"📅 Дата: <b>{wd}, {d.day} {month}</b>\n"
                    f"🕐 Время: <b>{b['time']}</b>\n\n"
                    f"Ждём вас!",
                    parse_mode="HTML",
                )
                logger.info("Sent 24h reminder to user %s for booking #%s", b["user_id"], b["id"])
        except Exception as e:
            logger.warning("Failed to send 24h reminder for booking #%s: %s", b["id"], e)

    # Process 2h reminders
    bookings_2 = await db.get_confirmed_bookings_for_date(target_date_2)
    for b in bookings_2:
        try:
            booking_time = datetime.strptime(b["time"], "%H:%M")
            booking_dt = datetime.combine(reminder_2h.date(), booking_time.time())
            diff = abs((booking_dt - reminder_2h).total_seconds())
            # Send if within 30-minute window
            if diff <= 1800:
                d = date.fromisoformat(b["date"])
                from keyboards.inline import WEEKDAYS_RU, MONTHS_RU
                wd = WEEKDAYS_RU[d.weekday()]
                month = MONTHS_RU[d.month]
                await bot.send_message(
                    b["user_id"],
                    f"⏰ <b>Напоминание: через 2 часа у вас запись!</b>\n\n"
                    f"📋 Услуга: <b>{b['service_name']}</b>\n"
                    f"👤 Мастер: <b>{b['master_name']}</b>\n"
                    f"📅 Дата: <b>{wd}, {d.day} {month}</b>\n"
                    f"🕐 Время: <b>{b['time']}</b>\n\n"
                    f"Не опаздывайте!",
                    parse_mode="HTML",
                )
                logger.info("Sent 2h reminder to user %s for booking #%s", b["user_id"], b["id"])
        except Exception as e:
            logger.warning("Failed to send 2h reminder for booking #%s: %s", b["id"], e)


def setup_scheduler(bot: Bot) -> None:
    """Configure and start the APScheduler."""
    scheduler.add_job(
        send_reminders,
        "interval",
        minutes=30,
        args=[bot],
        id="reminders_job",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started: reminders every 30 minutes")
