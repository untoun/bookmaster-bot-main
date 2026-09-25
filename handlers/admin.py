import csv
import io
import logging
from datetime import date, datetime

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import database as db
from config import ADMIN_IDS, LOYALTY_EVERY_N
from keyboards.reply import admin_menu, main_menu, cancel_kb
from keyboards.inline import (
    admin_services_kb, admin_service_actions_kb,
    admin_masters_kb, admin_master_actions_kb,
    admin_master_services_kb, admin_weekdays_kb,
    admin_schedule_day_kb, admin_bookings_filter_kb,
    admin_booking_actions_kb, admin_days_off_kb,
    admin_client_notes_kb,
    WEEKDAYS_RU, MONTHS_RU,
)

logger = logging.getLogger(__name__)
router = Router()

STATUS_LABELS = {
    "confirmed": "🟢 Подтверждена",
    "completed": "✅ Завершена",
    "cancelled": "🔴 Отменена",
}

# SQLite strftime('%w') returns 0=Sunday, but Python weekday() returns 0=Monday
# Map SQLite weekday to Russian names
SQLITE_WEEKDAYS_RU = ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ──────────────────── FSM states ────────────────────

class AdminStates(StatesGroup):
    adding_service = State()        # waiting: name|duration|price
    adding_master = State()         # waiting: name|specialization
    setting_schedule = State()      # waiting: HH:MM-HH:MM
    adding_day_off = State()        # waiting: YYYY-MM-DD|reason
    adding_client_note = State()    # waiting: note text
    export_bookings = State()       # waiting: date range
    export_master_schedule = State()  # waiting: master pick


# ──────────────────── Admin entry ────────────────────

@router.message(F.text == "/admin")
async def cmd_admin(message: Message) -> None:
    if not _is_admin(message.from_user.id):  # type: ignore
        await message.answer("⛔ Доступ запрещён.")
        return
    await message.answer(
        "<b>🔧 Панель администратора</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_menu(),
    )


@router.message(F.text == "◀️ Назад")
async def admin_back(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Главное меню:", reply_markup=main_menu())


# ═══════════════════════════════════════════════════
#  SERVICES
# ═══════════════════════════════════════════════════

@router.message(F.text == "🔧 Услуги")
async def admin_services(message: Message) -> None:
    if not _is_admin(message.from_user.id):  # type: ignore
        return
    await _show_services_list(message)


async def _show_services_list(target: Message | CallbackQuery) -> None:
    all_services = await db.get_all_services()
    kb = admin_services_kb(all_services)
    text = "<b>🔧 Управление услугами:</b>"

    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)  # type: ignore
        await target.answer()
    else:
        await target.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb)


@router.callback_query(F.data == "adm_svc_list")
async def adm_svc_list_cb(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    await _show_services_list(callback)


@router.callback_query(F.data.startswith("adm_svc:"))
async def adm_svc_detail(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    svc_id = int(callback.data.split(":")[1])  # type: ignore
    svc = await db.get_service(svc_id)
    if not svc:
        await callback.answer("Не найдено", show_alert=True)
        return
    status = "✅ Активна" if svc["is_active"] else "❌ Неактивна"
    await callback.message.edit_text(  # type: ignore
        f"<b>Услуга #{svc['id']}</b>\n\n"
        f"📋 Название: <b>{svc['name']}</b>\n"
        f"⏱ Длительность: <b>{svc['duration_minutes']} мин</b>\n"
        f"💰 Цена: <b>{int(svc['price'])} р.</b>\n"
        f"📌 Статус: {status}",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_service_actions_kb(svc_id, svc["is_active"]),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_svc_toggle:"))
async def adm_svc_toggle(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    svc_id = int(callback.data.split(":")[1])  # type: ignore
    await db.toggle_service(svc_id)
    await callback.answer("Статус изменён")
    await _show_services_list(callback)


@router.callback_query(F.data.startswith("adm_svc_del:"))
async def adm_svc_delete(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    svc_id = int(callback.data.split(":")[1])  # type: ignore
    await db.delete_service(svc_id)
    await callback.answer("Услуга удалена")
    await _show_services_list(callback)


@router.callback_query(F.data == "adm_svc_add")
async def adm_svc_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return
    await state.set_state(AdminStates.adding_service)
    await callback.message.answer(  # type: ignore
        "Введите данные услуги в формате:\n"
        "<code>Название | Длительность (мин) | Цена</code>\n\n"
        "Пример: <code>Стрижка мужская | 45 | 1500</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(AdminStates.adding_service)
async def adm_svc_add_process(message: Message, state: FSMContext) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_menu())
        return

    parts = [p.strip() for p in message.text.split("|")]  # type: ignore
    if len(parts) != 3:
        await message.answer("❌ Неверный формат. Используйте: <code>Название | Длительность | Цена</code>",
                             parse_mode=ParseMode.HTML)
        return

    name = parts[0]
    try:
        duration = int(parts[1])
        price = float(parts[2])
    except ValueError:
        await message.answer("❌ Длительность и цена должны быть числами.")
        return

    svc_id = await db.add_service(name, duration, price)
    await state.clear()
    await message.answer(
        f"✅ Услуга <b>{name}</b> добавлена (#{svc_id}).",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_menu(),
    )


# ═══════════════════════════════════════════════════
#  MASTERS
# ═══════════════════════════════════════════════════

@router.message(F.text == "👤 Мастера")
async def admin_masters(message: Message) -> None:
    if not _is_admin(message.from_user.id):  # type: ignore
        return
    await _show_masters_list(message)


async def _show_masters_list(target: Message | CallbackQuery) -> None:
    all_masters = await db.get_all_masters()
    kb = admin_masters_kb(all_masters)
    text = "<b>👤 Управление мастерами:</b>"
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)  # type: ignore
        await target.answer()
    else:
        await target.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb)


@router.callback_query(F.data == "adm_mst_list")
async def adm_mst_list_cb(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    await _show_masters_list(callback)


@router.callback_query(F.data.startswith("adm_mst:"))
async def adm_mst_detail(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    master_id = int(callback.data.split(":")[1])  # type: ignore
    m = await db.get_master(master_id)
    if not m:
        await callback.answer("Не найден", show_alert=True)
        return
    status = "✅ Активен" if m["is_active"] else "❌ Неактивен"

    services = await db.get_services_for_master(master_id)
    svc_text = ", ".join(s["name"] for s in services) if services else "—"

    schedule = await db.get_full_schedule(master_id)
    sched_lines = []
    for s in schedule:
        sched_lines.append(f"  {WEEKDAYS_RU[s['weekday']]}: {s['start_time']}–{s['end_time']}")
    sched_text = "\n".join(sched_lines) if sched_lines else "  Не задано"

    # Rating
    avg = await db.get_master_avg_rating(master_id)
    rating_text = f"⭐ {avg}" if avg else "Нет оценок"

    # Days off
    days_off = await db.get_days_off(master_id)
    days_off_text = ", ".join(d["date"] for d in days_off[:5]) if days_off else "—"
    if len(days_off) > 5:
        days_off_text += f" (+{len(days_off) - 5})"

    await callback.message.edit_text(  # type: ignore
        f"<b>Мастер #{m['id']}</b>\n\n"
        f"👤 Имя: <b>{m['name']}</b>\n"
        f"🔧 Специализация: <b>{m['specialization'] or '—'}</b>\n"
        f"📌 Статус: {status}\n"
        f"⭐ Рейтинг: {rating_text}\n"
        f"📋 Услуги: {svc_text}\n\n"
        f"📅 Расписание:\n{sched_text}\n\n"
        f"🏖 Выходные: {days_off_text}",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_master_actions_kb(master_id, m["is_active"]),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_mst_toggle:"))
async def adm_mst_toggle(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    master_id = int(callback.data.split(":")[1])  # type: ignore
    await db.toggle_master(master_id)
    await callback.answer("Статус изменён")
    await _show_masters_list(callback)


@router.callback_query(F.data.startswith("adm_mst_del:"))
async def adm_mst_delete(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    master_id = int(callback.data.split(":")[1])  # type: ignore
    await db.delete_master(master_id)
    await callback.answer("Мастер удалён")
    await _show_masters_list(callback)


@router.callback_query(F.data == "adm_mst_add")
async def adm_mst_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return
    await state.set_state(AdminStates.adding_master)
    await callback.message.answer(  # type: ignore
        "Введите данные мастера в формате:\n"
        "<code>Имя | Специализация</code>\n\n"
        "Пример: <code>Анна Иванова | Парикмахер</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(AdminStates.adding_master)
async def adm_mst_add_process(message: Message, state: FSMContext) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_menu())
        return

    parts = [p.strip() for p in message.text.split("|")]  # type: ignore
    if len(parts) < 1:
        await message.answer("❌ Неверный формат.")
        return

    name = parts[0]
    spec = parts[1] if len(parts) > 1 else ""

    master_id = await db.add_master(name, spec)
    await state.clear()
    await message.answer(
        f"✅ Мастер <b>{name}</b> добавлен (#{master_id}).",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_menu(),
    )


# ──────────────────── Master ↔ Services ────────────────────

@router.callback_query(F.data.startswith("adm_mst_svcs:"))
async def adm_mst_services(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    master_id = int(callback.data.split(":")[1])  # type: ignore
    await _show_master_services(callback, master_id)


async def _show_master_services(callback: CallbackQuery, master_id: int) -> None:
    all_services = await db.get_all_services()
    linked = await db.get_services_for_master(master_id)
    linked_ids = {s["id"] for s in linked}

    master = await db.get_master(master_id)
    name = master["name"] if master else "?"

    await callback.message.edit_text(  # type: ignore
        f"<b>Услуги мастера {name}:</b>\n"
        f"Нажмите, чтобы привязать/отвязать услугу.",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_master_services_kb(master_id, all_services, linked_ids),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_mst_svc_toggle:"))
async def adm_mst_svc_toggle(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    parts = callback.data.split(":")  # type: ignore
    master_id = int(parts[1])
    service_id = int(parts[2])

    linked = await db.get_services_for_master(master_id)
    linked_ids = {s["id"] for s in linked}

    if service_id in linked_ids:
        await db.unlink_master_service(master_id, service_id)
    else:
        await db.link_master_service(master_id, service_id)

    await _show_master_services(callback, master_id)


# ──────────────────── Schedule ────────────────────

@router.message(F.text == "📅 Расписание")
async def admin_schedule_menu(message: Message) -> None:
    if not _is_admin(message.from_user.id):  # type: ignore
        return
    masters = await db.get_active_masters()
    if not masters:
        await message.answer("Нет активных мастеров.")
        return
    from keyboards.inline import masters_kb
    await message.answer(
        "<b>📅 Выберите мастера для настройки расписания:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=masters_kb(masters, prefix="adm_mst_sched"),
    )


@router.callback_query(F.data.startswith("adm_mst_sched:"))
async def adm_mst_schedule(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    master_id = int(callback.data.split(":")[1])  # type: ignore
    master = await db.get_master(master_id)
    if not master:
        await callback.answer("Не найден", show_alert=True)
        return

    schedule = await db.get_full_schedule(master_id)
    existing = {s["weekday"] for s in schedule}

    sched_lines = []
    for s in schedule:
        sched_lines.append(f"  {WEEKDAYS_RU[s['weekday']]}: {s['start_time']}–{s['end_time']}")
    sched_text = "\n".join(sched_lines) if sched_lines else "  Не задано"

    await callback.message.edit_text(  # type: ignore
        f"<b>📅 Расписание — {master['name']}</b>\n\n{sched_text}\n\n"
        f"Выберите день для настройки:",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_weekdays_kb(master_id, existing),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_sched_day:"))
async def adm_sched_day(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    parts = callback.data.split(":")  # type: ignore
    master_id = int(parts[1])
    weekday = int(parts[2])

    schedule = await db.get_schedule(master_id, weekday)
    if schedule:
        text = f"<b>{WEEKDAYS_RU[weekday]}</b>: {schedule['start_time']}–{schedule['end_time']}"
    else:
        text = f"<b>{WEEKDAYS_RU[weekday]}</b>: выходной"

    await callback.message.edit_text(  # type: ignore
        text, parse_mode=ParseMode.HTML,
        reply_markup=admin_schedule_day_kb(master_id, weekday),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_sched_set:"))
async def adm_sched_set_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return
    parts = callback.data.split(":")  # type: ignore
    master_id = int(parts[1])
    weekday = int(parts[2])

    await state.set_state(AdminStates.setting_schedule)
    await state.update_data(sched_master_id=master_id, sched_weekday=weekday)

    await callback.message.answer(  # type: ignore
        f"Введите рабочее время для <b>{WEEKDAYS_RU[weekday]}</b> в формате:\n"
        f"<code>09:00-18:00</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(AdminStates.setting_schedule)
async def adm_sched_set_process(message: Message, state: FSMContext) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_menu())
        return

    text = message.text.strip().replace(" ", "")  # type: ignore
    if "-" not in text:
        await message.answer("❌ Используйте формат <code>09:00-18:00</code>", parse_mode=ParseMode.HTML)
        return

    parts = text.split("-")
    if len(parts) != 2:
        await message.answer("❌ Используйте формат <code>09:00-18:00</code>", parse_mode=ParseMode.HTML)
        return

    start_time, end_time = parts[0], parts[1]

    try:
        s = datetime.strptime(start_time, "%H:%M")
        e = datetime.strptime(end_time, "%H:%M")
        if e <= s:
            raise ValueError
    except ValueError:
        await message.answer("❌ Неверное время. Конец должен быть позже начала.")
        return

    data = await state.get_data()
    master_id = data["sched_master_id"]
    weekday = data["sched_weekday"]

    await db.set_schedule(master_id, weekday, start_time, end_time)
    await state.clear()

    await message.answer(
        f"✅ Расписание на <b>{WEEKDAYS_RU[weekday]}</b> установлено: "
        f"{start_time}–{end_time}",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_menu(),
    )


@router.callback_query(F.data.startswith("adm_sched_del:"))
async def adm_sched_delete(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    parts = callback.data.split(":")  # type: ignore
    master_id = int(parts[1])
    weekday = int(parts[2])
    await db.delete_schedule(master_id, weekday)
    await callback.answer("День удалён из расписания")

    # Go back to schedule view
    callback.data = f"adm_mst_sched:{master_id}"  # type: ignore
    await adm_mst_schedule(callback)


# ═══════════════════════════════════════════════════
#  DAYS OFF
# ═══════════════════════════════════════════════════

@router.message(F.text == "🏖 Выходные")
async def admin_days_off_menu(message: Message) -> None:
    if not _is_admin(message.from_user.id):  # type: ignore
        return
    masters = await db.get_active_masters()
    if not masters:
        await message.answer("Нет активных мастеров.")
        return
    from keyboards.inline import masters_kb
    await message.answer(
        "<b>🏖 Выберите мастера для управления выходными:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=masters_kb(masters, prefix="adm_mst_daysoff"),
    )


@router.callback_query(F.data.startswith("adm_mst_daysoff:"))
async def adm_mst_daysoff(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    master_id = int(callback.data.split(":")[1])  # type: ignore
    master = await db.get_master(master_id)
    if not master:
        await callback.answer("Не найден", show_alert=True)
        return

    days_off = await db.get_days_off(master_id)
    await callback.message.edit_text(  # type: ignore
        f"<b>🏖 Выходные — {master['name']}</b>\n\n"
        f"Нажмите на дату, чтобы удалить. Или добавьте новый выходной.",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_days_off_kb(master_id, days_off),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_dayoff_add:"))
async def adm_dayoff_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return
    master_id = int(callback.data.split(":")[1])  # type: ignore
    await state.set_state(AdminStates.adding_day_off)
    await state.update_data(dayoff_master_id=master_id)
    await callback.message.answer(  # type: ignore
        "Введите дату выходного и причину в формате:\n"
        "<code>2025-03-15 | Отпуск</code>\n\n"
        "Причину можно не указывать:\n"
        "<code>2025-03-15</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(AdminStates.adding_day_off)
async def adm_dayoff_add_process(message: Message, state: FSMContext) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_menu())
        return

    parts = [p.strip() for p in message.text.split("|")]  # type: ignore
    date_str = parts[0]
    reason = parts[1] if len(parts) > 1 else ""

    try:
        date.fromisoformat(date_str)
    except ValueError:
        await message.answer("❌ Неверный формат даты. Используйте YYYY-MM-DD.")
        return

    data = await state.get_data()
    master_id = data["dayoff_master_id"]
    await db.add_day_off(master_id, date_str, reason)
    await state.clear()

    reason_str = f" ({reason})" if reason else ""
    await message.answer(
        f"✅ Выходной <b>{date_str}</b>{reason_str} добавлен.",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_menu(),
    )


@router.callback_query(F.data.startswith("adm_dayoff_del:"))
async def adm_dayoff_delete(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    parts = callback.data.split(":")  # type: ignore
    dayoff_id = int(parts[1])
    master_id = int(parts[2])
    await db.delete_day_off(dayoff_id)
    await callback.answer("Выходной удалён")

    # Refresh
    callback.data = f"adm_mst_daysoff:{master_id}"  # type: ignore
    await adm_mst_daysoff(callback)


# ═══════════════════════════════════════════════════
#  BOOKINGS
# ═══════════════════════════════════════════════════

@router.message(F.text == "📊 Записи")
async def admin_bookings(message: Message) -> None:
    if not _is_admin(message.from_user.id):  # type: ignore
        return
    await message.answer(
        "<b>📊 Фильтр записей:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_bookings_filter_kb(),
    )


@router.callback_query(F.data.startswith("adm_bk_filter:"))
async def adm_bk_filter(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    status = callback.data.split(":")[1]  # type: ignore
    bookings = await db.get_all_bookings(status if status != "all" else None)

    if not bookings:
        await callback.message.edit_text(  # type: ignore
            "Записей не найдено.",
            reply_markup=admin_bookings_filter_kb(),
        )
        await callback.answer()
        return

    booking_buttons = []
    for b in bookings[:20]:
        st_icon = {"confirmed": "🟢", "completed": "✅", "cancelled": "🔴"}.get(b["status"], "⚪")
        booking_buttons.append([InlineKeyboardButton(
            text=f"{st_icon} #{b['id']} {b['date']} {b['time']} — {b['service_name']}",
            callback_data=f"adm_bk_detail:{b['id']}",
        )])
    booking_buttons.append([InlineKeyboardButton(text="◀️ Фильтры", callback_data="adm_bk_filters_back")])

    await callback.message.edit_text(  # type: ignore
        f"<b>📊 Записи ({len(bookings)}):</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=booking_buttons),
    )
    await callback.answer()


@router.callback_query(F.data == "adm_bk_filters_back")
async def adm_bk_filters_back(callback: CallbackQuery) -> None:
    await callback.message.edit_text(  # type: ignore
        "<b>📊 Фильтр записей:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_bookings_filter_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_bk_detail:"))
async def adm_bk_detail(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    booking_id = int(callback.data.split(":")[1])  # type: ignore
    b = await db.get_booking(booking_id)
    if not b:
        await callback.answer("Не найдена", show_alert=True)
        return

    d = date.fromisoformat(b["date"])
    wd = WEEKDAYS_RU[d.weekday()]
    month = MONTHS_RU[d.month]
    status = STATUS_LABELS.get(b["status"], b["status"])
    user_display = f"@{b['username']}" if b["username"] else f"id:{b['user_id']}"

    # Get client notes
    notes = await db.get_client_notes(b["user_id"])
    notes_text = ""
    if notes:
        notes_text = "\n📝 <b>Заметки о клиенте:</b>\n"
        for n in notes[:3]:
            notes_text += f"  • {n['note']}\n"
        if len(notes) > 3:
            notes_text += f"  <i>...и ещё {len(notes) - 3}</i>\n"

    await callback.message.edit_text(  # type: ignore
        f"<b>Запись #{b['id']}</b>\n\n"
        f"👤 Клиент: <b>{user_display}</b>\n"
        f"📋 Услуга: <b>{b['service_name']}</b>\n"
        f"🧑‍💼 Мастер: <b>{b['master_name']}</b>\n"
        f"📅 Дата: <b>{wd}, {d.day} {month}</b>\n"
        f"🕐 Время: <b>{b['time']}</b>\n"
        f"⏱ Длительность: <b>{b['duration_minutes']} мин</b>\n"
        f"💰 Стоимость: <b>{int(b['price'])} р.</b>\n"
        f"📌 Статус: {status}\n"
        f"🕒 Создана: {b['created_at']}"
        f"{notes_text}",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_booking_actions_kb(booking_id, b["status"]),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_bk_status:"))
async def adm_bk_change_status(callback: CallbackQuery, bot: Bot) -> None:
    if not _is_admin(callback.from_user.id):
        return
    parts = callback.data.split(":")  # type: ignore
    booking_id = int(parts[1])
    new_status = parts[2]

    await db.update_booking_status(booking_id, new_status)

    # If completed, update loyalty and prompt review
    if new_status == "completed":
        b = await db.get_booking(booking_id)
        if b:
            loyalty = await db.increment_loyalty(b["user_id"], LOYALTY_EVERY_N)
            # Notify user about completion and prompt review
            try:
                review_kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="⭐ Оставить отзыв",
                        callback_data=f"review_start:{booking_id}",
                    )],
                ])
                loyalty_msg = ""
                if loyalty["discount_available"]:
                    loyalty_msg = (
                        f"\n\n🎉 <b>Поздравляем!</b> Вы накопили {loyalty['total_visits']} визитов. "
                        f"Ваша следующая запись будет со скидкой!"
                    )
                await bot.send_message(
                    b["user_id"],
                    f"✅ <b>Ваша запись #{booking_id} завершена!</b>\n\n"
                    f"📋 {b['service_name']}\n"
                    f"👤 Мастер: {b['master_name']}\n\n"
                    f"Будем рады вашему отзыву!{loyalty_msg}",
                    parse_mode="HTML",
                    reply_markup=review_kb,
                )
            except Exception as e:
                logger.warning("Failed to send completion notification to user %s: %s", b["user_id"], e)

    await callback.answer(f"Статус изменён на: {new_status}")

    # Refresh detail
    callback.data = f"adm_bk_detail:{booking_id}"  # type: ignore
    await adm_bk_detail(callback)


# ═══════════════════════════════════════════════════
#  CLIENT NOTES
# ═══════════════════════════════════════════════════

@router.message(F.text == "📝 Заметки")
async def admin_notes_menu(message: Message) -> None:
    if not _is_admin(message.from_user.id):  # type: ignore
        return
    await message.answer(
        "<b>📝 Заметки о клиентах</b>\n\n"
        "Чтобы управлять заметками, откройте запись клиента в разделе «Записи» "
        "и нажмите «📝 Заметки клиента».",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_menu(),
    )


@router.callback_query(F.data.startswith("adm_bk_notes:"))
async def adm_bk_notes(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    booking_id = int(callback.data.split(":")[1])  # type: ignore
    b = await db.get_booking(booking_id)
    if not b:
        await callback.answer("Запись не найдена", show_alert=True)
        return

    notes = await db.get_client_notes(b["user_id"])
    user_display = f"@{b['username']}" if b["username"] else f"id:{b['user_id']}"

    text = f"<b>📝 Заметки о клиенте {user_display}</b>\n\n"
    if notes:
        for n in notes:
            text += f"• {n['note']} <i>({n['created_at'][:10]})</i>\n"
    else:
        text += "<i>Заметок пока нет.</i>"

    await callback.message.edit_text(  # type: ignore
        text, parse_mode=ParseMode.HTML,
        reply_markup=admin_client_notes_kb(b["user_id"], notes, booking_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_note_add:"))
async def adm_note_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return
    parts = callback.data.split(":")  # type: ignore
    user_id = int(parts[1])
    booking_id = int(parts[2]) if len(parts) > 2 and parts[2] != "0" else None

    await state.set_state(AdminStates.adding_client_note)
    await state.update_data(note_user_id=user_id, note_booking_id=booking_id)
    await callback.message.answer(  # type: ignore
        "Введите текст заметки о клиенте:\n\n"
        "Примеры: <i>Аллергия на краску</i>, <i>VIP клиент</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(AdminStates.adding_client_note)
async def adm_note_add_process(message: Message, state: FSMContext) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_menu())
        return

    note_text = message.text.strip()  # type: ignore
    if not note_text:
        await message.answer("❌ Заметка не может быть пустой.")
        return

    data = await state.get_data()
    user_id = data["note_user_id"]
    await db.add_client_note(user_id, note_text, message.from_user.id)  # type: ignore
    await state.clear()

    await message.answer(
        f"✅ Заметка добавлена.",
        reply_markup=admin_menu(),
    )


@router.callback_query(F.data.startswith("adm_note_del:"))
async def adm_note_delete(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    parts = callback.data.split(":")  # type: ignore
    note_id = int(parts[1])
    user_id = int(parts[2])
    booking_id = int(parts[3]) if len(parts) > 3 and parts[3] != "0" else None

    await db.delete_client_note(note_id)
    await callback.answer("Заметка удалена")

    if booking_id:
        callback.data = f"adm_bk_notes:{booking_id}"  # type: ignore
        await adm_bk_notes(callback)


# ═══════════════════════════════════════════════════
#  CSV EXPORT
# ═══════════════════════════════════════════════════

@router.message(Command("export_bookings"))
async def export_bookings_start(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):  # type: ignore
        await message.answer("⛔ Доступ запрещён.")
        return
    await state.set_state(AdminStates.export_bookings)
    await message.answer(
        "Введите диапазон дат для экспорта записей:\n"
        "<code>2025-01-01 | 2025-01-31</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_kb(),
    )


@router.message(AdminStates.export_bookings)
async def export_bookings_process(message: Message, state: FSMContext) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_menu())
        return

    parts = [p.strip() for p in message.text.split("|")]  # type: ignore
    if len(parts) != 2:
        await message.answer("❌ Используйте формат: <code>YYYY-MM-DD | YYYY-MM-DD</code>",
                             parse_mode=ParseMode.HTML)
        return

    try:
        date_from = date.fromisoformat(parts[0]).isoformat()
        date_to = date.fromisoformat(parts[1]).isoformat()
    except ValueError:
        await message.answer("❌ Неверный формат даты.")
        return

    bookings = await db.get_bookings_in_date_range(date_from, date_to)
    if not bookings:
        await message.answer("Нет записей за указанный период.", reply_markup=admin_menu())
        await state.clear()
        return

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Клиент", "Username", "Услуга", "Мастер", "Дата", "Время", "Статус", "Цена", "Создана"])
    for b in bookings:
        writer.writerow([
            b["id"],
            b["user_id"],
            b.get("username", ""),
            b["service_name"],
            b["master_name"],
            b["date"],
            b["time"],
            b["status"],
            int(b["price"]),
            b["created_at"],
        ])

    csv_bytes = output.getvalue().encode("utf-8-sig")  # BOM for Excel
    doc = BufferedInputFile(csv_bytes, filename=f"bookings_{date_from}_{date_to}.csv")
    await message.answer_document(doc, caption=f"📊 Записи с {date_from} по {date_to} ({len(bookings)} шт.)")
    await state.clear()
    await message.answer("Экспорт завершён.", reply_markup=admin_menu())


@router.message(Command("export_schedule"))
async def export_schedule(message: Message) -> None:
    if not _is_admin(message.from_user.id):  # type: ignore
        await message.answer("⛔ Доступ запрещён.")
        return

    masters = await db.get_active_masters()
    if not masters:
        await message.answer("Нет активных мастеров.", reply_markup=admin_menu())
        return

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Мастер", "Специализация", "День недели", "Начало", "Конец"])

    for m in masters:
        schedule = await db.get_full_schedule(m["id"])
        if schedule:
            for s in schedule:
                writer.writerow([
                    m["name"],
                    m.get("specialization", ""),
                    WEEKDAYS_RU[s["weekday"]],
                    s["start_time"],
                    s["end_time"],
                ])
        else:
            writer.writerow([m["name"], m.get("specialization", ""), "—", "—", "—"])

    csv_bytes = output.getvalue().encode("utf-8-sig")
    doc = BufferedInputFile(csv_bytes, filename="master_schedule.csv")
    await message.answer_document(doc, caption="📅 Расписание мастеров")


# ═══════════════════════════════════════════════════
#  ANALYTICS / STATS
# ═══════════════════════════════════════════════════

@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if not _is_admin(message.from_user.id):  # type: ignore
        await message.answer("⛔ Доступ запрещён.")
        return

    today = date.today()
    year, month = today.year, today.month

    stats = await db.get_stats_bookings_month(year, month)
    popular = await db.get_popular_services(5)
    busiest = await db.get_busiest_weekdays()
    utilization = await db.get_master_utilization(year, month)
    ratings = await db.get_all_masters_avg_ratings()

    month_name = MONTHS_RU[month]

    # Build text
    text = f"<b>📊 Аналитика — {month_name} {year}</b>\n\n"

    # Monthly summary
    text += "<b>Записи за месяц:</b>\n"
    text += f"  Всего: {stats['total']}\n"
    text += f"  Завершено: {stats['completed']}\n"
    text += f"  Отменено: {stats['cancelled']}\n"
    text += f"  Выручка: {int(stats['revenue'])} р.\n\n"

    # Popular services bar chart
    if popular:
        text += "<b>Топ-5 услуг:</b>\n"
        max_cnt = max(s["cnt"] for s in popular) if popular else 1
        for s in popular:
            bar_len = int(s["cnt"] / max_cnt * 10) if max_cnt > 0 else 0
            bar = "█" * bar_len + "░" * (10 - bar_len)
            text += f"  {bar} {s['name']} ({s['cnt']})\n"
        text += "\n"

    # Busiest weekdays
    if busiest:
        text += "<b>Загрузка по дням недели:</b>\n"
        max_cnt = max(d["cnt"] for d in busiest) if busiest else 1
        for d in busiest:
            # SQLite %w: 0=Sunday, 1=Monday, ..., 6=Saturday
            wd_name = SQLITE_WEEKDAYS_RU[d["weekday_num"]]
            bar_len = int(d["cnt"] / max_cnt * 8) if max_cnt > 0 else 0
            bar = "█" * bar_len + "░" * (8 - bar_len)
            text += f"  {wd_name}: {bar} ({d['cnt']})\n"
        text += "\n"

    # Master utilization
    if utilization:
        text += "<b>Загрузка мастеров (завершённых):</b>\n"
        for m in utilization:
            text += f"  {m['name']}: {m['cnt']} записей\n"
        text += "\n"

    # Ratings
    if ratings:
        text += "<b>Рейтинг мастеров:</b>\n"
        masters = await db.get_active_masters()
        master_names = {m["id"]: m["name"] for m in masters}
        for mid, avg in sorted(ratings.items(), key=lambda x: x[1], reverse=True):
            name = master_names.get(mid, f"#{mid}")
            text += f"  {name}: ⭐ {avg}\n"

    await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=admin_menu())
