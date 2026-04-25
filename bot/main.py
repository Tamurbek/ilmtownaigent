"""
Biznestown Agency Telegram Bot
Asosiy ishga tushirish fayli.

Ishga tushirish:
    python -m bot.main
"""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import config
from bot.handlers import (
    start,
    employee,
    client_brief,
    admin,
    attendance,
    task_complete,
    create_task,
    auto_task,
    kpi,
    jobs,
)
from bot.services.scheduler import setup_scheduler


# Logging sozlash
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)


async def main():
    """Asosiy ishga tushirish funksiyasi"""

    # Konfiguratsiyani tekshirish
    if not config.validate():
        logger.error("❌ Konfiguratsiya noto'g'ri. .env faylni tekshiring.")
        return

    logger.info("=" * 50)
    logger.info("🤖 Biznestown Agency Bot ishga tushmoqda...")
    logger.info("=" * 50)

    # Bot va Dispatcher yaratish
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(storage=MemoryStorage())

    # Handlerlarni ulash (tartib muhim! task_complete oldinroq, chunki F.text == "📋 Vazifalarim" bilan oldin ushlaydi)
    dp.include_router(start.router)
    dp.include_router(attendance.router)
    dp.include_router(task_complete.router)
    dp.include_router(auto_task.router)
    dp.include_router(create_task.router)
    dp.include_router(kpi.router)
    dp.include_router(jobs.router)
    dp.include_router(employee.router)
    dp.include_router(client_brief.router)
    dp.include_router(admin.router)

    # Schedulerni ishga tushirish
    scheduler = setup_scheduler(bot)

    # Bot ma'lumotlarini tekshirish
    try:
        me = await bot.get_me()
        logger.info(f"✅ Bot @{me.username} ulandi")
    except Exception as e:
        logger.error(f"❌ Botni ulab bo'lmadi: {e}")
        return

    # Adminlarga bot ishga tushganligi haqida xabar
    try:
        await bot.send_message(
            chat_id=config.ADMIN_TELEGRAM_ID,
            text="🟢 <b>Bot ishga tushdi!</b>\n\nBarcha avtomatik vazifalar faol.",
        )
    except Exception as e:
        logger.warning(f"Admin xabar yuborib bo'lmadi: {e}")

    # Polling boshlash
    try:
        logger.info("🚀 Bot polling boshladi...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.error(f"❌ Polling xatoligi: {e}")
    finally:
        scheduler.stop()
        await bot.session.close()
        logger.info("👋 Bot to'xtatildi")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹ Ctrl+C tugmasi bosildi, bot to'xtatildi")
