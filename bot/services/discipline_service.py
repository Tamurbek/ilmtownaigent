"""
Intizomiy choralar va mukofot tizimi.

Hujjat asosida:
- Kechikish > 15 daq → 5% bonus kamayadi
- Kechikish > 60 daq → 10% bonus kamayadi
- Sababsiz kelmaslik → 100% bonus mahrum
- Vazifa bajarilmaslik (1-marta) → og'zaki ogohlantirish
- Vazifa bajarilmaslik (2-marta oyda) → yozma ogohlantirish + KPI vazifa qismi mahrum
- Vazifa bajarilmaslik (3-marta) → 100% bonus mahrum

KPI:
- Intizom 5%, Vazifalar 10%, Sifat 5% = 20% jami

Mukofot:
- 70-79% → ommaviy minnatdorchilik
- 80-89% → KPI + tushlik
- 90-99% → KPI + sovg'a
- 100% → KPI + qimmatroq sovg'a + 1 kun dam olish
"""
from datetime import datetime, timedelta
from typing import Optional

from bot.config import config
from bot.services.notion_service import notion_service


class DisciplineService:
    """Intizom va mukofot xizmati"""

    # ==================== INTIZOM ====================

    @classmethod
    async def record_lateness(
        cls,
        employee_id: str,
        late_minutes: int,
        date_str: Optional[str] = None,
    ) -> dict:
        """
        Kechikish voqeasini ro'yxatga olish.
        Hujjat asosida avtomatik chora belgilanadi.
        """
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        # Voqea turi va bonus kamaytirish foizi (hujjat asosida)
        if late_minutes <= 15:
            event_type = "Kechikish 15 daq"
            chora = "Ogzaki ogohlantirish"
            bonus_reduction = 0
        elif late_minutes <= 60:
            event_type = "Kechikish 15-60 daq"
            chora = "Bonusdan 5% kamaytirish"
            bonus_reduction = 5
        else:
            event_type = "Kechikish 1 soat+"
            chora = "Bonusdan 10% kamaytirish"
            bonus_reduction = 10

        # Bu xil voqea oyda qanchalik takrorlangan?
        repeat_count = await cls._count_monthly_events(
            employee_id, event_type
        )

        # Takrorlanса - chorani kuchaytiramiz
        if repeat_count >= 3:
            chora = "Bonusdan 100% mahrum"
            bonus_reduction = 100

        # Voqeani yozamiz
        title = f"Kechikish ({late_minutes} daq) — {date_str}"

        properties = {
            "Voqea nomi": {"title": [{"text": {"content": title}}]},
            "Xodim": {"relation": [{"id": employee_id}]},
            "Sana": {"date": {"start": date_str}},
            "Voqea turi": {"select": {"name": event_type}},
            "Chora turi": {"select": {"name": chora}},
            "Bonus kamaytirish foiz": {"number": bonus_reduction},
            "Bu xil voqea soni oyda": {"number": repeat_count + 1},
        }

        # 60+ daqiqa kechikish → tushuntirish kerak
        if late_minutes > 60:
            properties["Tushuntirish kerak"] = {"checkbox": True}

        return await notion_service.client.pages.create(
            parent={"database_id": config.DB_DISCIPLINE},
            properties=properties,
        )

    @classmethod
    async def record_task_failure(
        cls,
        employee_id: str,
        task_name: str,
        date_str: Optional[str] = None,
    ) -> dict:
        """
        Vazifa bajarilmaganligini ro'yxatga olish.
        Oydagi takrorlanish soniga qarab chora belgilanadi.
        """
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        # Bu oyda nechta vazifa bajarilmagan?
        repeat_count = await cls._count_monthly_events(
            employee_id, "Vazifa bajarilmadi"
        )

        # Hujjat asosida chora
        if repeat_count == 0:
            chora = "Ogzaki ogohlantirish"
            bonus_reduction = 0
            tushuntirish = True
        elif repeat_count == 1:
            chora = "Yozma ogohlantirish"
            bonus_reduction = 10  # KPI vazifa qismi (10%) mahrum
            tushuntirish = True
        else:  # 2+ marta = 3-chi marta
            chora = "Bonusdan 100% mahrum"
            bonus_reduction = 100
            tushuntirish = True

        title = f"Vazifa bajarilmadi: {task_name[:80]} — {date_str}"

        properties = {
            "Voqea nomi": {"title": [{"text": {"content": title}}]},
            "Xodim": {"relation": [{"id": employee_id}]},
            "Sana": {"date": {"start": date_str}},
            "Voqea turi": {"select": {"name": "Vazifa bajarilmadi"}},
            "Chora turi": {"select": {"name": chora}},
            "Bonus kamaytirish foiz": {"number": bonus_reduction},
            "Bu xil voqea soni oyda": {"number": repeat_count + 1},
            "Tushuntirish kerak": {"checkbox": tushuntirish},
            "Tafsilot": {
                "rich_text": [
                    {"text": {"content": f"Vazifa: {task_name}"}}
                ]
            },
        }

        return await notion_service.client.pages.create(
            parent={"database_id": config.DB_DISCIPLINE},
            properties=properties,
        )

    @classmethod
    async def _count_monthly_events(
        cls, employee_id: str, event_type: str
    ) -> int:
        """Joriy oyda shu turdagi voqealar soni"""
        # Joriy oyning birinchi kuni
        today = datetime.now()
        month_start = today.replace(day=1).strftime("%Y-%m-%d")

        try:
            response = await notion_service.client.databases.query(
                database_id=config.DB_DISCIPLINE,
                filter={
                    "and": [
                        {
                            "property": "Xodim",
                            "relation": {"contains": employee_id},
                        },
                        {
                            "property": "Voqea turi",
                            "select": {"equals": event_type},
                        },
                        {
                            "property": "Sana",
                            "date": {"on_or_after": month_start},
                        },
                    ]
                },
            )
            return len(response.get("results", []))
        except Exception:
            return 0

    # ==================== KPI HISOBOT ====================

    @classmethod
    async def calculate_monthly_kpi(
        cls,
        employee_id: str,
        month_start: str,  # "2026-04-01"
        month_end: str,  # "2026-04-30"
    ) -> dict:
        """
        Xodim uchun oylik KPI hisoblash.

        Hujjat asosida:
        - Intizom (5%): kechikishlar yo'q yoki 1 dan kam = to'liq, aks holda kamayadi
        - Vazifalar (10%): vazifalarning 90%+ bajarilgan = to'liq
        - Sifat (5%): mijoz/rahbar shikoyati yo'q (manual baholash)
        """
        # 1. Intizom ballini hisoblash
        late_count = await cls._count_lateness(employee_id, month_start, month_end)
        absence_count = await cls._count_absences(
            employee_id, month_start, month_end
        )

        if late_count == 0 and absence_count == 0:
            discipline_score = 5  # to'liq 5%
        elif late_count <= 1 and absence_count == 0:
            discipline_score = 4  # 1 marta kechikish - 4%
        elif late_count <= 3:
            discipline_score = 2  # 2-3 marta - yarmi
        else:
            discipline_score = 0  # ko'p kechikish - yo'q

        # 2. Vazifalar ballini hisoblash
        completion_rate = await cls._calculate_completion_rate(
            employee_id, month_start, month_end
        )

        if completion_rate >= 90:
            tasks_score = 10  # 90%+ = to'liq 10%
        elif completion_rate >= 80:
            tasks_score = 7
        elif completion_rate >= 70:
            tasks_score = 5
        elif completion_rate >= 50:
            tasks_score = 3
        else:
            tasks_score = 0

        # 3. Sifat ballini hisoblash (shikoyat soni asosida)
        complaint_count = await cls._count_complaints(
            employee_id, month_start, month_end
        )

        if complaint_count == 0:
            quality_score = 5  # to'liq 5%
        elif complaint_count == 1:
            quality_score = 3
        elif complaint_count == 2:
            quality_score = 1
        else:
            quality_score = 0

        # Jami KPI foiz
        total_kpi_percent = discipline_score + tasks_score + quality_score

        # Mukofot turi (vazifalar bajarish foiziga qarab)
        if completion_rate >= 100:
            reward = "KPI + Qimmat sovga + Dam olish"
        elif completion_rate >= 90:
            reward = "KPI + Sovga"
        elif completion_rate >= 80:
            reward = "KPI + Tushlik"
        elif completion_rate >= 70:
            reward = "Ommaviy minnatdorchilik"
        else:
            reward = "Hech narsa"

        # Bajarilmagan vazifalar
        unfinished = await cls._count_unfinished_tasks(
            employee_id, month_start, month_end
        )

        # Ogohlantirishlar
        warnings = await cls._count_all_warnings(
            employee_id, month_start, month_end
        )

        return {
            "discipline_score": discipline_score,
            "tasks_score": tasks_score,
            "quality_score": quality_score,
            "total_kpi_percent": total_kpi_percent,
            "completion_rate": completion_rate,
            "lateness_count": late_count,
            "absence_count": absence_count,
            "unfinished_tasks": unfinished,
            "warnings_count": warnings,
            "complaint_count": complaint_count,
            "reward_type": reward,
        }

    @classmethod
    async def save_kpi_record(
        cls,
        employee_id: str,
        employee_name: str,
        month_start: str,
        month_end: str,
        kpi_data: dict,
        salary_uzs: int = 0,
        salary_usd: float = 0,
    ) -> dict:
        """KPI hisobini Notion'ga saqlash"""
        title = f"{employee_name} — {month_start[:7]}"

        # KPI bonus hisoblash (asosiy maoshning foizi)
        bonus_uzs = int(salary_uzs * kpi_data["total_kpi_percent"] / 100)
        bonus_usd = round(salary_usd * kpi_data["total_kpi_percent"] / 100, 2)

        properties = {
            "Davr nomi": {"title": [{"text": {"content": title}}]},
            "Xodim": {"relation": [{"id": employee_id}]},
            "Davr boshi": {"date": {"start": month_start}},
            "Davr oxiri": {"date": {"start": month_end}},
            "Asosiy maosh USD": {"number": salary_usd},
            "Asosiy maosh UZS": {"number": salary_uzs},
            "Intizom ball": {"number": kpi_data["discipline_score"]},
            "Vazifalar ball": {"number": kpi_data["tasks_score"]},
            "Sifat ball": {"number": kpi_data["quality_score"]},
            "Umumiy KPI foiz": {"number": kpi_data["total_kpi_percent"]},
            "KPI bonus USD": {"number": bonus_usd},
            "KPI bonus UZS": {"number": bonus_uzs},
            "Bajarilgan vazifalar foizi": {
                "number": kpi_data["completion_rate"]
            },
            "Kechikishlar soni": {"number": kpi_data["lateness_count"]},
            "Bajarilmagan vazifalar": {
                "number": kpi_data["unfinished_tasks"]
            },
            "Ogohlantirishlar": {"number": kpi_data["warnings_count"]},
            "Mukofot turi": {"select": {"name": kpi_data["reward_type"]}},
            "Holati": {"select": {"name": "Hisoblanmoqda"}},
        }

        return await notion_service.client.pages.create(
            parent={"database_id": config.DB_KPI},
            properties=properties,
        )

    # ==================== HISOBLASH FUNKSIYALARI ====================

    @classmethod
    async def _count_lateness(
        cls, employee_id: str, start: str, end: str
    ) -> int:
        """Davrdagi kechikishlar soni"""
        try:
            response = await notion_service.client.databases.query(
                database_id=config.DB_DISCIPLINE,
                filter={
                    "and": [
                        {
                            "property": "Xodim",
                            "relation": {"contains": employee_id},
                        },
                        {
                            "or": [
                                {
                                    "property": "Voqea turi",
                                    "select": {"equals": "Kechikish 15 daq"},
                                },
                                {
                                    "property": "Voqea turi",
                                    "select": {"equals": "Kechikish 15-60 daq"},
                                },
                                {
                                    "property": "Voqea turi",
                                    "select": {"equals": "Kechikish 1 soat+"},
                                },
                            ]
                        },
                        {"property": "Sana", "date": {"on_or_after": start}},
                        {"property": "Sana", "date": {"on_or_before": end}},
                    ]
                },
            )
            return len(response.get("results", []))
        except Exception:
            return 0

    @classmethod
    async def _count_absences(
        cls, employee_id: str, start: str, end: str
    ) -> int:
        """Sababsiz kelmaslik soni"""
        try:
            response = await notion_service.client.databases.query(
                database_id=config.DB_DISCIPLINE,
                filter={
                    "and": [
                        {
                            "property": "Xodim",
                            "relation": {"contains": employee_id},
                        },
                        {
                            "property": "Voqea turi",
                            "select": {"equals": "Sababsiz kelmaslik"},
                        },
                        {"property": "Sana", "date": {"on_or_after": start}},
                        {"property": "Sana", "date": {"on_or_before": end}},
                    ]
                },
            )
            return len(response.get("results", []))
        except Exception:
            return 0

    @classmethod
    async def _calculate_completion_rate(
        cls, employee_id: str, start: str, end: str
    ) -> float:
        """Vazifalar bajarilish foizi"""
        try:
            # Davrdagi xodimga berilgan barcha vazifalar
            response = await notion_service.client.databases.query(
                database_id=config.DB_TASKS,
                filter={
                    "and": [
                        {
                            "property": "Masul xodim",
                            "relation": {"contains": employee_id},
                        },
                    ]
                },
            )
            all_tasks = response.get("results", [])

            # Davrga tegishli (Muddat oraliqda)
            relevant_tasks = []
            for task in all_tasks:
                deadline = notion_service._get_date(task, "Muddat")
                if deadline and start <= deadline <= end:
                    relevant_tasks.append(task)

            if not relevant_tasks:
                return 100.0  # vazifa yo'q = 100%

            # Bajarilganlar
            completed = [
                t
                for t in relevant_tasks
                if notion_service._get_select_value(t, "Holati") == "Bajarildi"
            ]

            return round(len(completed) / len(relevant_tasks) * 100, 1)
        except Exception:
            return 0.0

    @classmethod
    async def _count_unfinished_tasks(
        cls, employee_id: str, start: str, end: str
    ) -> int:
        """Bajarilmagan vazifalar soni (muddati o'tib ketgan)"""
        try:
            response = await notion_service.client.databases.query(
                database_id=config.DB_TASKS,
                filter={
                    "and": [
                        {
                            "property": "Masul xodim",
                            "relation": {"contains": employee_id},
                        },
                        {
                            "property": "Holati",
                            "select": {"does_not_equal": "Bajarildi"},
                        },
                        {
                            "property": "Holati",
                            "select": {"does_not_equal": "Bekor qilindi"},
                        },
                        {"property": "Muddat", "date": {"on_or_after": start}},
                        {"property": "Muddat", "date": {"on_or_before": end}},
                    ]
                },
            )
            return len(response.get("results", []))
        except Exception:
            return 0

    @classmethod
    async def _count_complaints(
        cls, employee_id: str, start: str, end: str
    ) -> int:
        """Mijoz/rahbar shikoyatlari soni"""
        try:
            response = await notion_service.client.databases.query(
                database_id=config.DB_DISCIPLINE,
                filter={
                    "and": [
                        {
                            "property": "Xodim",
                            "relation": {"contains": employee_id},
                        },
                        {
                            "property": "Voqea turi",
                            "select": {"equals": "Mijozga noprofessional"},
                        },
                        {"property": "Sana", "date": {"on_or_after": start}},
                        {"property": "Sana", "date": {"on_or_before": end}},
                    ]
                },
            )
            return len(response.get("results", []))
        except Exception:
            return 0

    @classmethod
    async def _count_all_warnings(
        cls, employee_id: str, start: str, end: str
    ) -> int:
        """Hammma ogohlantirishlar soni"""
        try:
            response = await notion_service.client.databases.query(
                database_id=config.DB_DISCIPLINE,
                filter={
                    "and": [
                        {
                            "property": "Xodim",
                            "relation": {"contains": employee_id},
                        },
                        {"property": "Sana", "date": {"on_or_after": start}},
                        {"property": "Sana", "date": {"on_or_before": end}},
                    ]
                },
            )
            return len(response.get("results", []))
        except Exception:
            return 0


# Singleton
discipline_service = DisciplineService()
