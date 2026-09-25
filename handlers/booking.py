import logging
from datetime import datetime, date, timedelta

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode

import database as db
from config import ADMIN_IDS, LOYALTY_EVERY_N, LOYALTY_DISCOUNT_PERCENT
from keyboards.inline import (
    services_kb, masters_kb, dates_kb,
    time_slots_kb, confirm_kb, WEEKDAYS_RU, MONTHS_RU,
)
from keyboards.reply import main_menu, cancel_kb

logger = logging.getLogger(__name__)
router = Router()


class BookingStates(StatesGroup):
    choosing_service = State()
    choosing_master = State()
    choosing_date = State()
    choosing_time = State()
    confirming = State()
    searching_service = State()


# ──────────────────── Helpers ────────────────────

def _generate_slots(start: str, end: str, duration: int, booked: list[dict]) -> list[str]:
    """Generate available time slots given schedule bounds and existing bookings."""
    fmt = "%H:%M"
    s = datetime.strptime(start, fmt)
    e = datetime.strptime(end, fmt)
    slots: list[str] = []

    while s + timedelta(minutes=duration) <= e:
        slot_start = s
        slot_end = s + timedelta(minutes=duration)
        conflict = False
        for b in booked:
            b_start = datetime.strptime(b["time"], fmt)
            b_end = b_start + timedelta(minutes=b["duration_minutes"])
            if slot_start < b_end and slot_end > b_start:
                conflict = True
                break
        if not conflict:
            slots.append(s.strftime(fmt))
        s += timedelta(minutes=30)  # slot step: 30 min

    return slots


# ──────────────────── Service Search ────────────────────

@router.message(F.text == "🔍 Поиск услуги")
@router.message(F.text == "/search")
async def search_start(message: Message, state: FSMContext) -> None:
    await state.set_state(BookingStates.searching_service)
    await message.answer(
        "🔍 <b>Поиск услуги</b>\n\n"
        "Введите название или часть названия услуги:",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_kb(),
    )


@router.message(BookingStates.searching_service)
async def search_process(message: Message, state: FSMContext) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Поиск отменён.", reply_markup=main_menu())
        return

    query = message.text.strip()  # type: ignore
    if len(query) < 2:
        await message.answer("Введите хотя бы 2 символа для поиска.")
        return

    results = await db.search_services(query)
    if not results:
        await message.answer(
            f"По запросу <b>«{query}»</b> ничего не найдено.\n"
            "Попробуйте другой запрос или нажмите ❌ Отмена.",
            parse_mode=ParseMode.HTML,
        )
        return

    await state.clear()
    await state.set_state(BookingStates.choosing_service)
    await message.answer(
        f"🔍 Найдено по запросу <b>«{query}»</b>:",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_kb(),
    )
    await message.answer(
        "Выберите услугу:",
        reply_markup=services_kb(results),
    )


# ──────────────────── Flow start ────────────────────

@router.message(F.text == "📋 Записаться")
async def start_booking(message: Message, state: FSMContext) -> None:
    services = await db.get_active_services()
    if not services:
        await message.answer("😔 Пока нет доступных услуг.", reply_markup=main_menu())
        return
    await state.set_state(BookingStates.choosing_service)
    await message.answer(
        "<b>Шаг 1/5 — Выберите услугу:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_kb(),
    )
    await message.answer(
        "Доступные услуги:",
        reply_markup=services_kb(services),
    )


@router.message(F.text == "❌ Отмена")
async def cancel_booking(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current is not None:
        await state.clear()
        await message.answer("❌ Запись отменена.", reply_markup=main_menu())
    else:
        await message.answer("Нечего отменять.", reply_markup=main_menu())


# ──────────────────── Step 1: Service ────────────────────

@router.callback_query(BookingStates.choosing_service, F.data.startswith("book_service:"))
async def pick_service(callback: CallbackQuery, state: FSMContext) -> None:
    service_id = int(callback.data.split(":")[1])  # type: ignore
    service = await db.get_service(service_id)
    if not service:
        await callback.answer("Услуга не найдена", show_alert=True)
        return

    masters = await db.get_masters_for_service(service_id)
    if not masters:
        await callback.answer("Нет мастеров для этой услуги", show_alert=True)
        return

    # Get ratings for masters
    ratings = await db.get_all_masters_avg_ratings()

    await state.update_data(service_id=service_id, service_name=service["name"],
                            duration=service["duration_minutes"], price=service["price"])
    await state.set_state(BookingStates.choosing_master)
    await callback.message.edit_text(  # type: ignore
        f"<b>Шаг 2/5 — Выберите мастера</b>\n"
        f"Услуга: <i>{service['name']}</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=masters_kb(masters, ratings=ratings),
    )
    await callback.answer()


# ──────────────────── Step 2: Master ────────────────────

@router.callback_query(BookingStates.choosing_master, F.data.startswith("book_master:"))
async def pick_master(callback: CallbackQuery, state: FSMContext) -> None:
    master_id = int(callback.data.split(":")[1])  # type: ignore
    master = await db.get_master(master_id)
    if not master:
        await callback.answer("Мастер не найден", show_alert=True)
        return

    # Get days off for this master to exclude from date picker
    days_off_list = await db.get_days_off(master_id)
    excluded_dates = {d["date"] for d in days_off_list}

    await state.update_data(master_id=master_id, master_name=master["name"])
    await state.set_state(BookingStates.choosing_date)
    data = await state.get_data()
    await callback.message.edit_text(  # type: ignore
        f"<b>Шаг 3/5 — Выберите дату</b>\n"
        f"Услуга: <i>{data['service_name']}</i>\n"
        f"Мастер: <i>{master['name']}</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=dates_kb(excluded_dates=excluded_dates),
    )
    await callback.answer()


# ──────────────────── Step 3: Date ────────────────────

@router.callback_query(BookingStates.choosing_date, F.data.startswith("book_date:"))
async def pick_date(callback: CallbackQuery, state: FSMContext) -> None:
    chosen_date = callback.data.split(":")[1]  # type: ignore
    data = await state.get_data()

    # Cooldown check
    has = await db.has_booking_today(callback.from_user.id, data["service_id"], chosen_date)
    if has:
        await callback.answer(
            "⚠️ У вас уже есть запись на эту услугу в этот день!",
            show_alert=True,
        )
        return

    # Check if day off
    is_off = await db.is_day_off(data["master_id"], chosen_date)
    if is_off:
        await callback.answer("Мастер в этот день не работает (выходной)", show_alert=True)
        return

    # Check schedule
    d = date.fromisoformat(chosen_date)
    weekday = d.weekday()
    schedule = await db.get_schedule(data["master_id"], weekday)
    if not schedule:
        await callback.answer("Мастер не работает в этот день", show_alert=True)
        return

    booked = await db.get_bookings_for_date(data["master_id"], chosen_date)
    slots = _generate_slots(schedule["start_time"], schedule["end_time"], data["duration"], booked)
    if not slots:
        await callback.answer("Нет свободных слотов на эту дату", show_alert=True)
        return

    await state.update_data(book_date=chosen_date)
    await state.set_state(BookingStates.choosing_time)

    wd_name = WEEKDAYS_RU[weekday]
    month_name = MONTHS_RU[d.month]
    await callback.message.edit_text(  # type: ignore
        f"<b>Шаг 4/5 — Выберите время</b>\n"
        f"Услуга: <i>{data['service_name']}</i>\n"
        f"Мастер: <i>{data['master_name']}</i>\n"
        f"Дата: <i>{wd_name}, {d.day} {month_name}</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=time_slots_kb(slots),
    )
    await callback.answer()


# ──────────────────── Step 4: Time ────────────────────

@router.callback_query(BookingStates.choosing_time, F.data.startswith("book_time:"))
async def pick_time(callback: CallbackQuery, state: FSMContext) -> None:
    chosen_time = callback.data.split(":")[1] + ":" + callback.data.split(":")[2]  # type: ignore
    await state.update_data(book_time=chosen_time)
    await state.set_state(BookingStates.confirming)

    data = await state.get_data()
    d = date.fromisoformat(data["book_date"])
    wd_name = WEEKDAYS_RU[d.weekday()]
    month_name = MONTHS_RU[d.month]

    # Check loyalty discount
    loyalty = await db.get_loyalty(callback.from_user.id)
    discount_line = ""
    if loyalty["discount_available"]:
        discounted_price = data["price"] * (1 - LOYALTY_DISCOUNT_PERCENT / 100)
        discount_line = (
            f"\n🎉 <b>Скидка {LOYALTY_DISCOUNT_PERCENT}% по программе лояльности!</b>\n"
            f"💰 Цена со скидкой: <b>{int(discounted_price)} р.</b>\n"
        )

    await callback.message.edit_text(  # type: ignore
        f"<b>Шаг 5/5 — Подтверждение</b>\n\n"
        f"📋 Услуга: <b>{data['service_name']}</b>\n"
        f"👤 Мастер: <b>{data['master_name']}</b>\n"
        f"📅 Дата: <b>{wd_name}, {d.day} {month_name}</b>\n"
        f"🕐 Время: <b>{chosen_time}</b>\n"
        f"⏱ Длительность: <b>{data['duration']} мин</b>\n"
        f"💰 Стоимость: <b>{int(data['price'])} р.</b>"
        f"{discount_line}\n"
        f"Всё верно?",
        parse_mode=ParseMode.HTML,
        reply_markup=confirm_kb(),
    )
    await callback.answer()


# ──────────────────── Step 5: Confirm ────────────────────

@router.callback_query(BookingStates.confirming, F.data.startswith("book_confirm:"))
async def confirm(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    action = callback.data.split(":")[1]  # type: ignore
    if action == "no":
        await state.clear()
        await callback.message.edit_text("❌ Запись отменена.")  # type: ignore
        await callback.message.answer("Возвращаю в меню.", reply_markup=main_menu())  # type: ignore
        await callback.answer()
        return

    data = await state.get_data()
    username = callback.from_user.username or ""

    booking_id = await db.create_booking(
        user_id=callback.from_user.id,
        username=username,
        master_id=data["master_id"],
        service_id=data["service_id"],
        book_date=data["book_date"],
        book_time=data["book_time"],
    )

    await state.clear()

    d = date.fromisoformat(data["book_date"])
    wd_name = WEEKDAYS_RU[d.weekday()]
    month_name = MONTHS_RU[d.month]

    await callback.message.edit_text(  # type: ignore
        f"✅ <b>Запись подтверждена!</b>\n\n"
        f"Номер записи: <code>#{booking_id}</code>\n"
        f"📋 Услуга: <b>{data['service_name']}</b>\n"
        f"👤 Мастер: <b>{data['master_name']}</b>\n"
        f"📅 Дата: <b>{wd_name}, {d.day} {month_name}</b>\n"
        f"🕐 Время: <b>{data['book_time']}</b>\n"
        f"💰 Стоимость: <b>{int(data['price'])} р.</b>\n\n"
        f"Ждём вас!",
        parse_mode=ParseMode.HTML,
    )
    await callback.message.answer("Главное меню:", reply_markup=main_menu())  # type: ignore
    await callback.answer()

    # Notify admins
    user_display = f"@{username}" if username else f"id:{callback.from_user.id}"
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"🔔 <b>Новая запись #{booking_id}</b>\n\n"
                f"👤 Клиент: {user_display}\n"
                f"📋 Услуга: {data['service_name']}\n"
                f"🧑‍💼 Мастер: {data['master_name']}\n"
                f"📅 {wd_name}, {d.day} {month_name} в {data['book_time']}\n"
                f"💰 {int(data['price'])} р.",
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            logger.warning("Failed to notify admin %s: %s", admin_id, e)


# ──────────────────── Repeat booking ────────────────────

@router.callback_query(F.data.startswith("repeat_booking:"))
async def repeat_booking(callback: CallbackQuery, state: FSMContext) -> None:
    booking_id = int(callback.data.split(":")[1])  # type: ignore
    b = await db.get_booking(booking_id)
    if not b:
        await callback.answer("Запись не найдена", show_alert=True)
        return

    # Pre-fill service and master, go to date selection
    service = await db.get_service(b["service_id"])
    master = await db.get_master(b["master_id"])
    if not service or not master:
        await callback.answer("Услуга или мастер больше недоступны", show_alert=True)
        return

    # Get days off to exclude
    days_off_list = await db.get_days_off(b["master_id"])
    excluded_dates = {d["date"] for d in days_off_list}

    await state.update_data(
        service_id=b["service_id"],
        service_name=b["service_name"],
        duration=b["duration_minutes"],
        price=b["price"],
        master_id=b["master_id"],
        master_name=b["master_name"],
    )
    await state.set_state(BookingStates.choosing_date)

    await callback.message.edit_text(  # type: ignore
        f"🔄 <b>Повторная запись</b>\n\n"
        f"📋 Услуга: <i>{b['service_name']}</i>\n"
        f"👤 Мастер: <i>{b['master_name']}</i>\n\n"
        f"<b>Выберите дату:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=dates_kb(excluded_dates=excluded_dates),
    )
    await callback.answer()
