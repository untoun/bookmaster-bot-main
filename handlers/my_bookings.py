from datetime import date

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ParseMode

import database as db
from keyboards.inline import (
    user_bookings_kb, cancel_booking_kb, completed_booking_kb,
    WEEKDAYS_RU, MONTHS_RU,
)
from keyboards.reply import main_menu

router = Router()

STATUS_LABELS = {
    "confirmed": "🟢 Подтверждена",
    "completed": "✅ Завершена",
    "cancelled": "🔴 Отменена",
}


@router.message(F.text == "📖 Мои записи")
async def my_bookings(message: Message) -> None:
    bookings = await db.get_user_bookings(message.from_user.id)  # type: ignore
    if not bookings:
        await message.answer("У вас пока нет записей.", reply_markup=main_menu())
        return

    await message.answer(
        "<b>📖 Ваши записи:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=user_bookings_kb(bookings),
    )


@router.callback_query(F.data.startswith("my_booking:"))
async def show_booking(callback: CallbackQuery) -> None:
    booking_id = int(callback.data.split(":")[1])  # type: ignore
    b = await db.get_booking(booking_id)
    if not b:
        await callback.answer("Запись не найдена", show_alert=True)
        return

    d = date.fromisoformat(b["date"])
    wd = WEEKDAYS_RU[d.weekday()]
    month = MONTHS_RU[d.month]
    status = STATUS_LABELS.get(b["status"], b["status"])

    text = (
        f"<b>Запись #{b['id']}</b>\n\n"
        f"📋 Услуга: <b>{b['service_name']}</b>\n"
        f"👤 Мастер: <b>{b['master_name']}</b>\n"
        f"📅 Дата: <b>{wd}, {d.day} {month}</b>\n"
        f"🕐 Время: <b>{b['time']}</b>\n"
        f"⏱ Длительность: <b>{b['duration_minutes']} мин</b>\n"
        f"💰 Стоимость: <b>{int(b['price'])} р.</b>\n"
        f"📌 Статус: {status}\n"
    )

    if b["status"] == "confirmed" and d >= date.today():
        await callback.message.edit_text(  # type: ignore
            text, parse_mode=ParseMode.HTML,
            reply_markup=cancel_booking_kb(booking_id),
        )
    elif b["status"] == "completed":
        # Check if already has review
        review = await db.get_review_by_booking(booking_id)
        has_review = review is not None
        await callback.message.edit_text(  # type: ignore
            text, parse_mode=ParseMode.HTML,
            reply_markup=completed_booking_kb(booking_id, has_review),
        )
    else:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        await callback.message.edit_text(  # type: ignore
            text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_my_bookings")],
            ]),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("cancel_booking:"))
async def cancel_booking(callback: CallbackQuery) -> None:
    booking_id = int(callback.data.split(":")[1])  # type: ignore
    b = await db.get_booking(booking_id)
    if not b or b["user_id"] != callback.from_user.id:
        await callback.answer("Ошибка", show_alert=True)
        return
    await db.update_booking_status(booking_id, "cancelled")
    await callback.answer("Запись отменена", show_alert=True)
    # Refresh list
    await _show_bookings_list(callback)


@router.callback_query(F.data == "back_to_my_bookings")
async def back_to_list(callback: CallbackQuery) -> None:
    await _show_bookings_list(callback)


async def _show_bookings_list(callback: CallbackQuery) -> None:
    bookings = await db.get_user_bookings(callback.from_user.id)
    if not bookings:
        await callback.message.edit_text("У вас пока нет записей.")  # type: ignore
    else:
        await callback.message.edit_text(  # type: ignore
            "<b>📖 Ваши записи:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=user_bookings_kb(bookings),
        )
    await callback.answer()
