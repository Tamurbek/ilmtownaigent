"""
Telegram tugmalar (klaviaturalar).
Barcha tugmalar shu yerda yaratiladi.
"""
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


def main_employee_keyboard() -> ReplyKeyboardMarkup:
    """Xodim uchun asosiy tugmalar"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🟢 Keldim"), KeyboardButton(text="🔴 Ketdim")],
            [KeyboardButton(text="📋 Vazifalarim"), KeyboardButton(text="📦 Ish qo'shish")],
            [KeyboardButton(text="📊 Hisobot"), KeyboardButton(text="💰 Daromadim")],
            [KeyboardButton(text="💼 Loyihalarim"), KeyboardButton(text="📅 Davomat")],
            [KeyboardButton(text="⭐ Mening KPI"), KeyboardButton(text="ℹ️ Yordam")],
        ],
        resize_keyboard=True,
    )


def main_admin_keyboard() -> ReplyKeyboardMarkup:
    """Direktor uchun asosiy tugmalar"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🤖 Avto vazifa"), KeyboardButton(text="➕ Vazifa berish")],
            [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="⭐ KPI hisob")],
            [KeyboardButton(text="🎯 Mijozlar"), KeyboardButton(text="💼 Loyihalar")],
            [KeyboardButton(text="👥 Xodimlar"), KeyboardButton(text="⚠️ Intizom")],
            [KeyboardButton(text="ℹ️ Yordam")],
        ],
        resize_keyboard=True,
    )


def main_client_keyboard() -> ReplyKeyboardMarkup:
    """Mijoz uchun asosiy tugmalar (guruhda ko'rinmaydi, shaxsiy chatda)"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Status"), KeyboardButton(text="📝 Brief")],
            [KeyboardButton(text="ℹ️ Yordam")],
        ],
        resize_keyboard=True,
    )


def cancel_keyboard() -> ReplyKeyboardMarkup:
    """Bekor qilish tugmasi"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True,
    )


def brief_skip_keyboard() -> ReplyKeyboardMarkup:
    """Brief to'ldirishda tashlab ketish"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⏭ O'tkazib yuborish")],
            [KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True,
    )
