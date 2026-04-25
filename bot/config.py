"""
Konfiguratsiya fayli - barcha sozlamalar shu yerda.
.env faylidan o'qiydi.
"""
import os
from dotenv import load_dotenv

# .env faylni yuklash
load_dotenv()


class Config:
    """Bot uchun barcha sozlamalar"""

    # Telegram Bot
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_TELEGRAM_ID: int = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))
    ADMIN_GROUP_ID: int = int(os.getenv("ADMIN_GROUP_ID", "0"))

    # Notion
    NOTION_TOKEN: str = os.getenv("NOTION_TOKEN", "")

    # Notion Databases
    DB_SERVICES: str = os.getenv("NOTION_DB_SERVICES", "")
    DB_EMPLOYEES: str = os.getenv("NOTION_DB_EMPLOYEES", "")
    DB_CLIENTS: str = os.getenv("NOTION_DB_CLIENTS", "")
    DB_PROJECTS: str = os.getenv("NOTION_DB_PROJECTS", "")
    DB_TASKS: str = os.getenv("NOTION_DB_TASKS", "")
    DB_FINANCE: str = os.getenv("NOTION_DB_FINANCE", "")
    DB_CONTENT: str = os.getenv("NOTION_DB_CONTENT", "")
    DB_KNOWLEDGE: str = os.getenv("NOTION_DB_KNOWLEDGE", "")
    DB_ATTENDANCE: str = os.getenv("NOTION_DB_ATTENDANCE", "")
    DB_CONTENT_PLAN: str = os.getenv("NOTION_DB_CONTENT_PLAN", "")
    DB_KPI: str = os.getenv("NOTION_DB_KPI", "")
    DB_DISCIPLINE: str = os.getenv("NOTION_DB_DISCIPLINE", "")
    DB_PRICES: str = os.getenv("NOTION_DB_PRICES", "")
    DB_COMPLETED_JOBS: str = os.getenv("NOTION_DB_COMPLETED_JOBS", "")

    # Scheduler
    DAILY_REPORT_TIME: str = os.getenv("DAILY_REPORT_TIME", "09:00")
    REMINDER_CHECK_INTERVAL_MINUTES: int = int(
        os.getenv("REMINDER_CHECK_INTERVAL_MINUTES", "30")
    )
    TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Tashkent")

    # Ish vaqti (kechikish hisoblash uchun) - hujjat asosida
    WORK_START_TIME: str = os.getenv("WORK_START_TIME", "08:30")
    WORK_END_TIME: str = os.getenv("WORK_END_TIME", "19:00")
    LUNCH_START_TIME: str = os.getenv("LUNCH_START_TIME", "13:00")
    LUNCH_END_TIME: str = os.getenv("LUNCH_END_TIME", "13:45")

    @classmethod
    def validate(cls) -> bool:
        """Barcha majburiy sozlamalar mavjudligini tekshirish"""
        required = {
            "BOT_TOKEN": cls.BOT_TOKEN,
            "NOTION_TOKEN": cls.NOTION_TOKEN,
            "ADMIN_TELEGRAM_ID": cls.ADMIN_TELEGRAM_ID,
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            print(f"❌ Quyidagi sozlamalar yo'q: {', '.join(missing)}")
            print("   .env faylni tekshiring!")
            return False
        return True


config = Config()
