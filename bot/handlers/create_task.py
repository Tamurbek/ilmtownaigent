"""
Direktor xodimlarga vazifa berish handler.
Savol-javob (FSM) tariqasida ishlaydi.

/vazifa_ber yoki "➕ Vazifa berish" tugmasi bosilganda boshlanadi.
"""
from datetime import datetime
import re

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
from bot.utils.keyboards import main_admin_keyboard, cancel_keyboard

router = Router()


# Vazifa kategoriyalari (Notion bazasi bilan mos)
TASK_CATEGORIES = [
    "Senariy",
    "Syomka",
    "Montaj",
    "Dizayn",
    "Kopirayting",
    "SMM",
    "Reklama",
    "Mijoz bilan aloqa",
    "Boshqa",
]

# Prioritet darajalari
TASK_PRIORITIES = ["Past", "Orta", "Yuqori", "Shoshilinch"]

PRIORITY_EMOJI = {
    "Past": "⚪",
    "Orta": "🟡",
    "Yuqori": "🟠",
    "Shoshilinch": "🔴",
}


class CreateTaskState(StatesGroup):
    """Vazifa yaratish bosqichlari"""
    choosing_employee = State()
    entering_name = State()
    choosing_project = State()
    choosing_category = State()
    choosing_priority = State()
    entering_deadline = State()
    entering_description = State()
    confirming = State()


# ==================== /vazifa_ber - BOSHLASH ====================

@router.message(Command("vazifa_ber"))
@router.message(F.text == "➕ Vazifa berish")
async def cmd_create_task_start(message: Message, state: FSMContext):
    """Vazifa berish jarayonini boshlash"""
    if message.chat.type != "private":
        return

    # Kim chaqirayapti? Direktor yoki SMM menejer bo'lishi kerak
    user_id = message.from_user.id

    # Direktormi?
    is_admin = user_id == config.ADMIN_TELEGRAM_ID

    # Yoki xodimi (SMM menejer rolida)?
    is_manager = False
    if not is_admin:
        employee = await notion_service.find_employee_by_telegram_id(str(user_id))
        if employee:
            role = notion_service._get_select_value(employee, "Lavozim")
            if role in ["Direktor", "SMM Menejer"]:
                is_manager = True

    if not (is_admin or is_manager):
        await message.answer(
            "⛔ Bu buyruq faqat direktor va SMM menejerlar uchun.\n"
            "Agar siz xodim bo'lsangiz, vazifani direktordan oling."
        )
        return

    # Xodimlar ro'yxatini olamiz
    employees = await notion_service.get_all_employees()
    if not employees:
        await message.answer(
            "❌ Notion'da xodimlar yo'q.\n"
            "Avval Xodimlar bazasiga xodimlarni qo'shing."
        )
        return

    # Telegram ID si bor xodimlarni filtr qilamiz
    employees_with_tg = [
        e
        for e in employees
        if notion_service._get_rich_text(e, "Telegram ID")
    ]

    if not employees_with_tg:
        await message.answer(
            "⚠️ Hech bir xodimda Telegram ID yo'q.\n"
            "Notion'da xodimlarga Telegram ID qo'shing, keyin vazifa bera olasiz."
        )
        return

    # Inline tugmalar - har bir xodim uchun
    keyboard_buttons = []
    for emp in employees_with_tg[:20]:  # 20 ta cheklov
        emp_id = emp["id"]
        emp_name = notion_service._get_title(emp)
        emp_role = notion_service._get_select_value(emp, "Lavozim") or ""

        button_text = f"{emp_name}"
        if emp_role:
            button_text += f" ({emp_role})"

        keyboard_buttons.append(
            [
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"task_emp:{emp_id}",
                )
            ]
        )

    # Bekor qilish tugmasi
    keyboard_buttons.append(
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="task_cancel")]
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await state.set_state(CreateTaskState.choosing_employee)
    await message.answer(
        "➕ <b>Yangi vazifa berish</b>\n\n"
        "👤 <b>1/7:</b> Vazifa kimga?\n"
        "<i>Quyidagi ro'yxatdan xodimni tanlang:</i>",
        reply_markup=keyboard,
    )


# ==================== BEKOR QILISH ====================

@router.callback_query(F.data == "task_cancel")
async def callback_cancel(callback: CallbackQuery, state: FSMContext):
    """Vazifa berishni bekor qilish (callback)"""
    await state.clear()
    await callback.message.answer(
        "❌ Vazifa berish bekor qilindi.",
        reply_markup=main_admin_keyboard(),
    )
    await callback.answer()


@router.message(F.text == "❌ Bekor qilish", CreateTaskState())
async def text_cancel(message: Message, state: FSMContext):
    """Vazifa berishni bekor qilish (matn)"""
    await state.clear()
    await message.answer(
        "❌ Vazifa berish bekor qilindi.",
        reply_markup=main_admin_keyboard(),
    )


# ==================== 1. XODIM TANLANDI ====================

@router.callback_query(
    CreateTaskState.choosing_employee, F.data.startswith("task_emp:")
)
async def callback_employee_selected(
    callback: CallbackQuery, state: FSMContext
):
    """Xodim tanlandi - vazifa nomini so'raymiz"""
    emp_id = callback.data.split(":", 1)[1]

    # Xodim ma'lumotlarini olamiz
    try:
        employee = await notion_service.client.pages.retrieve(page_id=emp_id)
    except Exception:
        await callback.answer("❌ Xodim topilmadi", show_alert=True)
        return

    emp_name = notion_service._get_title(employee)

    await state.update_data(employee_id=emp_id, employee_name=emp_name)
    await state.set_state(CreateTaskState.entering_name)

    await callback.message.answer(
        f"✅ Xodim tanlandi: <b>{emp_name}</b>\n\n"
        f"📝 <b>2/7:</b> Vazifa nomini yozing.\n"
        f"<i>Misol: Instagram uchun 5 ta post yozish, "
        f"Saytni yangilash, Mijoz bilan kelishish va h.k.</i>",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


# ==================== 2. VAZIFA NOMI ====================

@router.message(CreateTaskState.entering_name, F.text)
async def task_name_entered(message: Message, state: FSMContext):
    """Vazifa nomi kiritildi - loyihalarni so'raymiz"""
    if message.text == "❌ Bekor qilish":
        return  # text_cancel handler bajaradi

    task_name = message.text.strip()
    if len(task_name) < 3:
        await message.answer(
            "⚠️ Vazifa nomi juda qisqa. Iltimos, tushunarli nom yozing."
        )
        return

    if len(task_name) > 200:
        await message.answer(
            "⚠️ Vazifa nomi juda uzun (200 belgidan ortiq). Qisqartiring."
        )
        return

    await state.update_data(task_name=task_name)

    # Faol loyihalar ro'yxati
    projects = await notion_service.get_active_projects()

    # Inline tugmalar
    keyboard_buttons = []

    # "Loyihasiz" varianti
    keyboard_buttons.append(
        [
            InlineKeyboardButton(
                text="🚫 Loyihasiz (umumiy vazifa)",
                callback_data="task_proj:none",
            )
        ]
    )

    # Loyihalar (max 15 ta)
    for proj in projects[:15]:
        proj_id = proj["id"]
        proj_name = notion_service._get_title(proj)
        # Nomni qisqartiramiz agar uzun bo'lsa
        if len(proj_name) > 50:
            proj_name = proj_name[:47] + "..."

        keyboard_buttons.append(
            [
                InlineKeyboardButton(
                    text=f"💼 {proj_name}",
                    callback_data=f"task_proj:{proj_id}",
                )
            ]
        )

    keyboard_buttons.append(
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="task_cancel")]
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await state.set_state(CreateTaskState.choosing_project)
    await message.answer(
        f"✅ Vazifa nomi: <b>{task_name}</b>\n\n"
        f"💼 <b>3/7:</b> Qaysi loyihaga tegishli?",
        reply_markup=keyboard,
    )


# ==================== 3. LOYIHA TANLANDI ====================

@router.callback_query(
    CreateTaskState.choosing_project, F.data.startswith("task_proj:")
)
async def callback_project_selected(
    callback: CallbackQuery, state: FSMContext
):
    """Loyiha tanlandi - kategoriya so'raymiz"""
    proj_value = callback.data.split(":", 1)[1]

    if proj_value == "none":
        await state.update_data(project_id=None, project_name="Loyihasiz")
        proj_display = "🚫 Loyihasiz"
    else:
        try:
            project = await notion_service.get_project_by_id(proj_value)
            proj_name = notion_service._get_title(project)
            await state.update_data(project_id=proj_value, project_name=proj_name)
            proj_display = f"💼 {proj_name}"
        except Exception:
            await callback.answer("❌ Loyiha topilmadi", show_alert=True)
            return

    # Kategoriya tanlash
    keyboard_buttons = []
    row = []
    for i, cat in enumerate(TASK_CATEGORIES):
        row.append(
            InlineKeyboardButton(text=cat, callback_data=f"task_cat:{cat}")
        )
        # 2 ustun
        if (i + 1) % 2 == 0:
            keyboard_buttons.append(row)
            row = []
    if row:
        keyboard_buttons.append(row)

    keyboard_buttons.append(
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="task_cancel")]
    )

    await state.set_state(CreateTaskState.choosing_category)
    await callback.message.answer(
        f"✅ Loyiha: {proj_display}\n\n"
        f"🏷 <b>4/7:</b> Vazifa kategoriyasi?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
    )
    await callback.answer()


# ==================== 4. KATEGORIYA TANLANDI ====================

@router.callback_query(
    CreateTaskState.choosing_category, F.data.startswith("task_cat:")
)
async def callback_category_selected(
    callback: CallbackQuery, state: FSMContext
):
    """Kategoriya tanlandi - prioritet so'raymiz"""
    category = callback.data.split(":", 1)[1]
    await state.update_data(category=category)

    # Prioritet tugmalari
    keyboard_buttons = [
        [
            InlineKeyboardButton(
                text=f"{PRIORITY_EMOJI[p]} {p}",
                callback_data=f"task_pri:{p}",
            )
        ]
        for p in TASK_PRIORITIES
    ]
    keyboard_buttons.append(
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="task_cancel")]
    )

    await state.set_state(CreateTaskState.choosing_priority)
    await callback.message.answer(
        f"✅ Kategoriya: <b>{category}</b>\n\n"
        f"⭐ <b>5/7:</b> Vazifa prioriteti?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
    )
    await callback.answer()


# ==================== 5. PRIORITET TANLANDI ====================

@router.callback_query(
    CreateTaskState.choosing_priority, F.data.startswith("task_pri:")
)
async def callback_priority_selected(
    callback: CallbackQuery, state: FSMContext
):
    """Prioritet tanlandi - muddat so'raymiz"""
    priority = callback.data.split(":", 1)[1]
    await state.update_data(priority=priority)

    await state.set_state(CreateTaskState.entering_deadline)
    await callback.message.answer(
        f"✅ Prioritet: {PRIORITY_EMOJI[priority]} <b>{priority}</b>\n\n"
        f"📅 <b>6/7:</b> Vazifa muddati?\n\n"
        f"<i>Sanani shu formatda yozing: <b>DD.MM.YYYY</b>\n"
        f"Misol: 30.04.2026\n\n"
        f"Yoki:\n"
        f"• <b>bugun</b> — bugungi sana\n"
        f"• <b>ertaga</b> — ertangi sana\n"
        f"• <b>yoq</b> — muddat belgilamaslik</i>",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


# ==================== 6. MUDDAT KIRITILDI ====================

@router.message(CreateTaskState.entering_deadline, F.text)
async def deadline_entered(message: Message, state: FSMContext):
    """Muddat kiritildi - tavsif so'raymiz"""
    if message.text == "❌ Bekor qilish":
        return

    text = message.text.strip().lower()
    deadline = None
    deadline_display = "Belgilanmagan"

    if text in ["yoq", "yo'q", "skip"]:
        deadline = None
        deadline_display = "Belgilanmagan"
    elif text == "bugun":
        today = datetime.now().strftime("%Y-%m-%d")
        deadline = today
        deadline_display = datetime.now().strftime("%d.%m.%Y") + " (bugun)"
    elif text == "ertaga":
        from datetime import timedelta
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        deadline = tomorrow
        deadline_display = (datetime.now() + timedelta(days=1)).strftime(
            "%d.%m.%Y"
        ) + " (ertaga)"
    else:
        # DD.MM.YYYY formatini tahlil qilamiz
        match = re.match(r"^(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})$", text)
        if not match:
            await message.answer(
                "⚠️ Sana noto'g'ri formatda.\n\n"
                "Iltimos shunday yozing:\n"
                "• <code>30.04.2026</code>\n"
                "• <code>bugun</code>\n"
                "• <code>ertaga</code>\n"
                "• <code>yoq</code> — muddatni belgilamaslik"
            )
            return

        day, month, year = match.groups()
        try:
            dt = datetime(int(year), int(month), int(day))
            if dt.date() < datetime.now().date():
                await message.answer(
                    "⚠️ Bu sana o'tib ketgan!\n"
                    "Iltimos, kelajakdagi sanani kiriting."
                )
                return
            deadline = dt.strftime("%Y-%m-%d")
            deadline_display = dt.strftime("%d.%m.%Y")
        except ValueError:
            await message.answer(
                "⚠️ Bunday sana mavjud emas. Qaytadan yozing."
            )
            return

    await state.update_data(deadline=deadline, deadline_display=deadline_display)
    await state.set_state(CreateTaskState.entering_description)

    await message.answer(
        f"✅ Muddat: <b>{deadline_display}</b>\n\n"
        f"📝 <b>7/7:</b> Vazifaga batafsil tavsif yoki ko'rsatma yozing.\n\n"
        f"<i>Misol: 'Bizning Instagram bio'da yangi xizmat haqida yozish kerak. "
        f"Maksimum 150 belgi, hashtag qo'shing.'\n\n"
        f"Yoki <b>yoq</b> deb yozing — tavsifsiz qoldirish uchun.</i>",
        reply_markup=cancel_keyboard(),
    )


# ==================== 7. TAVSIF KIRITILDI - TASDIQLASH ====================

@router.message(CreateTaskState.entering_description, F.text)
async def description_entered(message: Message, state: FSMContext):
    """Tavsif kiritildi - oxirgi tasdiq"""
    if message.text == "❌ Bekor qilish":
        return

    text = message.text.strip()
    if text.lower() in ["yoq", "yo'q", "skip"]:
        description = ""
    else:
        description = text[:2000]  # 2000 belgi cheklov

    await state.update_data(description=description)

    # Barcha ma'lumotlarni ko'rsatamiz
    data = await state.get_data()

    summary = (
        "📋 <b>Vazifa ma'lumotlari:</b>\n\n"
        f"👤 <b>Xodim:</b> {data['employee_name']}\n"
        f"📝 <b>Vazifa:</b> {data['task_name']}\n"
        f"💼 <b>Loyiha:</b> {data['project_name']}\n"
        f"🏷 <b>Kategoriya:</b> {data['category']}\n"
        f"⭐ <b>Prioritet:</b> {PRIORITY_EMOJI[data['priority']]} {data['priority']}\n"
        f"📅 <b>Muddat:</b> {data['deadline_display']}\n"
    )
    if description:
        # Tavsifni qisqartirib ko'rsatamiz
        desc_short = description if len(description) <= 200 else description[:200] + "..."
        summary += f"\n📌 <b>Tavsif:</b>\n<i>{desc_short}</i>\n"

    summary += "\n<b>Yaratamizmi?</b>"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Ha, yaratish", callback_data="task_confirm"
                ),
                InlineKeyboardButton(
                    text="❌ Bekor qilish", callback_data="task_cancel"
                ),
            ]
        ]
    )

    await state.set_state(CreateTaskState.confirming)
    await message.answer(summary, reply_markup=keyboard)


# ==================== 8. TASDIQLANDI - NOTION'GA YOZAMIZ ====================

@router.callback_query(CreateTaskState.confirming, F.data == "task_confirm")
async def callback_task_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Vazifani Notion'ga yozish va xodimga xabar yuborish"""
    data = await state.get_data()

    try:
        # Notion'da vazifa yaratamiz
        new_task = await notion_service.create_task(
            name=data["task_name"],
            project_id=data.get("project_id"),
            employee_id=data["employee_id"],
            priority=data["priority"],
            category=data["category"],
            deadline=data.get("deadline"),
            description=data.get("description", ""),
        )

        # Direktorga muvaffaqiyat xabari
        await callback.message.answer(
            f"✅ <b>Vazifa yaratildi!</b>\n\n"
            f"📌 <b>{data['task_name']}</b>\n"
            f"👤 {data['employee_name']} ga yuborildi.\n\n"
            f"<i>Notion 'Vazifalar' bazasida ko'rishingiz mumkin.</i>",
            reply_markup=main_admin_keyboard(),
        )

        # Xodimga xabar yuboramiz
        try:
            employee = await notion_service.client.pages.retrieve(
                page_id=data["employee_id"]
            )
            telegram_id = notion_service._get_rich_text(employee, "Telegram ID")

            if telegram_id:
                # Yuboruvchi kim?
                sender_id = callback.from_user.id
                sender_name = "Direktor"
                if sender_id != config.ADMIN_TELEGRAM_ID:
                    sender = await notion_service.find_employee_by_telegram_id(
                        str(sender_id)
                    )
                    if sender:
                        sender_name = notion_service._get_title(sender)

                emp_message = (
                    f"📌 <b>Sizga yangi vazifa berildi!</b>\n\n"
                    f"📝 <b>{data['task_name']}</b>\n\n"
                    f"💼 Loyiha: {data['project_name']}\n"
                    f"🏷 Kategoriya: {data['category']}\n"
                    f"⭐ Prioritet: {PRIORITY_EMOJI[data['priority']]} {data['priority']}\n"
                    f"📅 Muddat: {data['deadline_display']}\n"
                )
                if data.get("description"):
                    emp_message += f"\n📋 <b>Tavsif:</b>\n<i>{data['description']}</i>\n"

                emp_message += (
                    f"\n<i>Bergan: {sender_name}</i>\n\n"
                    f"Bajarganingizdan keyin /vazifalarim ni bosing va "
                    f"vazifa yonidagi <b>✅ Bajarildi</b> tugmasini bosing."
                )

                # Bevosita javob beradigan tugma
                inline_kb = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="✅ Bajarildi (tasdiqlash)",
                                callback_data=f"complete_task:{new_task['id']}",
                            )
                        ]
                    ]
                )

                await bot.send_message(
                    chat_id=int(telegram_id),
                    text=emp_message,
                    reply_markup=inline_kb,
                )
            else:
                await callback.message.answer(
                    f"⚠️ Xodimga xabar yuborilmadi - Telegram ID yo'q.\n"
                    f"Vazifa Notion'da saqlandi."
                )
        except Exception as e:
            await callback.message.answer(
                f"⚠️ Vazifa yaratildi, lekin xodimga xabar yuborib bo'lmadi:\n"
                f"<code>{str(e)[:200]}</code>"
            )

    except Exception as e:
        await callback.message.answer(
            f"❌ Xatolik: vazifa yaratib bo'lmadi.\n<code>{str(e)[:200]}</code>",
            reply_markup=main_admin_keyboard(),
        )

    await state.clear()
    await callback.answer()
