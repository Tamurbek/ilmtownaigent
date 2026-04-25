"""
/start va /help buyruqlari uchun handlerlar
"""
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from bot.config import config
from bot.services.notion_service import notion_service
from bot.utils.messages import WELCOME_PRIVATE, WELCOME_GROUP, HELP_TEXT
from bot.utils.keyboards import (
    main_admin_keyboard,
    main_employee_keyboard,
    main_client_keyboard,
)

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Bot bilan birinchi aloqa"""
    # Guruh yoki shaxsiy chat?
    if message.chat.type in ["group", "supergroup"]:
        # Bu guruh - mijozlar yoki ichki guruh
        await message.answer(WELCOME_GROUP)
        return

    user_id = message.from_user.id

    # Direktormi?
    if user_id == config.ADMIN_TELEGRAM_ID:
        await message.answer(
            "👑 <b>Assalomu alaykum, direktor!</b>\n\n"
            "Biznestown Agency boshqaruv paneliga xush kelibsiz.\n\n"
            "<b>📌 Asosiy buyruqlar:</b>\n"
            "➕ <b>Vazifa berish</b> — xodimga yangi vazifa\n"
            "📊 <b>Statistika</b> — bugungi ko'rsatkichlar\n"
            "👥 <b>Xodimlar</b> — jamoa ro'yxati\n"
            "🎯 <b>Mijozlar</b> — mijozlar bazasi\n\n"
            "<i>Quyidagi tugmalardan foydalaning yoki /help yozing.</i>",
            reply_markup=main_admin_keyboard(),
        )
        return

    # Xodimmi?
    employee = await notion_service.find_employee_by_telegram_id(str(user_id))
    if employee:
        employee_name = notion_service._get_title(employee)
        await message.answer(
            f"👋 <b>Assalomu alaykum, {employee_name}!</b>\n\n"
            f"Biznestown Agency bot.\n\n"
            f"<b>📌 Asosiy buyruqlar:</b>\n"
            f"🟢 <b>Keldim</b> — ish boshlaganda bosing\n"
            f"🔴 <b>Ketdim</b> — ish tugatganda bosing\n"
            f"📋 <b>Vazifalarim</b> — bugungi ishlar\n"
            f"📊 <b>Hisobot</b> — kunlik hisobot\n\n"
            f"<i>Quyidagi tugmalardan foydalaning yoki /help yozing.</i>",
            reply_markup=main_employee_keyboard(),
        )
        return

    # Aks holda - mijoz yoki yangi foydalanuvchi
    await message.answer(WELCOME_PRIVATE, reply_markup=main_client_keyboard())


@router.message(Command("help"))
@router.message(F.text == "ℹ️ Yordam")
async def cmd_help(message: Message):
    """Yordam menyusi"""
    await message.answer(HELP_TEXT)
