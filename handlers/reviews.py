import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import database as db
from keyboards.inline import rating_kb, WEEKDAYS_RU, MONTHS_RU
from keyboards.reply import main_menu, cancel_kb

logger = logging.getLogger(__name__)
router = Router()


class ReviewStates(StatesGroup):
    writing_comment = State()


# ──────────────────── Start review ────────────────────

@router.callback_query(F.data.startswith("review_start:"))
async def review_start(callback: CallbackQuery) -> None:
    booking_id = int(callback.data.split(":")[1])  # type: ignore
    b = await db.get_booking(booking_id)
    if not b or b["status"] != "completed":
        await callback.answer("Отзыв можно оставить только для завершённой записи", show_alert=True)
        return

    existing = await db.get_review_by_booking(booking_id)
    if existing:
        await callback.answer("Вы уже оставили отзыв для этой записи", show_alert=True)
        return

    await callback.message.edit_text(  # type: ignore
        f"⭐ <b>Оценка записи #{booking_id}</b>\n\n"
        f"📋 Услуга: {b['service_name']}\n"
        f"👤 Мастер: {b['master_name']}\n\n"
        f"Поставьте оценку:",
        parse_mode=ParseMode.HTML,
        reply_markup=rating_kb(booking_id),
    )
    await callback.answer()


# ──────────────────── Rating selected ────────────────────

@router.callback_query(F.data.startswith("review_rate:"))
async def review_rate(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":")  # type: ignore
    booking_id = int(parts[1])
    rating = int(parts[2])

    await state.update_data(review_booking_id=booking_id, review_rating=rating)
    await state.set_state(ReviewStates.writing_comment)

    stars = "⭐" * rating
    await callback.message.edit_text(  # type: ignore
        f"Ваша оценка: {stars} ({rating}/5)\n\n"
        f"Напишите комментарий к отзыву (или отправьте «—» чтобы пропустить):",
        parse_mode=ParseMode.HTML,
    )
    await callback.message.answer("Ожидаю ваш комментарий:", reply_markup=cancel_kb())  # type: ignore
    await callback.answer()


# ──────────────────── Comment ────────────────────

@router.message(ReviewStates.writing_comment)
async def review_comment(message: Message, state: FSMContext) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отзыв отменён.", reply_markup=main_menu())
        return

    comment = message.text.strip() if message.text else ""  # type: ignore
    if comment == "—" or comment == "-":
        comment = ""

    data = await state.get_data()
    booking_id = data["review_booking_id"]
    rating = data["review_rating"]

    b = await db.get_booking(booking_id)
    if not b:
        await state.clear()
        await message.answer("Запись не найдена.", reply_markup=main_menu())
        return

    await db.create_review(
        booking_id=booking_id,
        user_id=message.from_user.id,  # type: ignore
        master_id=b["master_id"],
        rating=rating,
        comment=comment,
    )

    await state.clear()

    stars = "⭐" * rating
    comment_text = f"\n💬 {comment}" if comment else ""
    await message.answer(
        f"✅ <b>Спасибо за отзыв!</b>\n\n"
        f"Оценка: {stars}\n"
        f"Мастер: {b['master_name']}"
        f"{comment_text}",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu(),
    )


# ──────────────────── View own review ────────────────────

@router.callback_query(F.data.startswith("review_view:"))
async def review_view(callback: CallbackQuery) -> None:
    booking_id = int(callback.data.split(":")[1])  # type: ignore
    review = await db.get_review_by_booking(booking_id)
    if not review:
        await callback.answer("Отзыв не найден", show_alert=True)
        return

    stars = "⭐" * review["rating"]
    comment_text = f"\n💬 {review['comment']}" if review["comment"] else ""

    await callback.message.edit_text(  # type: ignore
        f"📖 <b>Ваш отзыв</b>\n\n"
        f"Оценка: {stars} ({review['rating']}/5)"
        f"{comment_text}\n\n"
        f"Дата отзыва: {review['created_at']}",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data=f"my_booking:{booking_id}")],
        ]),
    )
    await callback.answer()


# ──────────────────── Master reviews (profile) ────────────────────

@router.callback_query(F.data.startswith("master_reviews:"))
async def master_reviews(callback: CallbackQuery) -> None:
    master_id = int(callback.data.split(":")[1])  # type: ignore
    master = await db.get_master(master_id)
    if not master:
        await callback.answer("Мастер не найден", show_alert=True)
        return

    reviews = await db.get_reviews_for_master(master_id)
    avg = await db.get_master_avg_rating(master_id)

    avg_text = f"⭐ {avg}" if avg else "Нет оценок"
    text = f"<b>📖 Отзывы — {master['name']}</b>\n"
    text += f"Средняя оценка: {avg_text}\n"
    text += f"Всего отзывов: {len(reviews)}\n\n"

    if not reviews:
        text += "<i>Пока нет отзывов.</i>"
    else:
        for r in reviews[:10]:  # limit to 10
            stars = "⭐" * r["rating"]
            comment = f"\n  💬 {r['comment']}" if r["comment"] else ""
            text += (
                f"{stars} — {r['service_name']} ({r['date']})"
                f"{comment}\n\n"
            )
        if len(reviews) > 10:
            text += f"<i>...и ещё {len(reviews) - 10} отзывов</i>"

    await callback.message.edit_text(  # type: ignore
        text, parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_my_bookings")],
        ]),
    )
    await callback.answer()
