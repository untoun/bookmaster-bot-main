from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.enums import ParseMode

from keyboards.reply import main_menu

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "<b>👋 Добро пожаловать в BookMaster!</b>\n\n"
        "Я помогу вам записаться на услугу.\n\n"
        "Выберите действие в меню ниже:",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu(),
    )


@router.message(Command("help"))
@router.message(F.text == "ℹ️ Помощь")
async def cmd_help(message: Message) -> None:
    await message.answer(
        "<b>📚 Помощь</b>\n\n"
        "📋 <b>Записаться</b> — выбрать услугу, мастера, дату и время\n"
        "📖 <b>Мои записи</b> — просмотр, отмена и повторная запись\n"
        "🔍 <b>Поиск услуги</b> — найти услугу по названию\n"
        "👤 <b>Профиль</b> — ваша статистика и программа лояльности\n"
        "ℹ️ <b>Помощь</b> — это сообщение\n\n"
        "<b>Дополнительные команды:</b>\n"
        "/profile — ваш профиль и статистика\n"
        "/search — поиск услуги по названию\n\n"
        "Для записи просто нажмите кнопку <b>📋 Записаться</b> "
        "и следуйте инструкциям.",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu(),
    )
