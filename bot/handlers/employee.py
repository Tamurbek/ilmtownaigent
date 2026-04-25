"""
Xodimlar uchun buyruqlar:
- /vazifalarim yoki "📋 Vazifalarim"
- /hisobot yoki "📊 Hisobot"
- /loyihalarim yoki "💼 Loyihalarim"
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.services.notion_service import notion_service
from bot.utils.messages import format_task
from bot.utils.keyboards import main_employee_keyboard, cancel_keyboard

router = Router()


class ReportState(StatesGroup):
    """Hisobot topshirish holati"""
    waiting_for_text = State()


@router.message(Command("vazifalarim_oddiy"))
async def cmd_my_tasks_simple(message: Message):
    """Eski versiya - hozir ishlatilmaydi (task_complete.py ga o'tdi)"""
    pass


@router.message(Command("hisobot"))
@router.message(F.text == "📊 Hisobot")
async def cmd_report_start(message: Message, state: FSMContext):
    """Kunlik hisobot topshirish boshlash"""
    if message.chat.type != "private":
        return

    user_id = str(message.from_user.id)
    employee = await notion_service.find_employee_by_telegram_id(user_id)

    if not employee:
        await message.answer(
            "❌ Siz tizimda ro'yxatdan o'tmagansiz.\n"
            "Direktor sizni Notion 'Xodimlar' bazasiga qo'shishi kerak."
        )
        return

    await state.set_state(ReportState.waiting_for_text)
    await state.update_data(employee_id=employee["id"])

    await message.answer(
        "📝 <b>Kunlik hisobot</b>\n\n"
        "Bugun qanday ishlarni bajardingiz? Batafsil yozib yuboring.\n\n"
        "<i>Misol: 'X mijoz uchun 3 ta reels senariyi yozdim, Y mijoz uchun postlarni tahrirladim.'</i>",
        reply_markup=cancel_keyboard(),
    )


@router.message(ReportState.waiting_for_text, F.text == "❌ Bekor qilish")
async def cmd_report_cancel(message: Message, state: FSMContext):
    """Hisobotni bekor qilish"""
    await state.clear()
    await message.answer(
        "❌ Hisobot bekor qilindi.",
        reply_markup=main_employee_keyboard(),
    )


@router.message(ReportState.waiting_for_text)
async def cmd_report_save(message: Message, state: FSMContext):
    """Hisobot matnini Notion'ga saqlash"""
    data = await state.get_data()
    employee_id = data.get("employee_id")

    if not employee_id:
        await state.clear()
        await message.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")
        return

    try:
        await notion_service.create_employee_report(
            employee_id=employee_id,
            report_text=message.text,
        )
        await message.answer(
            "✅ <b>Hisobot qabul qilindi!</b>\n\n"
            "Rahmat, hisobot Notion'ga saqlandi.",
            reply_markup=main_employee_keyboard(),
        )
    except Exception as e:
        await message.answer(
            f"❌ Xatolik: hisobotni saqlab bo'lmadi.\n<code>{str(e)[:200]}</code>",
            reply_markup=main_employee_keyboard(),
        )

    await state.clear()


@router.message(Command("loyihalarim"))
@router.message(F.text == "💼 Loyihalarim")
async def cmd_my_projects(message: Message):
    """Xodim boshqarayotgan loyihalarni ko'rsatish"""
    if message.chat.type != "private":
        return

    user_id = str(message.from_user.id)
    employee = await notion_service.find_employee_by_telegram_id(user_id)

    if not employee:
        await message.answer("❌ Siz tizimda ro'yxatdan o'tmagansiz.")
        return

    # Xodim mas'ul bo'lgan loyihalarni qidiramiz
    from bot.config import config

    response = await notion_service.client.databases.query(
        database_id=config.DB_PROJECTS,
        filter={
            "property": "Masul menejer",
            "relation": {"contains": employee["id"]},
        },
    )

    projects = response.get("results", [])

    if not projects:
        await message.answer("💼 Sizda boshqarayotgan loyihalar yo'q.")
        return

    text = f"💼 <b>Sizning loyihalaringiz ({len(projects)} ta):</b>\n\n"

    for project in projects[:10]:
        name = notion_service._get_title(project)
        stage = notion_service._get_select_value(project, "Bosqich") or "Belgilanmagan"
        priority = notion_service._get_select_value(project, "Prioritet") or "Orta"

        priority_emoji = {
            "Juda yuqori": "🔴",
            "Yuqori": "🟠",
            "Orta": "🟡",
            "Past": "⚪",
        }.get(priority, "⚪")

        text += f"{priority_emoji} <b>{name}</b>\n   📍 {stage}\n\n"

    if len(projects) > 10:
        text += f"\n<i>Va yana {len(projects) - 10} ta loyiha...</i>"

    await message.answer(text)
