"""
Operator va montajchilar uchun ish qo'shish va daromad ko'rish:
- /ish_qosh — yangi bajargan ishni qo'shish (savol-javob)
- /mening_daromadim — joriy oylik daromad

PM yoki direktor ham boshqa xodimlar uchun ish qo'shishi mumkin.
"""
from datetime import datetime
from calendar import monthrange

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
from bot.services.payment_service import payment_service
from bot.utils.keyboards import main_employee_keyboard, cancel_keyboard

router = Router()


QUALITY_OPTIONS = [
    ("Yaxshi", "🟢 Yaxshi (×1.2)"),
    ("Orta", "🟡 O'rta (×1.0)"),
    ("Yomon", "🔴 Yomon (×0.7)"),
]

DELAY_OPTIONS = [
    ("Muddatdan oldin", "⚡ Muddatdan oldin (×1.1)"),
    ("Oz vaqtida", "✅ O'z vaqtida (×1.0)"),
    ("1 kun kechikkan", "🟡 1 kun kechikkan (×0.9)"),
    ("2 kun kechikkan", "🟠 2 kun kechikkan (×0.8)"),
    ("3+ kun kechikkan", "🔴 3+ kun kechikkan (×0.7)"),
]


class JobAddState(StatesGroup):
    """Ish qo'shish bosqichlari"""
    choosing_category = State()
    entering_name = State()
    choosing_quality = State()
    choosing_delay = State()
    entering_days_before = State()
    entering_link = State()
    confirming = State()


def _get_month_range(year: int, month: int) -> tuple[str, str]:
    last_day = monthrange(year, month)[1]
    return (f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last_day:02d}")


# ==================== /ish_qosh — BOSHLASH ====================

@router.message(Command("ish_qosh"))
@router.message(F.text == "📦 Ish qo'shish")
async def cmd_add_job_start(message: Message, state: FSMContext):
    """Operator/montajchi yangi ish qo'shadi"""
    if message.chat.type != "private":
        return

    user_id = str(message.from_user.id)
    employee = await notion_service.find_employee_by_telegram_id(user_id)

    if not employee:
        await message.answer("❌ Siz tizimda ro'yxatdan o'tmagansiz.")
        return

    # Narx kategoriyalarini olamiz
    categories = await payment_service.get_price_categories()
    if not categories:
        await message.answer(
            "❌ Narx kategoriyalari topilmadi. Direktorga murojaat qiling."
        )
        return

    # Ikki guruhga bo'lamiz: Syomka va Montaj
    syomka_cats = []
    montaj_cats = []

    for cat in categories:
        cat_type = notion_service._get_select_value(cat, "Tur")
        if cat_type == "Syomka":
            syomka_cats.append(cat)
        elif cat_type == "Montaj":
            montaj_cats.append(cat)

    keyboard_buttons = []

    if syomka_cats:
        keyboard_buttons.append(
            [InlineKeyboardButton(text="━━━ 🎬 SYOMKA ━━━", callback_data="job_section_label")]
        )
        for cat in syomka_cats:
            cat_id = cat["id"]
            cat_name = notion_service._get_title(cat)
            price = (
                cat.get("properties", {})
                .get("Bazaviy narx UZS", {})
                .get("number") or 0
            )
            keyboard_buttons.append(
                [
                    InlineKeyboardButton(
                        text=f"{cat_name} — {price:,} so'm".replace(",", " "),
                        callback_data=f"job_cat:{cat_id}",
                    )
                ]
            )

    if montaj_cats:
        keyboard_buttons.append(
            [InlineKeyboardButton(text="━━━ ✂️ MONTAJ ━━━", callback_data="job_section_label")]
        )
        for cat in montaj_cats:
            cat_id = cat["id"]
            cat_name = notion_service._get_title(cat)
            price = (
                cat.get("properties", {})
                .get("Bazaviy narx UZS", {})
                .get("number") or 0
            )
            keyboard_buttons.append(
                [
                    InlineKeyboardButton(
                        text=f"{cat_name} — {price:,} so'm".replace(",", " "),
                        callback_data=f"job_cat:{cat_id}",
                    )
                ]
            )

    keyboard_buttons.append(
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="job_cancel")]
    )

    await state.set_state(JobAddState.choosing_category)
    await state.update_data(employee_id=employee["id"])

    await message.answer(
        "📦 <b>Yangi ish qo'shish</b>\n\n"
        "🎯 <b>1/6:</b> Qaysi turdagi ish bajardingiz?\n"
        "<i>Quyidagi ro'yxatdan tanlang. Yonidagi raqam bazaviy narx.</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
    )


# ==================== BEKOR QILISH ====================

@router.callback_query(F.data == "job_cancel")
async def callback_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        "❌ Bekor qilindi.", reply_markup=main_employee_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "job_section_label")
async def callback_section_label(callback: CallbackQuery):
    """Bo'lim sarlavhasi - bosilsa hech narsa qilmaydi"""
    await callback.answer("Pastdagi tugmalardan tanlang", show_alert=False)


@router.message(F.text == "❌ Bekor qilish", JobAddState())
async def text_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Bekor qilindi.", reply_markup=main_employee_keyboard())


# ==================== 1. KATEGORIYA TANLANDI ====================

@router.callback_query(
    JobAddState.choosing_category, F.data.startswith("job_cat:")
)
async def callback_category(callback: CallbackQuery, state: FSMContext):
    """Kategoriya tanlandi - ish nomini so'raymiz"""
    cat_id = callback.data.split(":", 1)[1]

    cat = await payment_service.get_price_by_id(cat_id)
    if not cat:
        await callback.answer("❌ Kategoriya topilmadi", show_alert=True)
        return

    cat_name = notion_service._get_title(cat)
    base_price = (
        cat.get("properties", {})
        .get("Bazaviy narx UZS", {})
        .get("number") or 0
    )
    cat_type = notion_service._get_select_value(cat, "Tur")

    await state.update_data(
        category_id=cat_id,
        category_name=cat_name,
        base_price=base_price,
        job_type=cat_type,
    )
    await state.set_state(JobAddState.entering_name)

    await callback.message.answer(
        f"✅ Kategoriya: <b>{cat_name}</b>\n"
        f"💰 Bazaviy narx: <b>{base_price:,} so'm</b>".replace(",", " ") + "\n\n"
        f"📝 <b>2/6:</b> Bu ish nima edi? Qisqa nom yoki tavsif yozing.\n"
        f"<i>Misol: 'Mijoz X uchun Reels #15' yoki 'Wedding video — Aliyev'</i>",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


# ==================== 2. ISH NOMI ====================

@router.message(JobAddState.entering_name, F.text)
async def job_name(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        return

    name = message.text.strip()
    if len(name) < 3:
        await message.answer("⚠️ Juda qisqa.")
        return

    await state.update_data(job_name=name)

    keyboard_buttons = [
        [
            InlineKeyboardButton(
                text=label, callback_data=f"job_quality:{value}"
            )
        ]
        for value, label in QUALITY_OPTIONS
    ]
    keyboard_buttons.append(
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="job_cancel")]
    )

    await state.set_state(JobAddState.choosing_quality)
    await message.answer(
        f"✅ Ish: <b>{name}</b>\n\n"
        f"⭐ <b>3/6:</b> Sifat darajasini tanlang\n"
        f"<i>Bu narxga ta'sir qiladi:</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
    )


# ==================== 3. SIFAT TANLANDI ====================

@router.callback_query(
    JobAddState.choosing_quality, F.data.startswith("job_quality:")
)
async def callback_quality(callback: CallbackQuery, state: FSMContext):
    quality = callback.data.split(":", 1)[1]
    await state.update_data(quality=quality)

    keyboard_buttons = [
        [
            InlineKeyboardButton(
                text=label, callback_data=f"job_delay:{value}"
            )
        ]
        for value, label in DELAY_OPTIONS
    ]
    keyboard_buttons.append(
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="job_cancel")]
    )

    await state.set_state(JobAddState.choosing_delay)
    await callback.message.answer(
        f"✅ Sifat: <b>{quality}</b>\n\n"
        f"⏰ <b>4/6:</b> Vaqt holati qanday?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
    )
    await callback.answer()


# ==================== 4. KECHIKISH HOLATI ====================

@router.callback_query(
    JobAddState.choosing_delay, F.data.startswith("job_delay:")
)
async def callback_delay(callback: CallbackQuery, state: FSMContext):
    delay = callback.data.split(":", 1)[1]
    await state.update_data(delay_status=delay)

    # Faqat "Muddatdan oldin" tanlasa, deadline bonusi so'raymiz
    if delay == "Muddatdan oldin":
        await state.set_state(JobAddState.entering_days_before)
        await callback.message.answer(
            f"✅ Vaqt: <b>Muddatdan oldin</b>\n\n"
            f"⚡ <b>5/6:</b> Muddatdan necha kun oldin yakunlandi?\n\n"
            f"<i>1 kun = +10,000 so'm bonus\n"
            f"2 kun = +20,000 so'm bonus\n"
            f"3+ kun = +30,000 so'm bonus</i>\n\n"
            f"Faqat raqam yozing: 1, 2, 3 yoki ko'p",
            reply_markup=cancel_keyboard(),
        )
    else:
        # Boshqa holatlarda 0 kun
        await state.update_data(days_before_deadline=0)
        await _ask_for_link(callback.message, state)
    await callback.answer()


# ==================== 5. NECHA KUN OLDIN ====================

@router.message(JobAddState.entering_days_before, F.text)
async def days_before(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        return

    text = message.text.strip()
    try:
        days = int(text)
        if days < 0:
            raise ValueError()
    except ValueError:
        await message.answer("⚠️ Faqat raqam: 1, 2, 3 va h.k.")
        return

    await state.update_data(days_before_deadline=days)
    await _ask_for_link(message, state)


async def _ask_for_link(message: Message, state: FSMContext):
    """Havola/izoh so'rash"""
    await state.set_state(JobAddState.entering_link)
    await message.answer(
        f"🔗 <b>6/6:</b> Ish havolasi (Drive, Instagram link va h.k.)\n\n"
        f"<i>Yoki <b>yoq</b> deb yozing — havola bo'lmasa.</i>",
        reply_markup=cancel_keyboard(),
    )


# ==================== 6. HAVOLA - HISOBLASH ====================

@router.message(JobAddState.entering_link, F.text)
async def link_and_calculate(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        return

    text = message.text.strip()
    link = "" if text.lower() in ["yoq", "yo'q", "skip"] else text
    if link and not (link.startswith("http://") or link.startswith("https://")):
        link = ""  # noto'g'ri havola - qoldiramiz

    await state.update_data(link=link)

    data = await state.get_data()

    # Narxni hisoblaymiz
    calc = payment_service.calculate_job_price(
        base_price=data["base_price"],
        quality=data["quality"],
        delay_status=data["delay_status"],
        days_before_deadline=data.get("days_before_deadline", 0),
    )

    # Tasdiq xabari
    summary = (
        "📦 <b>Ish ma'lumotlari:</b>\n\n"
        f"📝 <b>{data['job_name']}</b>\n"
        f"🏷 Kategoriya: {data['category_name']}\n"
        f"⭐ Sifat: {data['quality']}\n"
        f"⏰ Holat: {data['delay_status']}\n\n"
        f"💰 <b>Narx hisobi:</b>\n"
        f"   Bazaviy narx: {calc['base_price']:,} so'm\n".replace(",", " ") +
        f"   × Sifat koef: {calc['quality_coef']}\n"
        f"   × Kechikish koef: {calc['delay_coef']}\n"
    )

    if calc["deadline_bonus"] > 0:
        summary += f"   + Deadline bonus: {calc['deadline_bonus']:,} so'm\n".replace(",", " ")

    summary += (
        f"   ━━━━━━━━━━━━━━\n"
        f"   <b>YAKUNIY: {calc['final_price']:,} so'm</b>\n\n".replace(",", " ") +
        f"<b>Saqlanadimi?</b>"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Saqlash", callback_data="job_confirm"
                ),
                InlineKeyboardButton(
                    text="❌ Bekor", callback_data="job_cancel"
                ),
            ]
        ]
    )

    await state.set_state(JobAddState.confirming)
    await message.answer(summary, reply_markup=keyboard)


# ==================== TASDIQLASH ====================

@router.callback_query(JobAddState.confirming, F.data == "job_confirm")
async def callback_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Ishni Notion'ga yozish"""
    data = await state.get_data()

    try:
        await payment_service.create_completed_job(
            employee_id=data["employee_id"],
            price_category_id=data["category_id"],
            base_price=data["base_price"],
            job_type=data["job_type"],
            job_name=data["job_name"],
            quality=data["quality"],
            delay_status=data["delay_status"],
            days_before_deadline=data.get("days_before_deadline", 0),
            link=data.get("link", ""),
        )

        # Yakuniy narx ko'rsatamiz
        calc = payment_service.calculate_job_price(
            base_price=data["base_price"],
            quality=data["quality"],
            delay_status=data["delay_status"],
            days_before_deadline=data.get("days_before_deadline", 0),
        )

        await callback.message.answer(
            f"✅ <b>Ish qo'shildi!</b>\n\n"
            f"💰 Daromadingizga qo'shildi: "
            f"<b>{calc['final_price']:,} so'm</b>\n\n".replace(",", " ") +
            f"<i>/mening_daromadim — joriy oylik daromadingiz</i>",
            reply_markup=main_employee_keyboard(),
        )

        # Direktorga ham xabar (oddiy)
        if config.ADMIN_TELEGRAM_ID:
            try:
                emp_name = "Xodim"
                emp = await notion_service.client.pages.retrieve(
                    page_id=data["employee_id"]
                )
                if emp:
                    emp_name = notion_service._get_title(emp)

                await bot.send_message(
                    chat_id=config.ADMIN_TELEGRAM_ID,
                    text=(
                        f"📦 <b>Yangi bajarilgan ish</b>\n\n"
                        f"👤 {emp_name}\n"
                        f"📝 {data['job_name']}\n"
                        f"💰 {calc['final_price']:,} so'm".replace(",", " ")
                    ),
                )
            except Exception:
                pass

    except Exception as e:
        await callback.message.answer(
            f"❌ Xatolik: <code>{str(e)[:200]}</code>",
            reply_markup=main_employee_keyboard(),
        )

    await state.clear()
    await callback.answer()


# ==================== /mening_daromadim ====================

@router.message(Command("mening_daromadim"))
@router.message(F.text == "💰 Daromadim")
async def cmd_my_earnings(message: Message):
    """Xodim joriy oylik daromadini ko'radi"""
    if message.chat.type != "private":
        return

    user_id = str(message.from_user.id)
    employee = await notion_service.find_employee_by_telegram_id(user_id)

    if not employee:
        await message.answer("❌ Siz tizimda ro'yxatdan o'tmagansiz.")
        return

    emp_name = notion_service._get_title(employee)
    now = datetime.now()
    month_start, month_end = _get_month_range(now.year, now.month)

    await message.answer("⏳ Hisoblanmoqda...")

    try:
        earnings = await payment_service.calculate_employee_monthly_earnings(
            employee_id=employee["id"],
            month_start=month_start,
            month_end=month_end,
        )

        text = (
            f"💰 <b>Sizning daromadingiz — {month_start[:7]}</b>\n"
            f"👤 {emp_name}\n\n"
            f"📊 <b>Statistika:</b>\n"
            f"   📦 Jami ishlar: {earnings['jobs_count']} ta\n"
        )

        # Tur bo'yicha
        if earnings["by_type"]["Syomka"]["count"] > 0:
            text += (
                f"   🎬 Syomka: {earnings['by_type']['Syomka']['count']} ta — "
                f"{earnings['by_type']['Syomka']['sum']:,} so'm\n".replace(",", " ")
            )
        if earnings["by_type"]["Montaj"]["count"] > 0:
            text += (
                f"   ✂️ Montaj: {earnings['by_type']['Montaj']['count']} ta — "
                f"{earnings['by_type']['Montaj']['sum']:,} so'm\n".replace(",", " ")
            )

        text += f"\n💵 <b>Hisob:</b>\n"
        text += f"   Asosiy: {earnings['subtotal']:,} so'm\n".replace(",", " ")

        if earnings["volume_bonus_percent"] > 0:
            text += (
                f"   + Hajm bonusi (+{earnings['volume_bonus_percent']}%): "
                f"{earnings['volume_bonus_uzs']:,} so'm\n".replace(",", " ")
            )

        text += (
            f"   ━━━━━━━━━━━━━━\n"
            f"   <b>JAMI: {earnings['total']:,} so'm</b>\n\n".replace(",", " ")
        )

        # Keyingi bonus tomon
        if earnings["jobs_count"] < 30:
            text += f"💡 30 ishga yetsangiz, +5% bonus olasiz! ({30 - earnings['jobs_count']} ta qoldi)"
        elif earnings["jobs_count"] < 50:
            text += f"💡 50 ishga yetsangiz, +10% bonus olasiz! ({50 - earnings['jobs_count']} ta qoldi)"
        elif earnings["jobs_count"] < 70:
            text += f"💡 70 ishga yetsangiz, +15% bonus olasiz! ({70 - earnings['jobs_count']} ta qoldi)"
        else:
            text += "🏆 70+ ish! Maksimal bonus olayapsiz."

        await message.answer(text)
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)[:200]}")
