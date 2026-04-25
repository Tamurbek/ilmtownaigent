"""
Vazifa tasdiqlash:
- /vazifalarim (yoki tugma) → faol vazifalar ro'yxati har birida [✅ Bajarildi] tugmasi bilan
- Xodim tugmani bosadi → bot izoh va havolani so'raydi
- Xodim javob beradi → vazifa "Bajarildi" holatiga o'tadi
- Direktor guruhiga xabar boradi
"""
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.config import config
from bot.services.notion_service import notion_service
from bot.utils.messages import format_task
from bot.utils.keyboards import main_employee_keyboard, cancel_keyboard

router = Router()


class TaskCompleteState(StatesGroup):
    """Vazifa tasdiqlash holati"""
    waiting_for_result = State()


# ==================== VAZIFALAR RO'YXATI (TUGMALAR BILAN) ====================

@router.message(Command("vazifalarim"))
@router.message(F.text == "📋 Vazifalarim")
async def cmd_my_tasks(message: Message):
    """Faol vazifalarni inline tugmalar bilan ko'rsatish"""
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

    tasks = await notion_service.get_tasks_by_employee_telegram_id(user_id)

    if not tasks:
        await message.answer(
            "✅ Sizda faol vazifalar yo'q!\n\nYaxshi ish, dam oling 😊"
        )
        return

    await message.answer(
        f"📋 <b>Sizning faol vazifalaringiz ({len(tasks)} ta):</b>\n\n"
        f"<i>Vazifani bajarganingizdan keyin pastdagi tugmani bosing.</i>"
    )

    # Har bir vazifa uchun alohida xabar (tugma bilan)
    for task in tasks[:10]:  # Ko'pi bilan 10 ta
        task_id = task["id"]
        task_name = notion_service._get_title(task)
        deadline = notion_service._get_date(task, "Muddat") or "Belgilanmagan"
        priority = notion_service._get_select_value(task, "Prioritet") or "Orta"
        category = notion_service._get_select_value(task, "Kategoriya") or "—"

        # Loyiha nomini olamiz
        project_ids = notion_service._get_relation_ids(task, "Loyiha")
        project_name = ""
        if project_ids:
            project = await notion_service.get_project_by_id(project_ids[0])
            if project:
                project_name = notion_service._get_title(project)

        priority_emoji = {
            "Shoshilinch": "🔴",
            "Yuqori": "🟠",
            "Orta": "🟡",
            "Past": "⚪",
        }.get(priority, "⚪")

        text = (
            f"{priority_emoji} <b>{task_name}</b>\n"
            f"📅 Muddat: {deadline}\n"
            f"🏷 Kategoriya: {category}\n"
        )
        if project_name:
            text += f"💼 Loyiha: {project_name}\n"

        # Inline tugma — vazifa ID si bilan
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Bajarildi",
                        callback_data=f"complete_task:{task_id}",
                    )
                ]
            ]
        )

        await message.answer(text, reply_markup=keyboard)

    if len(tasks) > 10:
        await message.answer(
            f"<i>Va yana {len(tasks) - 10} ta vazifa bor. "
            f"Eng muhimlarini avval bajaring.</i>"
        )


# ==================== TUGMA BOSILDI - IZOH SO'RAYDI ====================

@router.callback_query(F.data.startswith("complete_task:"))
async def callback_complete_task(callback: CallbackQuery, state: FSMContext):
    """Xodim ✅ Bajarildi tugmasini bosdi"""
    task_id = callback.data.split(":", 1)[1]

    # Vazifani Notion'dan olamiz
    task = await notion_service.get_task_by_id(task_id)
    if not task:
        await callback.answer("❌ Vazifa topilmadi", show_alert=True)
        return

    task_name = notion_service._get_title(task)
    current_status = notion_service._get_select_value(task, "Holati")

    # Allaqachon bajarilganmi?
    if current_status == "Bajarildi":
        await callback.answer("ℹ️ Bu vazifa allaqachon bajarilgan", show_alert=True)
        return

    # Holatni saqlaymiz
    await state.set_state(TaskCompleteState.waiting_for_result)
    await state.update_data(task_id=task_id, task_name=task_name)

    await callback.message.answer(
        f"📝 <b>Vazifani tasdiqlash: {task_name}</b>\n\n"
        f"Iltimos, quyidagilardan birini yuboring:\n"
        f"• Natija havolasi (Google Drive, Notion, dropbox va h.k.)\n"
        f"• Yoki qisqa izoh — nima qilganingiz haqida\n"
        f"• Yoki ikkalasini birga: <code>https://link.com — izoh matni</code>\n\n"
        f"<i>Yoki bekor qilish uchun pastdagi tugmani bosing.</i>",
        reply_markup=cancel_keyboard(),
    )

    await callback.answer()  # tugmani "yashil" qilish


# ==================== BEKOR QILISH ====================

@router.message(TaskCompleteState.waiting_for_result, F.text == "❌ Bekor qilish")
async def cmd_complete_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Tasdiqlash bekor qilindi.",
        reply_markup=main_employee_keyboard(),
    )


# ==================== IZOH/HAVOLA OLISH VA NOTION'GA YOZISH ====================

@router.message(TaskCompleteState.waiting_for_result)
async def cmd_complete_save(message: Message, state: FSMContext, bot: Bot):
    """Vazifani Notion'da 'Bajarildi' qilamiz"""
    data = await state.get_data()
    task_id = data.get("task_id")
    task_name = data.get("task_name", "Vazifa")

    if not task_id:
        await state.clear()
        await message.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")
        return

    # Matnni tahlil qilamiz: havola va izoh
    text = message.text.strip()
    result_link = ""
    completion_note = text

    # URL bormi?
    import re
    url_pattern = r'https?://[^\s]+'
    urls = re.findall(url_pattern, text)
    if urls:
        result_link = urls[0]
        # Izohdan URL ni olib tashlaymiz
        completion_note = re.sub(url_pattern, "", text).strip(" —-")
        if not completion_note:
            completion_note = "Bajarildi"

    user_id = str(message.from_user.id)
    employee = await notion_service.find_employee_by_telegram_id(user_id)
    employee_name = (
        notion_service._get_title(employee) if employee else "Xodim"
    )

    try:
        await notion_service.complete_task(
            task_id=task_id,
            result_link=result_link,
            completion_note=completion_note,
        )

        # Xodimga tasdiq
        success_text = (
            f"✅ <b>Ajoyib ish, {employee_name}!</b>\n\n"
            f"📌 <b>{task_name}</b> vazifasi bajarildi deb belgilandi.\n"
        )
        if result_link:
            success_text += f"🔗 Havola: {result_link}\n"
        success_text += f"\n<i>Notion'da yangilandi.</i>"

        await message.answer(success_text, reply_markup=main_employee_keyboard())

        # Direktorga xabar
        if config.ADMIN_TELEGRAM_ID:
            try:
                admin_text = (
                    f"✅ <b>Vazifa bajarildi</b>\n\n"
                    f"👤 Xodim: {employee_name}\n"
                    f"📌 Vazifa: {task_name}\n"
                )
                if result_link:
                    admin_text += f"🔗 Havola: {result_link}\n"
                if completion_note and completion_note != "Bajarildi":
                    admin_text += f"💬 Izoh: {completion_note}\n"

                await bot.send_message(
                    chat_id=config.ADMIN_TELEGRAM_ID, text=admin_text
                )
            except Exception:
                pass

        # Direktor guruhiga ham xabar (agar sozlangan bo'lsa)
        if config.ADMIN_GROUP_ID:
            try:
                await bot.send_message(
                    chat_id=config.ADMIN_GROUP_ID,
                    text=(
                        f"✅ {employee_name} <b>{task_name}</b> "
                        f"vazifasini bajardi."
                    ),
                )
            except Exception:
                pass

    except Exception as e:
        await message.answer(
            f"❌ Xatolik: vazifani yangilab bo'lmadi.\n<code>{str(e)[:200]}</code>",
            reply_markup=main_employee_keyboard(),
        )

    await state.clear()
