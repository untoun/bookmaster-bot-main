import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode

import database as db
from config import LOYALTY_EVERY_N, LOYALTY_DISCOUNT_PERCENT
from keyboards.reply import main_menu

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("profile"))
@router.message(F.text == "👤 Профиль")
async def cmd_profile(message: Message) -> None:
    user_id = message.from_user.id  # type: ignore
    user_name = message.from_user.full_name  # type: ignore

    # Get profile stats
    stats = await db.get_user_profile_stats(user_id)
    loyalty = await db.get_loyalty(user_id)

    total_visits = loyalty["total_visits"]
    visits_until_discount = LOYALTY_EVERY_N - (total_visits % LOYALTY_EVERY_N)
    if visits_until_discount == LOYALTY_EVERY_N:
        visits_until_discount = 0

    # Loyalty status
    if loyalty["discount_available"]:
        loyalty_text = (
            f"🎁 <b>У вас есть скидка {LOYALTY_DISCOUNT_PERCENT}%!</b>\n"
            f"   Она будет применена при следующей записи."
        )
    elif visits_until_discount == 0:
        loyalty_text = f"🎉 Поздравляем! Скидка {LOYALTY_DISCOUNT_PERCENT}% доступна!"
    else:
        loyalty_text = (
            f"Следующая скидка через: <b>{visits_until_discount}</b> "
            f"{'визит' if visits_until_discount == 1 else 'визита' if 2 <= visits_until_discount <= 4 else 'визитов'}"
        )

    fav_master = stats["favorite_master"] or "—"

    text = (
        f"<b>👤 Ваш профиль</b>\n\n"
        f"Имя: <b>{user_name}</b>\n"
        f"ID: <code>{user_id}</code>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"  Всего записей: <b>{stats['total_bookings']}</b>\n"
        f"  Предстоящих: <b>{stats['upcoming']}</b>\n"
        f"  Любимый мастер: <b>{fav_master}</b>\n\n"
        f"🏆 <b>Программа лояльности:</b>\n"
        f"  Завершённых визитов: <b>{total_visits}</b>\n"
        f"  Каждый {LOYALTY_EVERY_N}-й визит — скидка {LOYALTY_DISCOUNT_PERCENT}%\n"
        f"  {loyalty_text}"
    )

    await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=main_menu())
