from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import date, timedelta

WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
MONTHS_RU = [
    "", "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]


def services_kb(services: list[dict], prefix: str = "book_service") -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            text=f"{s['name']} — {int(s['price'])} р. ({s['duration_minutes']} мин)",
            callback_data=f"{prefix}:{s['id']}",
        )]
        for s in services
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def masters_kb(
    masters: list[dict],
    prefix: str = "book_master",
    ratings: dict[int, float] | None = None,
) -> InlineKeyboardMarkup:
    """Build masters keyboard. If ratings dict is passed, show avg rating next to name."""
    buttons = []
    for m in masters:
        label = m["name"]
        if m.get("specialization"):
            label += f" ({m['specialization']})"
        if ratings and m["id"] in ratings:
            label += f" \u2b50 {ratings[m['id']]}"
        buttons.append([InlineKeyboardButton(
            text=label,
            callback_data=f"{prefix}:{m['id']}",
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def dates_kb(days: int = 7, excluded_dates: set[str] | None = None) -> InlineKeyboardMarkup:
    """Generate date picker. excluded_dates is a set of ISO date strings to skip."""
    today = date.today()
    buttons = []
    excluded = excluded_dates or set()
    for i in range(days):
        d = today + timedelta(days=i)
        if d.isoformat() in excluded:
            continue
        wd = WEEKDAYS_RU[d.weekday()]
        label = f"{wd}, {d.day} {MONTHS_RU[d.month]}"
        buttons.append(
            [InlineKeyboardButton(text=label, callback_data=f"book_date:{d.isoformat()}")]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def time_slots_kb(slots: list[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for s in slots:
        row.append(InlineKeyboardButton(text=s, callback_data=f"book_time:{s}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data="book_confirm:yes"),
            InlineKeyboardButton(text="❌ Отменить", callback_data="book_confirm:no"),
        ]
    ])


def user_bookings_kb(bookings: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for b in bookings:
        status_icon = {"confirmed": "🟢", "completed": "✅", "cancelled": "🔴"}.get(b["status"], "⚪")
        buttons.append([InlineKeyboardButton(
            text=f"{status_icon} {b['date']} {b['time']} — {b['service_name']}",
            callback_data=f"my_booking:{b['id']}",
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cancel_booking_kb(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Отменить запись", callback_data=f"cancel_booking:{booking_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_my_bookings")],
    ])


def completed_booking_kb(booking_id: int, has_review: bool) -> InlineKeyboardMarkup:
    """Keyboard for a completed booking: repeat + optional review."""
    buttons = []
    buttons.append([InlineKeyboardButton(
        text="🔄 Повторить запись",
        callback_data=f"repeat_booking:{booking_id}",
    )])
    if not has_review:
        buttons.append([InlineKeyboardButton(
            text="⭐ Оставить отзыв",
            callback_data=f"review_start:{booking_id}",
        )])
    else:
        buttons.append([InlineKeyboardButton(
            text="📖 Мой отзыв",
            callback_data=f"review_view:{booking_id}",
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_my_bookings")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def rating_kb(booking_id: int) -> InlineKeyboardMarkup:
    """Stars 1-5 rating keyboard."""
    buttons = []
    row = []
    for i in range(1, 6):
        row.append(InlineKeyboardButton(
            text="⭐" * i,
            callback_data=f"review_rate:{booking_id}:{i}",
        ))
    # Two rows: 1-3 and 4-5
    buttons.append(row[:3])
    buttons.append(row[3:])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_my_bookings")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def master_profile_kb(master_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Все отзывы", callback_data=f"master_reviews:{master_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_my_bookings")],
    ])


# ──────────────────── Admin keyboards ────────────────────

def admin_services_kb(services: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for s in services:
        icon = "✅" if s["is_active"] else "❌"
        buttons.append([InlineKeyboardButton(
            text=f"{icon} {s['name']} — {int(s['price'])} р.",
            callback_data=f"adm_svc:{s['id']}",
        )])
    buttons.append([InlineKeyboardButton(text="➕ Добавить услугу", callback_data="adm_svc_add")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_service_actions_kb(service_id: int, is_active: int) -> InlineKeyboardMarkup:
    toggle_text = "⛔ Деактивировать" if is_active else "✅ Активировать"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data=f"adm_svc_toggle:{service_id}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"adm_svc_del:{service_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm_svc_list")],
    ])


def admin_masters_kb(masters: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for m in masters:
        icon = "✅" if m["is_active"] else "❌"
        buttons.append([InlineKeyboardButton(
            text=f"{icon} {m['name']}" + (f" ({m['specialization']})" if m['specialization'] else ""),
            callback_data=f"adm_mst:{m['id']}",
        )])
    buttons.append([InlineKeyboardButton(text="➕ Добавить мастера", callback_data="adm_mst_add")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_master_actions_kb(master_id: int, is_active: int) -> InlineKeyboardMarkup:
    toggle_text = "⛔ Деактивировать" if is_active else "✅ Активировать"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data=f"adm_mst_toggle:{master_id}")],
        [InlineKeyboardButton(text="📋 Услуги мастера", callback_data=f"adm_mst_svcs:{master_id}")],
        [InlineKeyboardButton(text="📅 Расписание", callback_data=f"adm_mst_sched:{master_id}")],
        [InlineKeyboardButton(text="🏖 Выходные", callback_data=f"adm_mst_daysoff:{master_id}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"adm_mst_del:{master_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm_mst_list")],
    ])


def admin_master_services_kb(
    master_id: int,
    all_services: list[dict],
    linked_ids: set[int],
) -> InlineKeyboardMarkup:
    buttons = []
    for s in all_services:
        icon = "✅" if s["id"] in linked_ids else "➖"
        buttons.append([InlineKeyboardButton(
            text=f"{icon} {s['name']}",
            callback_data=f"adm_mst_svc_toggle:{master_id}:{s['id']}",
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_mst:{master_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_weekdays_kb(master_id: int, existing: set[int]) -> InlineKeyboardMarkup:
    buttons = []
    for wd in range(7):
        icon = "✅" if wd in existing else "➖"
        buttons.append([InlineKeyboardButton(
            text=f"{icon} {WEEKDAYS_RU[wd]}",
            callback_data=f"adm_sched_day:{master_id}:{wd}",
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_mst:{master_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_schedule_day_kb(master_id: int, weekday: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Задать время", callback_data=f"adm_sched_set:{master_id}:{weekday}")],
        [InlineKeyboardButton(text="🗑 Удалить день", callback_data=f"adm_sched_del:{master_id}:{weekday}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_mst_sched:{master_id}")],
    ])


def admin_bookings_filter_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🟢 Подтверждённые", callback_data="adm_bk_filter:confirmed"),
            InlineKeyboardButton(text="✅ Завершённые", callback_data="adm_bk_filter:completed"),
        ],
        [
            InlineKeyboardButton(text="🔴 Отменённые", callback_data="adm_bk_filter:cancelled"),
            InlineKeyboardButton(text="📋 Все", callback_data="adm_bk_filter:all"),
        ],
    ])


def admin_booking_actions_kb(booking_id: int, current_status: str) -> InlineKeyboardMarkup:
    buttons = []
    if current_status != "confirmed":
        buttons.append([InlineKeyboardButton(
            text="🟢 Подтвердить", callback_data=f"adm_bk_status:{booking_id}:confirmed"
        )])
    if current_status != "completed":
        buttons.append([InlineKeyboardButton(
            text="✅ Завершить", callback_data=f"adm_bk_status:{booking_id}:completed"
        )])
    if current_status != "cancelled":
        buttons.append([InlineKeyboardButton(
            text="🔴 Отменить", callback_data=f"adm_bk_status:{booking_id}:cancelled"
        )])
    # Client notes
    buttons.append([InlineKeyboardButton(
        text="📝 Заметки клиента", callback_data=f"adm_bk_notes:{booking_id}"
    )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="adm_bk_filter:all")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_days_off_kb(master_id: int, days_off: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for d in days_off:
        reason_str = f" ({d['reason']})" if d["reason"] else ""
        buttons.append([InlineKeyboardButton(
            text=f"🗑 {d['date']}{reason_str}",
            callback_data=f"adm_dayoff_del:{d['id']}:{master_id}",
        )])
    buttons.append([InlineKeyboardButton(text="➕ Добавить выходной", callback_data=f"adm_dayoff_add:{master_id}")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_mst:{master_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_client_notes_kb(user_id: int, notes: list[dict], booking_id: int | None = None) -> InlineKeyboardMarkup:
    buttons = []
    for n in notes:
        short = n["note"][:40] + ("..." if len(n["note"]) > 40 else "")
        buttons.append([InlineKeyboardButton(
            text=f"🗑 {short}",
            callback_data=f"adm_note_del:{n['id']}:{user_id}:{booking_id or 0}",
        )])
    buttons.append([InlineKeyboardButton(
        text="➕ Добавить заметку",
        callback_data=f"adm_note_add:{user_id}:{booking_id or 0}",
    )])
    if booking_id:
        buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_bk_detail:{booking_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
