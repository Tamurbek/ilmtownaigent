"""
KPI va intizom buyruqlari (faqat direktor):
- /kpi_hisob — barcha xodimlarga oylik KPI hisoblash
- /intizom — oxirgi 30 kunlik intizomiy choralar ro'yxati
- /mening_kpim — har bir xodim o'z KPI sini ko'rishi mumkin
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

from bot.config import config
from bot.services.notion_service import notion_service
from bot.services.discipline_service import discipline_service
from bot.utils.keyboards import main_admin_keyboard

router = Router()


def _get_month_range(year: int, month: int) -> tuple[str, str]:
    """Oyning birinchi va oxirgi kunini olish"""
    last_day = monthrange(year, month)[1]
    start = f"{year}-{month:02d}-01"
    end = f"{year}-{month:02d}-{last_day:02d}"
    return start, end


def admin_only(func):
    async def wrapper(message: Message, **kwargs):
        if message.from_user.id != config.ADMIN_TELEGRAM_ID:
            await message.answer("⛔ Bu buyruq faqat direktor uchun.")
            return
        import inspect
        sig = inspect.signature(func)
        valid_kwargs = {
            k: v for k, v in kwargs.items() if k in sig.parameters
        }
        return await func(message, **valid_kwargs)

    return wrapper


# ==================== /kpi_hisob — OYLIK KPI HISOBLASH ====================

@router.message(Command("kpi_hisob"))
@router.message(F.text == "⭐ KPI hisob")
@admin_only
async def cmd_calculate_kpi(message: Message):
    """Barcha xodimlarga oylik KPI hisoblash"""
    # Joriy oy
    now = datetime.now()
    month_start, month_end = _get_month_range(now.year, now.month)

    await message.answer(
        f"⏳ <b>{month_start[:7]}</b> oyi uchun KPI hisoblanmoqda...\n"
        f"Barcha xodimlar uchun avtomatik hisoblanyapti."
    )

    employees = await notion_service.get_all_employees()
    if not employees:
        await message.answer("❌ Xodimlar yo'q.")
        return

    # Har bir xodim uchun KPI hisoblash
    results = []
    for emp in employees:
        emp_id = emp["id"]
        emp_name = notion_service._get_title(emp)

        # Maoshini olamiz
        salary_uzs = (
            emp.get("properties", {})
            .get("Oylik maosh UZS", {})
            .get("number")
            or 0
        )
        salary_usd = (
            emp.get("properties", {})
            .get("Oylik maosh USD", {})
            .get("number")
            or 0
        )

        try:
            kpi_data = await discipline_service.calculate_monthly_kpi(
                employee_id=emp_id,
                month_start=month_start,
                month_end=month_end,
            )

            # Notion'ga yozish
            await discipline_service.save_kpi_record(
                employee_id=emp_id,
                employee_name=emp_name,
                month_start=month_start,
                month_end=month_end,
                kpi_data=kpi_data,
                salary_uzs=salary_uzs,
                salary_usd=salary_usd,
            )

            results.append((emp_name, kpi_data))
        except Exception as e:
            import logging
            logging.error(f"KPI hisoblashda xato ({emp_name}): {e}")

    if not results:
        await message.answer("❌ KPI hisoblanmadi.")
        return

    # Eng yaxshi xodimlardan boshlab tartiblaymiz
    results.sort(key=lambda x: x[1]["total_kpi_percent"], reverse=True)

    text = (
        f"📊 <b>{month_start[:7]} — KPI natijalari</b>\n"
        f"<i>Hujjat asosida avtomatik hisoblandi</i>\n\n"
    )

    for name, kpi in results:
        emoji = (
            "🏆"
            if kpi["completion_rate"] >= 100
            else "🥇"
            if kpi["completion_rate"] >= 90
            else "🥈"
            if kpi["completion_rate"] >= 80
            else "🥉"
            if kpi["completion_rate"] >= 70
            else "⚠️"
        )

        text += (
            f"{emoji} <b>{name}</b>\n"
            f"   📊 KPI: {kpi['total_kpi_percent']}%/20%\n"
            f"   ✅ Vazifalar: {kpi['completion_rate']}%\n"
            f"   ⏰ Kechikishlar: {kpi['lateness_count']}\n"
            f"   ⚠️ Ogohlantirishlar: {kpi['warnings_count']}\n"
            f"   🎁 Mukofot: {kpi['reward_type']}\n\n"
        )

    text += "\n<i>To'liq ma'lumot Notion 'KPI va Mukofot' bazasida.</i>"

    # Xabar uzun bo'lsa, qismlarga bo'lib yuboramiz
    if len(text) > 4000:
        # Boshini yuborib, keyin qolganini
        await message.answer(text[:4000])
        await message.answer(text[4000:])
    else:
        await message.answer(text)


# ==================== /intizom — INTIZOMIY CHORALAR ====================

@router.message(Command("intizom"))
@router.message(F.text == "⚠️ Intizom")
@admin_only
async def cmd_discipline_log(message: Message):
    """Joriy oydagi intizomiy choralar ro'yxati"""
    now = datetime.now()
    month_start, month_end = _get_month_range(now.year, now.month)

    try:
        response = await notion_service.client.databases.query(
            database_id=config.DB_DISCIPLINE,
            filter={
                "and": [
                    {"property": "Sana", "date": {"on_or_after": month_start}},
                    {"property": "Sana", "date": {"on_or_before": month_end}},
                ]
            },
            sorts=[{"property": "Sana", "direction": "descending"}],
        )
        events = response.get("results", [])
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)[:200]}")
        return

    if not events:
        await message.answer(
            f"✅ <b>{month_start[:7]} oyida intizomiy choralar yo'q!</b>\n\n"
            f"Hammasi qoidaga muvofiq ishlayapti. 👍"
        )
        return

    # Xodimlar bo'yicha guruhlash
    by_employee = {}
    for event in events:
        emp_ids = notion_service._get_relation_ids(event, "Xodim")
        if emp_ids:
            emp_id = emp_ids[0]
            by_employee.setdefault(emp_id, []).append(event)

    text = (
        f"⚠️ <b>{month_start[:7]} — Intizomiy choralar</b>\n"
        f"Jami: {len(events)} ta voqea\n\n"
    )

    for emp_id, emp_events in by_employee.items():
        try:
            employee = await notion_service.client.pages.retrieve(
                page_id=emp_id
            )
            emp_name = notion_service._get_title(employee)
        except Exception:
            emp_name = "Noma'lum"

        text += f"\n👤 <b>{emp_name}</b> ({len(emp_events)} ta):\n"

        for event in emp_events[:5]:  # 5 tagacha
            event_type = (
                notion_service._get_select_value(event, "Voqea turi") or "—"
            )
            chora = (
                notion_service._get_select_value(event, "Chora turi") or "—"
            )
            sana = notion_service._get_date(event, "Sana") or "—"

            text += f"   • {sana}: {event_type} → {chora}\n"

        if len(emp_events) > 5:
            text += f"   <i>... yana {len(emp_events) - 5} ta</i>\n"

    if len(text) > 4000:
        await message.answer(text[:4000])
        await message.answer(text[4000:])
    else:
        await message.answer(text)


# ==================== /mening_kpim — XODIM O'Z KPI SI ====================

@router.message(Command("mening_kpim"))
@router.message(F.text == "⭐ Mening KPI")
async def cmd_my_kpi(message: Message):
    """Xodim o'z joriy oylik KPI sini ko'radi"""
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

    await message.answer("⏳ KPI hisoblanmoqda...")

    try:
        kpi = await discipline_service.calculate_monthly_kpi(
            employee_id=employee["id"],
            month_start=month_start,
            month_end=month_end,
        )

        # Mukofot tavsifi (hujjat asosida)
        reward_descriptions = {
            "Hech narsa": "70% dan past — mukofot yo'q. Yaxshilang!",
            "Ommaviy minnatdorchilik": "70-79% — Jamoa oldida tan olish",
            "KPI + Tushlik": "80-89% — KPI bonus + 1 marta tushlik kompaniya hisobidan",
            "KPI + Sovga": "90-99% — KPI bonus + shaxsiy sovg'a",
            "KPI + Qimmat sovga + Dam olish": "100% — Qimmatroq sovg'a + 1 kun qo'shimcha dam olish! 🎉",
        }

        # Progress emoji
        if kpi["completion_rate"] >= 100:
            progress_emoji = "🏆"
        elif kpi["completion_rate"] >= 90:
            progress_emoji = "🥇"
        elif kpi["completion_rate"] >= 80:
            progress_emoji = "🥈"
        elif kpi["completion_rate"] >= 70:
            progress_emoji = "🥉"
        else:
            progress_emoji = "⚠️"

        text = (
            f"⭐ <b>Sizning KPI'ngiz — {month_start[:7]}</b>\n"
            f"👤 {emp_name}\n\n"
            f"{progress_emoji} <b>Vazifalar bajarilishi: {kpi['completion_rate']}%</b>\n\n"
            f"📊 <b>KPI ko'rsatkichlari:</b>\n"
            f"   ⏰ Intizom: {kpi['discipline_score']}/5\n"
            f"   ✅ Vazifalar: {kpi['tasks_score']}/10\n"
            f"   ⭐ Sifat: {kpi['quality_score']}/5\n"
            f"   ━━━━━━━━━━━━━━\n"
            f"   <b>Jami: {kpi['total_kpi_percent']}/20%</b>\n\n"
            f"📋 <b>Statistika:</b>\n"
            f"   • Kechikishlar: {kpi['lateness_count']}\n"
            f"   • Bajarilmagan vazifalar: {kpi['unfinished_tasks']}\n"
            f"   • Ogohlantirishlar: {kpi['warnings_count']}\n\n"
            f"🎁 <b>Mukofot turi:</b>\n"
            f"   {kpi['reward_type']}\n"
            f"   <i>{reward_descriptions.get(kpi['reward_type'], '')}</i>\n\n"
            f"<i>Oy oxirida yakuniy hisob qilib, KPI bonusi maoshga qo'shiladi.</i>"
        )

        await message.answer(text)

    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)[:200]}")
