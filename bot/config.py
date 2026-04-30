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

    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "8528223059:AAF9tBfyBtYSN_Ni4bi4QKcoTBAvMXYdV1w")
    ADMIN_TELEGRAM_ID: int = int(os.getenv("ADMIN_TELEGRAM_ID", "703665167"))
    ADMIN_GROUP_ID: int = int(os.getenv("ADMIN_GROUP_ID", "1002782538826"))

    NOTION_TOKEN: str = os.getenv("NOTION_TOKEN", "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")

    # Notion Databases
    DB_SERVICES: str = os.getenv("NOTION_DB_SERVICES", "249145d9-77df-4cfe-badc-228ab8a57cf6")
    DB_EMPLOYEES: str = os.getenv("NOTION_DB_EMPLOYEES", "410d5f0f-dd90-407a-a6b2-4561b2bae1d7")
    DB_CLIENTS: str = os.getenv("NOTION_DB_CLIENTS", "410d5f0f-dd90-407a-a6b2-4561b2bae1d7")
    DB_PROJECTS: str = os.getenv("NOTION_DB_PROJECTS", "410d5f0f-dd90-407a-a6b2-4561b2bae1d7")
    DB_TASKS: str = os.getenv("NOTION_DB_TASKS", "8b4f8c5b-d030-4dec-9b0f-193047043011")
    DB_FINANCE: str = os.getenv("NOTION_DB_FINANCE", "208d5bcf-9a51-488c-9369-1a12adb72b0e")
    DB_CONTENT: str = os.getenv("NOTION_DB_CONTENT", "762ad835-53e9-4b15-8deb-259dc7ce77a1")
    DB_KNOWLEDGE: str = os.getenv("NOTION_DB_KNOWLEDGE", "84810c8d-bd10-48fb-afac-2c68251792bb")
    DB_ATTENDANCE: str = os.getenv("NOTION_DB_ATTENDANCE", "724ab474-f76d-445f-b6ef-b1fedd31e126")
    DB_CONTENT_PLAN: str = os.getenv("NOTION_DB_CONTENT_PLAN", "d73a3240-d856-43af-8be9-d01e95a44dd1")
    DB_KPI: str = os.getenv("NOTION_DB_KPI", "cfac5aa8-a0b5-4b18-badf-dfd626a254e7")
    DB_DISCIPLINE: str = os.getenv("NOTION_DB_DISCIPLINE", "d5c4f6ec-2b3a-4ebe-b675-89b20c1d97cb")
    DB_PRICES: str = os.getenv("NOTION_DB_PRICES", "db6420e3-ba2b-419d-9bb4-f0065dc133d4")
    DB_COMPLETED_JOBS: str = os.getenv("NOTION_DB_COMPLETED_JOBS", "ce25574b-9593-4acf-88df-5a8f469387a8")

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
