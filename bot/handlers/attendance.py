"""
Davomat (kelish/ketish) buyruqlari:
- /keldim — ish boshlash
- /ketdim — ish tugatish
- /davomat — bugungi statusni ko'rish
"""
from datetime import datetime
import pytz

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import config
from bot.services.notion_service import notion_service
from bot.services.discipline_service import discipline_service

router = Router()


def _get_now() -> datetime:
    """Joriy vaqtni (Asia/Tashkent vaqtini) olish"""
    tz = pytz.timezone(config.TIMEZONE)
    return datetime.now(tz)


def _calculate_late_minutes(arrival: datetime) -> int:
    """Kechikish daqiqalarini hisoblash"""
    work_start = config.WORK_START_TIME.split(":")
    expected_hour = int(work_start[0])
    expected_minute = int(work_start[1])

    expected_time = arrival.replace(
        hour=expected_hour, minute=expected_minute, second=0, microsecond=0
    )

    if arrival > expected_time:
        delta = arrival - expected_time
        return int(delta.total_seconds() / 60)
    return 0


def _format_duration(start: datetime, end: datetime) -> str:
    """Ikki vaqt o'rtasidagi farqni soat va daqiqa shaklida"""
    delta = end - start
    total_minutes = int(delta.total_seconds() / 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours} soat {minutes} daqiqa"


# ==================== /keldim — ISH BOSHLASH ====================

@router.message(Command("keldim"))
@router.message(F.text == "🟢 Keldim")
async def cmd_check_in(message: Message, bot: Bot):
    """Xodim ish boshlaganini qayd qilish"""
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

    # Bugun keldim deb yozganmi?
    today_check_ins = await notion_service.get_today_attendance(
        employee["id"], record_type="Kelish"
    )
    if today_check_ins:
        existing_time = notion_service._get_rich_text(
            today_check_ins[0], "Vaqt"
        )
        await message.answer(
            f"ℹ️ Siz bugun allaqachon kelganligingizni qayd etgansiz.\n"
            f"⏰ Vaqt: {existing_time}\n\n"
            f"Ish tugaganda /ketdim ni bosing."
        )
        return

    now = _get_now()
    late_minutes = _calculate_late_minutes(now)

    # Holatni aniqlaymiz (hujjatdagi qoidalarga muvofiq)
    if late_minutes == 0:
        status = "Ozida"
        emoji = "✅"
        comment = "O'z vaqtida keldingiz!"
    elif late_minutes <= 15:
        status = "Kechikdi"
        emoji = "🟡"
        comment = (
            f"{late_minutes} daqiqa kechikdingiz.\n"
            f"<i>Og'zaki ogohlantirish.</i>"
        )
    elif late_minutes <= 60:
        status = "Kechikdi"
        emoji = "🟠"
        comment = (
            f"⚠️ {late_minutes} daqiqa kechikdingiz!\n"
            f"<i>KPI bonusdan 5% kamayadi (hujjat 5.1).</i>"
        )
    else:
        status = "Kechikdi"
        emoji = "🔴"
        comment = (
            f"🚨 {late_minutes} daqiqa kechikdingiz!\n"
            f"<i>KPI bonusdan 10% kamayadi.\n"
            f"Sababini direktorga yozma tushuntiring.</i>"
        )

    employee_name = notion_service._get_title(employee)

    try:
        # Davomatni yozamiz
        await notion_service.create_attendance_record(
            employee_id=employee["id"],
            record_type="Kelish",
            timestamp=now,
            late_minutes=late_minutes,
            status=status,
        )

        # Agar kechikgan bo'lsa - intizomiy chorani avtomatik yozamiz
        if late_minutes > 0:
            try:
                await discipline_service.record_lateness(
                    employee_id=employee["id"],
                    late_minutes=late_minutes,
                )
            except Exception as e:
                # Logga yozamiz, lekin foydalanuvchini xafa qilmaymiz
                import logging
                logging.error(f"Intizomiy chora yozib bo'lmadi: {e}")

        time_str = now.strftime("%H:%M")
        await message.answer(
            f"{emoji} <b>Salom, {employee_name}!</b>\n\n"
            f"⏰ Soat <b>{time_str}</b> da kelganligingiz qayd etildi.\n"
            f"{comment}\n\n"
            f"<i>Ish kuningiz xayrli o'tsin! Ish tugaganda /ketdim ni bosing.</i>"
        )

        # Agar kechikgan bo'lsa, direktorga xabar
        if late_minutes > 15 and config.ADMIN_TELEGRAM_ID:
            try:
                await bot.send_message(
                    chat_id=config.ADMIN_TELEGRAM_ID,
                    text=(
                        f"🔴 <b>Kechikish</b>\n\n"
                        f"👤 {employee_name}\n"
                        f"⏰ Keldi: {time_str}\n"
                        f"⏱ Kechikish: {late_minutes} daqiqa"
                    ),
                )
            except Exception:
                pass

    except Exception as e:
        await message.answer(
            f"❌ Xatolik: davomatni yozib bo'lmadi.\n<code>{str(e)[:200]}</code>"
        )


# ==================== /ketdim — ISH TUGATISH ====================

@router.message(Command("ketdim"))
@router.message(F.text == "🔴 Ketdim")
async def cmd_check_out(message: Message, bot: Bot):
    """Xodim ish tugatganini qayd qilish"""
    if message.chat.type != "private":
        return

    user_id = str(message.from_user.id)
    employee = await notion_service.find_employee_by_telegram_id(user_id)

    if not employee:
        await message.answer("❌ Siz tizimda ro'yxatdan o'tmagansiz.")
        return

    # Bugun ketdim deb yozganmi?
    today_check_outs = await notion_service.get_today_attendance(
        employee["id"], record_type="Ketish"
    )
    if today_check_outs:
        existing_time = notion_service._get_rich_text(
            today_check_outs[0], "Vaqt"
        )
        await message.answer(
            f"ℹ️ Siz bugun allaqachon ketganligingizni qayd etgansiz.\n"
            f"⏰ Vaqt: {existing_time}"
        )
        return

    # Avval keldim qilganmi?
    today_check_ins = await notion_service.get_today_attendance(
        employee["id"], record_type="Kelish"
    )
    if not today_check_ins:
        await message.answer(
            "⚠️ Siz bugun ish boshlaganingizni qayd etmagansiz!\n"
            "Avval /keldim ni bosing."
        )
        return

    now = _get_now()
    employee_name = notion_service._get_title(employee)

    try:
        await notion_service.create_attendance_record(
            employee_id=employee["id"],
            record_type="Ketish",
            timestamp=now,
            status="Ozida",
        )

        # Ish davomiyligini hisoblash
        check_in_time_str = notion_service._get_rich_text(
            today_check_ins[0], "Vaqt"
        )
        try:
            hour, minute = check_in_time_str.split(":")
            check_in_dt = now.replace(
                hour=int(hour), minute=int(minute), second=0, microsecond=0
            )
            duration = _format_duration(check_in_dt, now)
        except Exception:
            duration = "noma'lum"

        time_str = now.strftime("%H:%M")
        await message.answer(
            f"👋 <b>Yaxshi ish, {employee_name}!</b>\n\n"
            f"⏰ Ketish vaqti: <b>{time_str}</b>\n"
            f"⏱ Bugun ishladingiz: <b>{duration}</b>\n\n"
            f"<i>Ertaga ko'rishguncha! 😊</i>"
        )

    except Exception as e:
        await message.answer(
            f"❌ Xatolik: <code>{str(e)[:200]}</code>"
        )


# ==================== /davomat — STATUSNI KO'RISH ====================

@router.message(Command("davomat"))
@router.message(F.text == "📅 Davomat")
async def cmd_attendance_status(message: Message):
    """Bugungi davomat statusini ko'rsatish"""
    if message.chat.type != "private":
        return

    user_id = str(message.from_user.id)
    employee = await notion_service.find_employee_by_telegram_id(user_id)

    if not employee:
        await message.answer("❌ Siz tizimda ro'yxatdan o'tmagansiz.")
        return

    employee_name = notion_service._get_title(employee)
    today = datetime.now().strftime("%Y-%m-%d")

    check_ins = await notion_service.get_today_attendance(
        employee["id"], record_type="Kelish"
    )
    check_outs = await notion_service.get_today_attendance(
        employee["id"], record_type="Ketish"
    )

    text = f"📅 <b>Bugungi davomat — {today}</b>\n👤 {employee_name}\n\n"

    if check_ins:
        time = notion_service._get_rich_text(check_ins[0], "Vaqt")
        late = check_ins[0].get("properties", {}).get("Kechikish daqiqa", {}).get("number") or 0
        text += f"🟢 <b>Keldim:</b> {time}"
        if late > 0:
            text += f" <i>({late} daqiqa kechikish)</i>"
        text += "\n"
    else:
        text += "⚪ <b>Hali kelmagansiz</b> — /keldim bosing\n"

    if check_outs:
        time = notion_service._get_rich_text(check_outs[0], "Vaqt")
        text += f"🔴 <b>Ketdim:</b> {time}\n"
    elif check_ins:
        text += "⚪ <b>Hali ketmagansiz</b> — ish tugaganda /ketdim bosing\n"

    await message.answer(text)
