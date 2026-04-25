"""
Notion API bilan ishlash uchun barcha funksiyalar.
Bu yerda CRUD operatsiyalari va ma'lumot olish funksiyalari joylashgan.
"""
from typing import Optional
from datetime import datetime, timedelta, timezone
from notion_client import AsyncClient
from bot.config import config


class NotionService:
    """Notion API bilan ishlash uchun asosiy klass"""

    def __init__(self):
        self.client = AsyncClient(auth=config.NOTION_TOKEN)

    # ==================== VAZIFALAR ====================

    async def get_tasks_by_employee_telegram_id(
        self, telegram_id: str
    ) -> list[dict]:
        """Xodimning faol vazifalarini olish (Telegram ID orqali)"""
        # Avval xodim sahifasini topamiz
        employee = await self.find_employee_by_telegram_id(telegram_id)
        if not employee:
            return []

        employee_page_id = employee["id"]

        # Xodimga biriktirilgan, tugamagan vazifalar
        response = await self.client.databases.query(
            database_id=config.DB_TASKS,
            filter={
                "and": [
                    {
                        "property": "Masul xodim",
                        "relation": {"contains": employee_page_id},
                    },
                    {
                        "property": "Holati",
                        "select": {"does_not_equal": "Bajarildi"},
                    },
                    {
                        "property": "Holati",
                        "select": {"does_not_equal": "Bekor qilindi"},
                    },
                ]
            },
            sorts=[{"property": "Muddat", "direction": "ascending"}],
        )
        return response.get("results", [])

    async def get_upcoming_tasks(self, hours_ahead: int = 24) -> list[dict]:
        """Yaqin vaqt ichida muddati tugaydigan vazifalar (eslatma uchun)"""
        now = datetime.now(timezone.utc)
        deadline = now + timedelta(hours=hours_ahead)

        response = await self.client.databases.query(
            database_id=config.DB_TASKS,
            filter={
                "and": [
                    {
                        "property": "Muddat",
                        "date": {"on_or_before": deadline.isoformat()},
                    },
                    {
                        "property": "Muddat",
                        "date": {"on_or_after": now.isoformat()},
                    },
                    {
                        "property": "Holati",
                        "select": {"does_not_equal": "Bajarildi"},
                    },
                    {
                        "property": "Eslatma yuborilgan",
                        "checkbox": {"equals": False},
                    },
                ]
            },
        )
        return response.get("results", [])

    async def mark_task_reminder_sent(self, task_page_id: str) -> None:
        """Vazifaga 'eslatma yuborilgan' belgisini qo'yish"""
        await self.client.pages.update(
            page_id=task_page_id,
            properties={"Eslatma yuborilgan": {"checkbox": True}},
        )

    async def create_task(
        self,
        name: str,
        project_id: Optional[str] = None,
        employee_id: Optional[str] = None,
        priority: str = "Orta",
        category: str = "Boshqa",
        deadline: Optional[str] = None,
        description: str = "",
    ) -> dict:
        """Yangi vazifa yaratish"""
        properties = {
            "Vazifa nomi": {"title": [{"text": {"content": name}}]},
            "Holati": {"select": {"name": "Yangi"}},
            "Prioritet": {"select": {"name": priority}},
            "Kategoriya": {"select": {"name": category}},
            "Tavsif": {"rich_text": [{"text": {"content": description}}]},
        }
        if project_id:
            properties["Loyiha"] = {"relation": [{"id": project_id}]}
        if employee_id:
            properties["Masul xodim"] = {"relation": [{"id": employee_id}]}
        if deadline:
            properties["Muddat"] = {"date": {"start": deadline}}

        return await self.client.pages.create(
            parent={"database_id": config.DB_TASKS},
            properties=properties,
        )

    # ==================== XODIMLAR ====================

    async def find_employee_by_telegram_id(
        self, telegram_id: str
    ) -> Optional[dict]:
        """Telegram ID orqali xodimni topish"""
        response = await self.client.databases.query(
            database_id=config.DB_EMPLOYEES,
            filter={
                "property": "Telegram ID",
                "rich_text": {"equals": str(telegram_id)},
            },
        )
        results = response.get("results", [])
        return results[0] if results else None

    async def get_all_employees(self) -> list[dict]:
        """Barcha ishlayotgan xodimlarni olish"""
        response = await self.client.databases.query(
            database_id=config.DB_EMPLOYEES,
            filter={
                "property": "Holati",
                "select": {"equals": "Ishlayapti"},
            },
        )
        return response.get("results", [])

    # ==================== MIJOZLAR ====================

    async def find_client_by_group_id(self, group_id: str) -> Optional[dict]:
        """Telegram guruh ID orqali mijozni topish"""
        response = await self.client.databases.query(
            database_id=config.DB_CLIENTS,
            filter={
                "property": "Telegram guruh ID",
                "rich_text": {"equals": str(group_id)},
            },
        )
        results = response.get("results", [])
        return results[0] if results else None

    async def create_client_from_brief(self, brief_data: dict) -> dict:
        """Brief ma'lumotlaridan yangi mijoz yaratish"""
        properties = {
            "Mijoz nomi": {
                "title": [{"text": {"content": brief_data.get("name", "Yangi mijoz")}}]
            },
            "Kompaniya": {
                "rich_text": [{"text": {"content": brief_data.get("company", "")}}]
            },
            "Aloqa shaxsi": {
                "rich_text": [{"text": {"content": brief_data.get("contact", "")}}]
            },
            "Telefon": {"phone_number": brief_data.get("phone", "")},
            "Holati": {"select": {"name": "Potensial"}},
            "Manba": {"select": {"name": "Telegram"}},
            "Birinchi aloqa sanasi": {
                "date": {"start": datetime.now().strftime("%Y-%m-%d")}
            },
            "Izohlar": {
                "rich_text": [{"text": {"content": brief_data.get("notes", "")}}]
            },
        }
        return await self.client.pages.create(
            parent={"database_id": config.DB_CLIENTS},
            properties=properties,
        )

    # ==================== LOYIHALAR ====================

    async def get_project_by_id(self, project_id: str) -> Optional[dict]:
        """Loyihani ID orqali olish"""
        try:
            return await self.client.pages.retrieve(page_id=project_id)
        except Exception:
            return None

    async def get_projects_by_client(self, client_id: str) -> list[dict]:
        """Mijozning barcha loyihalarini olish"""
        response = await self.client.databases.query(
            database_id=config.DB_PROJECTS,
            filter={
                "property": "Mijoz",
                "relation": {"contains": client_id},
            },
        )
        return response.get("results", [])

    async def get_projects_needing_notification(self) -> list[dict]:
        """
        Oxirgi 30 daqiqada bosqichi o'zgargan loyihalarni olish
        (mijozga xabar yuborish uchun)
        """
        time_threshold = datetime.now(timezone.utc) - timedelta(minutes=35)

        response = await self.client.databases.query(
            database_id=config.DB_PROJECTS,
            filter={
                "timestamp": "last_edited_time",
                "last_edited_time": {"on_or_after": time_threshold.isoformat()},
            },
        )
        return response.get("results", [])

    async def get_active_projects(self) -> list[dict]:
        """Barcha faol loyihalarni olish (nashr qilinmagan)"""
        response = await self.client.databases.query(
            database_id=config.DB_PROJECTS,
            filter={
                "property": "Bosqich",
                "select": {"does_not_equal": "12. Nashr qilindi"},
            },
        )
        return response.get("results", [])

    # ==================== STATISTIKA (DIREKTOR UCHUN) ====================

    async def get_daily_stats(self) -> dict:
        """Direktor uchun kunlik statistika"""
        all_projects = await self.get_active_projects()

        # Bosqich bo'yicha taqsimlash
        stages = {}
        for project in all_projects:
            stage = self._get_select_value(project, "Bosqich")
            if stage:
                stages[stage] = stages.get(stage, 0) + 1

        # Vazifalar
        tasks_response = await self.client.databases.query(
            database_id=config.DB_TASKS,
            filter={
                "property": "Holati",
                "select": {"does_not_equal": "Bajarildi"},
            },
        )
        active_tasks = tasks_response.get("results", [])

        urgent_tasks = [
            t
            for t in active_tasks
            if self._get_select_value(t, "Prioritet") == "Shoshilinch"
        ]

        # Yangi mijozlar (shu hafta)
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        new_clients_response = await self.client.databases.query(
            database_id=config.DB_CLIENTS,
            filter={
                "property": "Birinchi aloqa sanasi",
                "date": {"on_or_after": week_ago},
            },
        )

        return {
            "active_projects": len(all_projects),
            "stages": stages,
            "active_tasks": len(active_tasks),
            "urgent_tasks": len(urgent_tasks),
            "new_clients_this_week": len(new_clients_response.get("results", [])),
        }

    # ==================== HISOBOTLAR ====================

    async def create_employee_report(
        self,
        employee_id: str,
        report_text: str,
        date: Optional[str] = None,
    ) -> dict:
        """
        Xodim hisobotini Bilimlar Bazasiga yozish.
        Har bir xodim kuni uchun alohida sahifa.
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        properties = {
            "Hujjat nomi": {
                "title": [
                    {"text": {"content": f"Kunlik hisobot — {date}"}}
                ]
            },
            "Kategoriya": {"select": {"name": "Boshqa"}},
            "Bolim": {"select": {"name": "Umumiy"}},
            "Holati": {"select": {"name": "Tasdiqlangan"}},
            "Yangilangan sana": {"date": {"start": date}},
            "Masul": {"relation": [{"id": employee_id}]},
        }

        # Sahifa yaratish va mazmunini qo'shish
        page = await self.client.pages.create(
            parent={"database_id": config.DB_KNOWLEDGE},
            properties=properties,
            children=[
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": report_text}}]
                    },
                }
            ],
        )
        return page

    # ==================== YORDAMCHI FUNKSIYALAR ====================

    @staticmethod
    def _get_title(page: dict, field: str = None) -> str:
        """Sahifadan title qiymatini olish"""
        properties = page.get("properties", {})
        for key, value in properties.items():
            if value.get("type") == "title":
                if field is None or key == field:
                    title_list = value.get("title", [])
                    if title_list:
                        return title_list[0].get("plain_text", "")
        return ""

    @staticmethod
    def _get_select_value(page: dict, field: str) -> Optional[str]:
        """Select yoki status qiymatini olish"""
        prop = page.get("properties", {}).get(field, {})
        if prop.get("type") == "select" and prop.get("select"):
            return prop["select"].get("name")
        if prop.get("type") == "status" and prop.get("status"):
            return prop["status"].get("name")
        return None

    @staticmethod
    def _get_rich_text(page: dict, field: str) -> str:
        """Rich text qiymatini olish"""
        prop = page.get("properties", {}).get(field, {})
        rich_text = prop.get("rich_text", [])
        if rich_text:
            return "".join([t.get("plain_text", "") for t in rich_text])
        return ""

    @staticmethod
    def _get_date(page: dict, field: str) -> Optional[str]:
        """Sana qiymatini olish"""
        prop = page.get("properties", {}).get(field, {})
        if prop.get("type") == "date" and prop.get("date"):
            return prop["date"].get("start")
        return None

    @staticmethod
    def _get_relation_ids(page: dict, field: str) -> list[str]:
        """Relation maydonidagi ID'lar ro'yxatini olish"""
        prop = page.get("properties", {}).get(field, {})
        relations = prop.get("relation", [])
        return [r.get("id") for r in relations]

    # ==================== DAVOMAT (KELISH/KETISH) ====================

    async def create_attendance_record(
        self,
        employee_id: str,
        record_type: str,  # "Kelish" yoki "Ketish"
        timestamp: datetime,
        late_minutes: int = 0,
        status: str = "Ozida",
        note: str = "",
    ) -> dict:
        """
        Davomat yozuvini yaratish (xodim keldi yoki ketdi)
        """
        date_str = timestamp.strftime("%Y-%m-%d")
        time_str = timestamp.strftime("%H:%M")
        title = f"{record_type} — {date_str} {time_str}"

        properties = {
            "Sana va vaqt": {"title": [{"text": {"content": title}}]},
            "Xodim": {"relation": [{"id": employee_id}]},
            "Turi": {"select": {"name": record_type}},
            "Sana": {"date": {"start": date_str}},
            "Vaqt": {"rich_text": [{"text": {"content": time_str}}]},
            "Holati": {"select": {"name": status}},
        }

        if late_minutes > 0:
            properties["Kechikish daqiqa"] = {"number": late_minutes}

        if note:
            properties["Izoh"] = {"rich_text": [{"text": {"content": note}}]}

        return await self.client.pages.create(
            parent={"database_id": config.DB_ATTENDANCE},
            properties=properties,
        )

    async def get_today_attendance(
        self, employee_id: str, record_type: Optional[str] = None
    ) -> list[dict]:
        """
        Xodimning bugungi davomat yozuvlarini olish.
        record_type berilsa, faqat o'sha turdagi yozuvlar.
        """
        today = datetime.now().strftime("%Y-%m-%d")

        filters = [
            {"property": "Xodim", "relation": {"contains": employee_id}},
            {"property": "Sana", "date": {"equals": today}},
        ]
        if record_type:
            filters.append(
                {"property": "Turi", "select": {"equals": record_type}}
            )

        response = await self.client.databases.query(
            database_id=config.DB_ATTENDANCE,
            filter={"and": filters},
        )
        return response.get("results", [])

    # ==================== VAZIFA TASDIQLASH ====================

    async def get_task_by_id(self, task_id: str) -> Optional[dict]:
        """Vazifa ma'lumotlarini ID orqali olish"""
        try:
            return await self.client.pages.retrieve(page_id=task_id)
        except Exception:
            return None

    async def complete_task(
        self,
        task_id: str,
        result_link: str = "",
        completion_note: str = "",
    ) -> dict:
        """
        Vazifani 'Bajarildi' holatiga o'tkazish.
        Natija havolasi va izoh ham qo'shiladi.
        """
        today = datetime.now().strftime("%Y-%m-%d")

        properties = {
            "Holati": {"select": {"name": "Bajarildi"}},
            "Bajarilgan sana": {"date": {"start": today}},
        }

        if result_link:
            properties["Natija havolasi"] = {"url": result_link}

        page = await self.client.pages.update(
            page_id=task_id,
            properties=properties,
        )

        # Izohni vazifa sahifasiga blok sifatida qo'shamiz
        if completion_note:
            try:
                await self.client.blocks.children.append(
                    block_id=task_id,
                    children=[
                        {
                            "object": "block",
                            "type": "callout",
                            "callout": {
                                "rich_text": [
                                    {
                                        "type": "text",
                                        "text": {
                                            "content": (
                                                f"✅ Bajarilgan ({today}):\n"
                                                f"{completion_note}"
                                            )
                                        },
                                    }
                                ],
                                "icon": {"type": "emoji", "emoji": "✅"},
                                "color": "green_background",
                            },
                        }
                    ],
                )
            except Exception:
                pass  # Agar block qo'shib bo'lmasa, vazifa baribir bajarilgan

        return page


# Singleton instance
notion_service = NotionService()
