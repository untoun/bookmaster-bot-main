from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Записаться"), KeyboardButton(text="📖 Мои записи")],
            [KeyboardButton(text="🔍 Поиск услуги"), KeyboardButton(text="👤 Профиль")],
            [KeyboardButton(text="ℹ️ Помощь")],
        ],
        resize_keyboard=True,
    )


def admin_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔧 Услуги"), KeyboardButton(text="👤 Мастера")],
            [KeyboardButton(text="📅 Расписание"), KeyboardButton(text="📊 Записи")],
            [KeyboardButton(text="🏖 Выходные"), KeyboardButton(text="📝 Заметки")],
            [KeyboardButton(text="◀️ Назад")],
        ],
        resize_keyboard=True,
    )


def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True,
    )
