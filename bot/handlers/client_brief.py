"""
Mijozdan brief olish - savol-javob tariqasida.
/brief buyrug'i orqali boshlanadi, natija Notion'ga saqlanadi.
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.services.notion_service import notion_service
from bot.utils.messages import BRIEF_QUESTIONS
from bot.utils.keyboards import brief_skip_keyboard, main_client_keyboard

router = Router()


class BriefState(StatesGroup):
    """Brief to'ldirish holati"""
    answering = State()


@router.message(Command("brief"))
@router.message(F.text == "📝 Brief")
async def cmd_brief_start(message: Message, state: FSMContext):
    """Brief to'ldirishni boshlash"""
    await state.set_state(BriefState.answering)
    await state.update_data(current_question=0, answers={})

    first_key, first_question = BRIEF_QUESTIONS[0]

    await message.answer(
        "📋 <b>Brief to'ldirish</b>\n\n"
        f"Salom! Sizning biznesingiz haqida bir nechta savollarga javob bering.\n"
        f"Jami {len(BRIEF_QUESTIONS)} ta savol bo'ladi.\n\n"
        "Agar savolni o'tkazib yubormoqchi bo'lsangiz, '⏭ O'tkazib yuborish' tugmasini bosing.\n\n"
        f"━━━━━━━━━━━━━━━\n{first_question}",
        reply_markup=brief_skip_keyboard(),
    )


@router.message(BriefState.answering, F.text == "❌ Bekor qilish")
async def cmd_brief_cancel(message: Message, state: FSMContext):
    """Briefni bekor qilish"""
    await state.clear()
    await message.answer(
        "❌ Brief to'ldirish bekor qilindi.",
        reply_markup=main_client_keyboard(),
    )


@router.message(BriefState.answering)
async def cmd_brief_answer(message: Message, state: FSMContext):
    """Brief savoliga javob"""
    data = await state.get_data()
    current = data.get("current_question", 0)
    answers = data.get("answers", {})

    current_key = BRIEF_QUESTIONS[current][0]

    # Javobni saqlaymiz
    if message.text == "⏭ O'tkazib yuborish":
        answers[current_key] = "—"
    else:
        answers[current_key] = message.text

    # Keyingi savol
    next_index = current + 1

    if next_index >= len(BRIEF_QUESTIONS):
        # Barcha savollar tugadi - Notion'ga saqlaymiz
        await _save_brief_to_notion(message, answers, state)
        return

    # Keyingi savolni yuboramiz
    next_key, next_question = BRIEF_QUESTIONS[next_index]
    await state.update_data(current_question=next_index, answers=answers)

    progress = f"({next_index + 1}/{len(BRIEF_QUESTIONS)})"
    await message.answer(
        f"✅ Qabul qilindi.\n\n━━━━━━━━━━━━━━━\n{progress} {next_question}",
        reply_markup=brief_skip_keyboard(),
    )


async def _save_brief_to_notion(
    message: Message, answers: dict, state: FSMContext
):
    """Brief javoblarini Notion'ga saqlash"""
    # Matnli izohga barcha javoblarni joylaymiz
    notes = "📋 Brief javoblari:\n\n"
    for key, question in BRIEF_QUESTIONS:
        answer = answers.get(key, "—")
        notes += f"• {question}\n  → {answer}\n\n"

    brief_data = {
        "name": answers.get("name", "Yangi mijoz") or "Yangi mijoz",
        "company": answers.get("company", ""),
        "contact": answers.get("contact", ""),
        "phone": answers.get("phone", ""),
        "notes": notes,
    }

    # Guruh ID'sini qo'shamiz (agar guruhda bo'lsa)
    if message.chat.type in ["group", "supergroup"]:
        brief_data["telegram_group_id"] = str(message.chat.id)

    try:
        result = await notion_service.create_client_from_brief(brief_data)

        await message.answer(
            "🎉 <b>Rahmat! Brief to'ldirildi.</b>\n\n"
            "Jamoamiz tez orada siz bilan bog'lanadi va loyihani boshlash "
            "bo'yicha takliflarimizni taqdim etadi.\n\n"
            "📞 Savollar bo'lsa, bizga yozing.",
            reply_markup=main_client_keyboard(),
        )

        # Direktorga xabar
        from bot.config import config
        from aiogram import Bot

        bot: Bot = message.bot
        await bot.send_message(
            chat_id=config.ADMIN_TELEGRAM_ID,
            text=(
                "🔔 <b>Yangi brief keldi!</b>\n\n"
                f"Kompaniya: {brief_data['name']}\n"
                f"Aloqa: {brief_data['contact']}\n"
                f"Telefon: {brief_data['phone']}\n\n"
                "Notion'da 'Mijozlar (CRM)' bazasiga qo'shildi."
            ),
        )

    except Exception as e:
        await message.answer(
            f"❌ Xatolik: briefni saqlab bo'lmadi.\n<code>{str(e)[:200]}</code>",
            reply_markup=main_client_keyboard(),
        )

    await state.clear()


@router.message(Command("status"))
@router.message(F.text == "📍 Status")
async def cmd_status(message: Message):
    """Mijoz loyihasining hozirgi holatini ko'rsatish"""
    # Guruh ID orqali mijozni topamiz
    if message.chat.type not in ["group", "supergroup"]:
        await message.answer(
            "ℹ️ Bu buyruq sizning mijoz guruhingizda ishlaydi."
        )
        return

    group_id = str(message.chat.id)
    client = await notion_service.find_client_by_group_id(group_id)

    if not client:
        await message.answer(
            "❌ Sizning guruhingiz tizimda topilmadi.\n"
            "Direktordan guruh ID'sini Notion'ga qo'shishni so'rang."
        )
        return

    # Mijozning loyihalarini olamiz
    projects = await notion_service.get_projects_by_client(client["id"])

    if not projects:
        await message.answer("📭 Hozircha sizda faol loyihalar yo'q.")
        return

    text = "📍 <b>Sizning loyihalaringiz:</b>\n\n"
    for project in projects:
        name = notion_service._get_title(project)
        stage = notion_service._get_select_value(project, "Bosqich") or "Belgilanmagan"
        deadline = notion_service._get_date(project, "Tugash sanasi") or "Belgilanmagan"

        text += f"💼 <b>{name}</b>\n"
        text += f"   📍 Bosqich: {stage}\n"
        text += f"   📅 Tugash sanasi: {deadline}\n\n"

    await message.answer(text)
