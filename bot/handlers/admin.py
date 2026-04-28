"""
Direktor uchun buyruqlar:
- /statistika
- /mijozlar
- /hafta_hisoboti
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import config
from bot.services.notion_service import notion_service
from bot.utils.messages import format_daily_report

router = Router()


def admin_only(func):
    """Faqat direktor uchun dekorator"""

    async def wrapper(message: Message, **kwargs):
        if message.from_user.id != config.ADMIN_TELEGRAM_ID:
            await message.answer("⛔ Bu buyruq faqat direktor uchun.")
            return
        # kwargs (dispatcher, bot va h.k.) ni func ga uzatish
        # lekin func qabul qiladigan argumentlarni filterlaymiz
        import inspect
        sig = inspect.signature(func)
        valid_kwargs = {
            k: v for k, v in kwargs.items() if k in sig.parameters
        }
        return await func(message, **valid_kwargs)

    return wrapper


@router.message(Command("statistika"))
@router.message(F.text == "📊 Statistika")
@admin_only
async def cmd_stats(message: Message):
    """Bugungi statistika"""
    await message.answer("⏳ Statistikani yig'yapman...")

    try:
        stats = await notion_service.get_daily_stats()
        text = format_daily_report(stats)
        await message.answer(text)
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)[:200]}")


@router.message(Command("mijozlar"))
@router.message(F.text == "🎯 Mijozlar")
@admin_only
async def cmd_clients(message: Message):
    """Mijozlar ro'yxati"""
    response = await notion_service.client.databases.query(
        database_id=config.DB_CLIENTS,
        filter={
            "property": "Holati",
            "select": {"equals": "Faol mijoz"},
        },
    )

    clients = response.get("results", [])

    if not clients:
        await message.answer("📭 Hozircha faol mijozlar yo'q.")
        return

    text = f"🤝 <b>Faol mijozlar ({len(clients)} ta):</b>\n\n"

    for client in clients[:20]:
        name = notion_service._get_title(client)
        company = notion_service._get_rich_text(client, "Kompaniya")
        field = notion_service._get_select_value(client, "Faoliyat sohasi")

        text += f"• <b>{name}</b>"
        if company:
            text += f" ({company})"
        if field:
            text += f" — {field}"
        text += "\n"

    if len(clients) > 20:
        text += f"\n<i>Va yana {len(clients) - 20} ta...</i>"

    await message.answer(text)


@router.message(Command("loyihalar"))
@router.message(F.text == "💼 Loyihalar")
@admin_only
async def cmd_projects(message: Message):
    """Faol loyihalar ro'yxati"""
    projects = await notion_service.get_active_projects()

    if not projects:
        await message.answer("📭 Hozircha faol loyihalar yo'q.")
        return

    # Bosqich bo'yicha guruhlash
    by_stage = {}
    for project in projects:
        stage = notion_service._get_select_value(project, "Bosqich") or "Belgilanmagan"
        by_stage.setdefault(stage, []).append(project)

    text = f"💼 <b>Faol loyihalar ({len(projects)} ta)</b>\n\n"

    for stage in sorted(by_stage.keys()):
        text += f"\n<b>{stage}</b> ({len(by_stage[stage])} ta):\n"
        for project in by_stage[stage][:5]:
            name = notion_service._get_title(project)
            text += f"  • {name}\n"
        if len(by_stage[stage]) > 5:
            text += f"  <i>...va yana {len(by_stage[stage]) - 5} ta</i>\n"

    await message.answer(text)


@router.message(Command("xodimlar"))
@router.message(F.text == "👥 Xodimlar")
@admin_only
async def cmd_employees(message: Message):
    """Xodimlar ro'yxati"""
    employees = await notion_service.get_all_employees()

    if not employees:
        await message.answer("📭 Xodimlar yo'q.")
        return

    text = f"👥 <b>Xodimlar ({len(employees)} ta):</b>\n\n"

    for emp in employees:
        name = notion_service._get_title(emp)
        role = notion_service._get_select_value(emp, "Lavozim") or "—"
        tg_id = notion_service._get_rich_text(emp, "Telegram ID")

        text += f"• <b>{name}</b> — {role}"
        if tg_id:
            text += " ✅"
        else:
            text += " ⚠️ <i>(Telegram ID yo'q)</i>"
        text += "\n"

    await message.answer(text)
