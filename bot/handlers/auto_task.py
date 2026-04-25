"""
Avtomatik vazifa taqsimlash:
1. Direktor /avtomatik_vazifa buyrug'ini bosadi (yoki "🤖 Avto vazifa" tugmasi)
2. Bot so'raydi: kerakli ko'nikma, daraja, muddat, tavsif
3. Bot eng mos xodimni topadi (assignment_service orqali)
4. SMM menejerga tasdiqlash uchun yuboradi:
   "Vazifa Aliga taqsimlandi. Tasdiqlasizmi?"
   [✅ Tasdiqlash] [✏️ Boshqa xodimga]
5. SMM tasdiqlasa → Notion'da yaratiladi → xodimga xabar
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
from bot.services.assignment_service import assignment_service
from bot.utils.keyboards import main_admin_keyboard, cancel_keyboard

router = Router()


# Ko'nikmalar Notion bilan mos
SKILLS = [
    "Senariy yozish",
    "Oddiy syomka",
    "Murakkab syomka",
    "Drone syomka",
    "Studio syomka",
    "Oddiy montaj",
    "Murakkab montaj",
    "Reels montaj",
    "Color grading",
    "Motion design",
    "Logo dizayn",
    "Post dizayn",
    "Story dizayn",
    "Karusel dizayn",
    "Banner",
    "Kopirayting",
    "Translate",
    "SMM strategiya",
    "Targeting",
    "Mijoz bilan ishlash",
]

LEVELS = ["Har qanday", "Orta", "Tajribali", "Ekspert"]

LEVEL_EMOJI = {
    "Har qanday": "⚪",
    "Orta": "🟡",
    "Tajribali": "🟢",
    "Ekspert": "🟣",
}

PRIORITY_EMOJI = {
    "Past": "⚪",
    "Orta": "🟡",
    "Yuqori": "🟠",
    "Shoshilinch": "🔴",
}


class AutoTaskState(StatesGroup):
    """Avtomatik vazifa yaratish bosqichlari"""
    entering_name = State()
    choosing_skill = State()
    choosing_level = State()
    choosing_priority = State()
    entering_deadline = State()
    entering_description = State()
    waiting_smm_approval = State()


# ==================== /avtomatik_vazifa - BOSHLASH ====================

@router.message(Command("avtomatik_vazifa"))
@router.message(F.text == "🤖 Avto vazifa")
async def cmd_auto_task_start(message: Message, state: FSMContext):
    """Avtomatik vazifa yaratish"""
    if message.chat.type != "private":
        return

    user_id = message.from_user.id
    is_admin = user_id == config.ADMIN_TELEGRAM_ID

    is_pm = False
    if not is_admin:
        employee = await notion_service.find_employee_by_telegram_id(str(user_id))
        if employee:
            pm_check = (
                employee.get("properties", {})
                .get("PM hisoblanadi", {})
                .get("checkbox", False)
            )
            if pm_check:
                is_pm = True

    if not (is_admin or is_pm):
        await message.answer(
            "⛔ Bu buyruq faqat direktor va PM uchun.\n"
            "Oddiy vazifa berish uchun /vazifa_ber dan foydalaning."
        )
        return

    await state.set_state(AutoTaskState.entering_name)
    await message.answer(
        "🤖 <b>Avtomatik vazifa taqsimlash</b>\n\n"
        "Bot eng mos xodimni o'zi tanlaydi (ko'nikma, daraja va bandlik bo'yicha).\n"
        "SMM menejer tasdiqlasagina, vazifa xodimga yuboriladi.\n\n"
        "📝 <b>1/6:</b> Vazifa nomini yozing.\n"
        "<i>Misol: 'Mijoz X uchun Reels syomka qilish'</i>",
        reply_markup=cancel_keyboard(),
    )


# ==================== BEKOR QILISH ====================

@router.message(F.text == "❌ Bekor qilish", AutoTaskState())
async def text_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Avtomatik vazifa bekor qilindi.",
        reply_markup=main_admin_keyboard(),
    )


@router.callback_query(F.data == "auto_cancel")
async def callback_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        "❌ Avtomatik vazifa bekor qilindi.",
        reply_markup=main_admin_keyboard(),
    )
    await callback.answer()


# ==================== 1. NOMI ====================

@router.message(AutoTaskState.entering_name, F.text)
async def task_name(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        return

    name = message.text.strip()
    if len(name) < 3:
        await message.answer("⚠️ Vazifa nomi juda qisqa.")
        return

    await state.update_data(task_name=name)

    # Ko'nikmalarni guruhlab beramiz
    keyboard_buttons = []
    skills_grouped = {
        "🎬 Syomka va Senariy": ["Senariy yozish", "Oddiy syomka", "Murakkab syomka", "Drone syomka", "Studio syomka"],
        "✂️ Montaj": ["Oddiy montaj", "Murakkab montaj", "Reels montaj", "Color grading", "Motion design"],
        "🎨 Dizayn": ["Logo dizayn", "Post dizayn", "Story dizayn", "Karusel dizayn", "Banner"],
        "📝 Matn va SMM": ["Kopirayting", "Translate", "SMM strategiya", "Targeting", "Mijoz bilan ishlash"],
    }

    # Tugmalarni 2 ustunga joylashtiramiz
    for skill in SKILLS:
        keyboard_buttons.append(
            [
                InlineKeyboardButton(
                    text=skill, callback_data=f"auto_skill:{skill}"
                )
            ]
        )

    keyboard_buttons.append(
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="auto_cancel")]
    )

    await state.set_state(AutoTaskState.choosing_skill)
    await message.answer(
        f"✅ Vazifa: <b>{name}</b>\n\n"
        f"🛠 <b>2/6:</b> Qanday ko'nikma kerak?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
    )


# ==================== 2. KO'NIKMA TANLANDI ====================

@router.callback_query(
    AutoTaskState.choosing_skill, F.data.startswith("auto_skill:")
)
async def callback_skill(callback: CallbackQuery, state: FSMContext):
    skill = callback.data.split(":", 1)[1]
    await state.update_data(skill=skill)

    keyboard_buttons = [
        [
            InlineKeyboardButton(
                text=f"{LEVEL_EMOJI[lvl]} {lvl}",
                callback_data=f"auto_level:{lvl}",
            )
        ]
        for lvl in LEVELS
    ]
    keyboard_buttons.append(
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="auto_cancel")]
    )

    await state.set_state(AutoTaskState.choosing_level)
    await callback.message.answer(
        f"✅ Ko'nikma: <b>{skill}</b>\n\n"
        f"⭐ <b>3/6:</b> Eng past kerakli daraja?\n"
        f"<i>'Har qanday' = boshlovchilar ham bajara oladi</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
    )
    await callback.answer()


# ==================== 3. DARAJA TANLANDI ====================

@router.callback_query(
    AutoTaskState.choosing_level, F.data.startswith("auto_level:")
)
async def callback_level(callback: CallbackQuery, state: FSMContext):
    level = callback.data.split(":", 1)[1]
    await state.update_data(level=level)

    keyboard_buttons = [
        [
            InlineKeyboardButton(
                text=f"{PRIORITY_EMOJI[p]} {p}",
                callback_data=f"auto_pri:{p}",
            )
        ]
        for p in ["Past", "Orta", "Yuqori", "Shoshilinch"]
    ]
    keyboard_buttons.append(
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="auto_cancel")]
    )

    await state.set_state(AutoTaskState.choosing_priority)
    await callback.message.answer(
        f"✅ Daraja: {LEVEL_EMOJI[level]} <b>{level}</b>\n\n"
        f"⚡ <b>4/6:</b> Prioritet?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
    )
    await callback.answer()


# ==================== 4. PRIORITET TANLANDI ====================

@router.callback_query(
    AutoTaskState.choosing_priority, F.data.startswith("auto_pri:")
)
async def callback_priority(callback: CallbackQuery, state: FSMContext):
    priority = callback.data.split(":", 1)[1]
    await state.update_data(priority=priority)

    await state.set_state(AutoTaskState.entering_deadline)
    await callback.message.answer(
        f"✅ Prioritet: {PRIORITY_EMOJI[priority]} <b>{priority}</b>\n\n"
        f"📅 <b>5/6:</b> Muddat?\n\n"
        f"<i>Format: <b>DD.MM.YYYY</b> (masalan: 30.04.2026)\n"
        f"Yoki: <b>bugun</b>, <b>ertaga</b>, <b>yoq</b></i>",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


# ==================== 5. MUDDAT KIRITILDI ====================

@router.message(AutoTaskState.entering_deadline, F.text)
async def deadline_entered(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        return

    text = message.text.strip().lower()
    deadline = None
    deadline_display = "Belgilanmagan"

    if text in ["yoq", "yo'q", "skip"]:
        pass
    elif text == "bugun":
        deadline = datetime.now().strftime("%Y-%m-%d")
        deadline_display = datetime.now().strftime("%d.%m.%Y") + " (bugun)"
    elif text == "ertaga":
        from datetime import timedelta
        d = datetime.now() + timedelta(days=1)
        deadline = d.strftime("%Y-%m-%d")
        deadline_display = d.strftime("%d.%m.%Y") + " (ertaga)"
    else:
        match = re.match(r"^(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})$", text)
        if not match:
            await message.answer(
                "⚠️ Sana noto'g'ri formatda. Qaytadan: 30.04.2026"
            )
            return
        day, month, year = match.groups()
        try:
            dt = datetime(int(year), int(month), int(day))
            if dt.date() < datetime.now().date():
                await message.answer("⚠️ Bu sana o'tib ketgan!")
                return
            deadline = dt.strftime("%Y-%m-%d")
            deadline_display = dt.strftime("%d.%m.%Y")
        except ValueError:
            await message.answer("⚠️ Bunday sana mavjud emas.")
            return

    await state.update_data(deadline=deadline, deadline_display=deadline_display)
    await state.set_state(AutoTaskState.entering_description)

    await message.answer(
        f"✅ Muddat: <b>{deadline_display}</b>\n\n"
        f"📋 <b>6/6:</b> Batafsil tavsif yoki <b>yoq</b>",
        reply_markup=cancel_keyboard(),
    )


# ==================== 6. TAVSIF VA AVTOMATIK TAQSIMLASH ====================

@router.message(AutoTaskState.entering_description, F.text)
async def description_and_assign(message: Message, state: FSMContext, bot: Bot):
    """Tavsif kiritildi - bot eng mos xodimni topadi"""
    if message.text == "❌ Bekor qilish":
        return

    text = message.text.strip()
    description = "" if text.lower() in ["yoq", "yo'q", "skip"] else text[:2000]
    await state.update_data(description=description)

    data = await state.get_data()

    # Bot ishlayotganini ko'rsatamiz
    await message.answer("🔍 Eng mos xodim qidirilmoqda...")

    # Eng mos xodimni topamiz
    best_employee = await assignment_service.find_best_employee(
        required_skill=data["skill"],
        required_level=data["level"],
    )

    if not best_employee:
        await message.answer(
            f"😔 <b>Mos xodim topilmadi!</b>\n\n"
            f"🛠 Ko'nikma: {data['skill']}\n"
            f"⭐ Daraja: {data['level']}\n\n"
            f"<b>Sabablar:</b>\n"
            f"• Bu ko'nikmaga ega xodim yo'q\n"
            f"• Yoki barcha mos xodimlar to'liq band\n"
            f"• Yoki ta'tilda\n\n"
            f"💡 <b>Yechim:</b>\n"
            f"1. Notion'da xodimlarga 'Qila oladigan ishlar' qo'shing\n"
            f"2. Yoki /vazifa_ber orqali qo'lda taqsimlang\n"
            f"3. Yoki past darajadagi xodimni tanlang",
            reply_markup=main_admin_keyboard(),
        )
        await state.clear()
        return

    # Xodim haqida ma'lumot
    emp_id = best_employee["id"]
    emp_name = notion_service._get_title(best_employee)
    emp_level = (
        notion_service._get_select_value(best_employee, "Daraja") or "—"
    )
    emp_busy = (
        notion_service._get_select_value(best_employee, "Bandlik darajasi")
        or "Belgilanmagan"
    )
    active_count = await assignment_service._count_active_tasks(emp_id)

    await state.update_data(
        suggested_employee_id=emp_id,
        suggested_employee_name=emp_name,
    )

    # SMM menejerlarni topamiz
    smm_managers = await assignment_service.find_smm_managers()

    summary = (
        "🤖 <b>Avtomatik taqsimlash natijasi</b>\n\n"
        f"📌 <b>Vazifa:</b> {data['task_name']}\n"
        f"🛠 Ko'nikma: {data['skill']}\n"
        f"⭐ Daraja: {data['level']}\n"
        f"⚡ Prioritet: {PRIORITY_EMOJI[data['priority']]} {data['priority']}\n"
        f"📅 Muddat: {data['deadline_display']}\n\n"
        f"👤 <b>Tavsiya etilgan xodim:</b>\n"
        f"   <b>{emp_name}</b>\n"
        f"   ⭐ Darajasi: {emp_level}\n"
        f"   📊 Bandlik: {emp_busy}\n"
        f"   📝 Faol vazifalari: {active_count} ta\n\n"
    )

    if smm_managers:
        summary += (
            "<i>SMM menejerlar tasdiqlashi kerak. "
            "Quyida tanlang:</i>"
        )
    else:
        summary += (
            "⚠️ <b>SMM menejer topilmadi!</b>\n"
            "Direktor o'zi tasdiqlasin:"
        )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Tasdiqlash va yuborish",
                    callback_data="auto_confirm",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Boshqa xodimga taqsimlash",
                    callback_data="auto_change_emp",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Bekor qilish", callback_data="auto_cancel"
                )
            ],
        ]
    )

    await state.set_state(AutoTaskState.waiting_smm_approval)
    await message.answer(summary, reply_markup=keyboard)

    # SMM menejerlarga ham xabar (agar direktor o'zi emas bo'lsa)
    sender_id = message.from_user.id
    if sender_id == config.ADMIN_TELEGRAM_ID:
        for smm in smm_managers:
            smm_tg = notion_service._get_rich_text(smm, "Telegram ID")
            if smm_tg and smm_tg != str(sender_id):
                try:
                    await bot.send_message(
                        chat_id=int(smm_tg),
                        text=(
                            f"📋 <b>Yangi vazifa tasdiqlash kerak</b>\n\n"
                            f"Direktor avtomatik vazifa yaratdi.\n"
                            f"Yuqorida ko'rib chiqing va tasdiqlang."
                        ),
                    )
                except Exception:
                    pass


# ==================== TASDIQLASH ====================

@router.callback_query(
    AutoTaskState.waiting_smm_approval, F.data == "auto_confirm"
)
async def callback_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Vazifani Notion'ga yozish va xodimga yuborish"""
    data = await state.get_data()

    try:
        # Notion'da vazifa yaratamiz (qo'shimcha maydonlar bilan)
        properties = {
            "Vazifa nomi": {
                "title": [{"text": {"content": data["task_name"]}}]
            },
            "Holati": {"select": {"name": "Yangi"}},
            "Prioritet": {"select": {"name": data["priority"]}},
            "Kategoriya": {"select": {"name": "Boshqa"}},
            "Tavsif": {
                "rich_text": [{"text": {"content": data.get("description", "")}}]
            },
            "Masul xodim": {
                "relation": [{"id": data["suggested_employee_id"]}]
            },
            "Kerakli konikma": {"select": {"name": data["skill"]}},
            "Kerakli daraja": {"select": {"name": data["level"]}},
            "SMM tasdiqladimi": {"checkbox": True},
            "Avtomatik taqsimlangan": {"checkbox": True},
        }

        if data.get("deadline"):
            properties["Muddat"] = {"date": {"start": data["deadline"]}}

        new_task = await notion_service.client.pages.create(
            parent={"database_id": config.DB_TASKS},
            properties=properties,
        )

        # Direktor/PM ga tasdiq
        await callback.message.answer(
            f"✅ <b>Vazifa yaratildi va yuborildi!</b>\n\n"
            f"📌 <b>{data['task_name']}</b>\n"
            f"👤 <b>{data['suggested_employee_name']}</b> ga taqsimlandi.",
            reply_markup=main_admin_keyboard(),
        )

        # Xodimga xabar yuboramiz
        try:
            employee = await notion_service.client.pages.retrieve(
                page_id=data["suggested_employee_id"]
            )
            telegram_id = notion_service._get_rich_text(employee, "Telegram ID")

            if telegram_id:
                emp_message = (
                    f"📌 <b>Sizga yangi vazifa berildi!</b>\n\n"
                    f"📝 <b>{data['task_name']}</b>\n\n"
                    f"🛠 Ko'nikma: {data['skill']}\n"
                    f"⚡ Prioritet: {PRIORITY_EMOJI[data['priority']]} {data['priority']}\n"
                    f"📅 Muddat: {data['deadline_display']}\n"
                )
                if data.get("description"):
                    emp_message += f"\n📋 <b>Tavsif:</b>\n<i>{data['description']}</i>\n"

                emp_message += (
                    f"\n🤖 <i>Avtomatik taqsimlangan, SMM menejer tasdiqladi.</i>"
                )

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
        except Exception as e:
            await callback.message.answer(
                f"⚠️ Xodimga xabar yuborib bo'lmadi: <code>{str(e)[:200]}</code>"
            )

    except Exception as e:
        await callback.message.answer(
            f"❌ Xatolik: <code>{str(e)[:200]}</code>",
            reply_markup=main_admin_keyboard(),
        )

    await state.clear()
    await callback.answer()


# ==================== BOSHQA XODIMGA O'ZGARTIRISH ====================

@router.callback_query(
    AutoTaskState.waiting_smm_approval, F.data == "auto_change_emp"
)
async def callback_change_employee(
    callback: CallbackQuery, state: FSMContext
):
    """Boshqa xodimga taqsimlash uchun ro'yxat"""
    data = await state.get_data()

    # Shu ko'nikmaga ega barcha xodimlarni topamiz
    employees = await notion_service.get_all_employees()
    suitable = []

    for emp in employees:
        skills = assignment_service._get_employee_skills(emp)
        if data["skill"] in skills:
            status = assignment_service._get_employee_status(emp)
            if status == "Ishlayapti":
                suitable.append(emp)

    if not suitable:
        await callback.answer("Mos xodim topilmadi", show_alert=True)
        return

    keyboard_buttons = []
    for emp in suitable[:15]:
        emp_id = emp["id"]
        emp_name = notion_service._get_title(emp)
        emp_level = (
            notion_service._get_select_value(emp, "Daraja") or "—"
        )
        active_count = await assignment_service._count_active_tasks(emp_id)

        button_text = f"{emp_name} ({emp_level}) — {active_count} vazifa"
        keyboard_buttons.append(
            [
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"auto_pickemp:{emp_id}",
                )
            ]
        )

    keyboard_buttons.append(
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="auto_cancel")]
    )

    await callback.message.answer(
        f"👥 <b>Mos keluvchi xodimlar (ko'nikma: {data['skill']}):</b>\n\n"
        f"<i>Birini tanlang:</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
    )
    await callback.answer()


@router.callback_query(
    AutoTaskState.waiting_smm_approval, F.data.startswith("auto_pickemp:")
)
async def callback_pick_employee(callback: CallbackQuery, state: FSMContext):
    """Boshqa xodimni tanlash"""
    emp_id = callback.data.split(":", 1)[1]

    try:
        employee = await notion_service.client.pages.retrieve(page_id=emp_id)
        emp_name = notion_service._get_title(employee)

        await state.update_data(
            suggested_employee_id=emp_id,
            suggested_employee_name=emp_name,
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Tasdiqlash va yuborish",
                        callback_data="auto_confirm",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="❌ Bekor qilish", callback_data="auto_cancel"
                    )
                ],
            ]
        )

        await callback.message.answer(
            f"✅ Xodim o'zgartirildi: <b>{emp_name}</b>\n\n"
            f"Tasdiqlasizmi?",
            reply_markup=keyboard,
        )
        await callback.answer()
    except Exception as e:
        await callback.answer(f"Xatolik: {str(e)[:50]}", show_alert=True)
