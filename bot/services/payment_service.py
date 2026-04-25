"""
Operator va montajchilar uchun ish narxi hisoblash xizmati.

Per-piece tizim:
1. Bazaviy narx (kategoriya bo'yicha)
2. Sifat koef: Yaxshi ×1.2 | Orta ×1.0 | Yomon ×0.7
3. Kechikish koef: Oldin ×1.1 | O'z vaq ×1.0 | 1 kun ×0.9 | 2 kun ×0.8 | 3+ ×0.7
4. Deadline bonus: 1 kun oldin +10k | 2 kun +20k | 3+ kun +30k

Yakuniy = (Bazaviy × Sifat × Kechikish) + Deadline bonus

Oylik bonuslar (oy oxirida hisoblanadi):
- 30+ ish: +5%
- 50+ ish: +10%
- 70+ ish: +15%
- Top performer: +200,000 (1-o'rinda)
"""
from datetime import datetime
from typing import Optional

from bot.config import config
from bot.services.notion_service import notion_service


# Sifat koeffitsientlari
QUALITY_COEF = {
    "Yaxshi": 1.2,
    "Orta": 1.0,
    "Yomon": 0.7,
}

# Kechikish koeffitsientlari
DELAY_COEF = {
    "Muddatdan oldin": 1.1,
    "Oz vaqtida": 1.0,
    "1 kun kechikkan": 0.9,
    "2 kun kechikkan": 0.8,
    "3+ kun kechikkan": 0.7,
}

# Deadline bonus (UZS) - muddatdan necha kun oldin
DEADLINE_BONUS = {
    1: 10_000,
    2: 20_000,
    3: 30_000,  # 3+ kun
}

# Oylik son bonusi
MONTHLY_VOLUME_BONUS = {
    30: 0.05,  # 30+ ish: +5%
    50: 0.10,  # 50+ ish: +10%
    70: 0.15,  # 70+ ish: +15%
}

TOP_PERFORMER_BONUS = 200_000


class PaymentService:
    """Per-piece to'lov xizmati"""

    @classmethod
    def calculate_job_price(
        cls,
        base_price: int,
        quality: str = "Orta",
        delay_status: str = "Oz vaqtida",
        days_before_deadline: int = 0,
    ) -> dict:
        """
        Bitta ish uchun yakuniy narxni hisoblash.

        Returns:
            {
                "base_price": 55000,
                "quality_coef": 1.2,
                "delay_coef": 1.0,
                "deadline_bonus": 20000,
                "final_price": 86000,
            }
        """
        quality_coef = QUALITY_COEF.get(quality, 1.0)
        delay_coef = DELAY_COEF.get(delay_status, 1.0)

        # Deadline bonus
        deadline_bonus = 0
        if days_before_deadline >= 3:
            deadline_bonus = DEADLINE_BONUS[3]
        elif days_before_deadline == 2:
            deadline_bonus = DEADLINE_BONUS[2]
        elif days_before_deadline == 1:
            deadline_bonus = DEADLINE_BONUS[1]

        # Yakuniy narx
        adjusted = base_price * quality_coef * delay_coef
        final_price = int(adjusted + deadline_bonus)

        return {
            "base_price": base_price,
            "quality_coef": quality_coef,
            "delay_coef": delay_coef,
            "deadline_bonus": deadline_bonus,
            "final_price": final_price,
        }

    @classmethod
    async def get_price_categories(cls) -> list[dict]:
        """Barcha narx kategoriyalarini olish"""
        try:
            response = await notion_service.client.databases.query(
                database_id=config.DB_PRICES,
                sorts=[{"property": "Bazaviy narx UZS", "direction": "ascending"}],
            )
            return response.get("results", [])
        except Exception:
            return []

    @classmethod
    async def get_price_by_id(cls, price_id: str) -> Optional[dict]:
        """Narx kategoriyasini ID bilan olish"""
        try:
            return await notion_service.client.pages.retrieve(page_id=price_id)
        except Exception:
            return None

    @classmethod
    async def create_completed_job(
        cls,
        employee_id: str,
        price_category_id: str,
        base_price: int,
        job_type: str,  # Syomka / Montaj
        job_name: str,
        quality: str = "Orta",
        delay_status: str = "Oz vaqtida",
        days_before_deadline: int = 0,
        project_id: Optional[str] = None,
        client_id: Optional[str] = None,
        link: str = "",
        note: str = "",
    ) -> dict:
        """Yangi bajarilgan ishni Notion'ga yozish (avtomatik narx hisoblash bilan)"""

        # Narxni hisoblaymiz
        calc = cls.calculate_job_price(
            base_price=base_price,
            quality=quality,
            delay_status=delay_status,
            days_before_deadline=days_before_deadline,
        )

        properties = {
            "Ish nomi": {"title": [{"text": {"content": job_name}}]},
            "Xodim": {"relation": [{"id": employee_id}]},
            "Narx kategoriyasi": {"relation": [{"id": price_category_id}]},
            "Tur": {"select": {"name": job_type}},
            "Sana": {"date": {"start": datetime.now().strftime("%Y-%m-%d")}},
            "Bazaviy narx UZS": {"number": calc["base_price"]},
            "Sifat": {"select": {"name": quality}},
            "Sifat koef": {"number": calc["quality_coef"]},
            "Kechikish holati": {"select": {"name": delay_status}},
            "Kechikish koef": {"number": calc["delay_coef"]},
            "Deadline bonus UZS": {"number": calc["deadline_bonus"]},
            "Yakuniy narx UZS": {"number": calc["final_price"]},
        }

        if project_id:
            properties["Loyiha"] = {"relation": [{"id": project_id}]}
        if client_id:
            properties["Mijoz"] = {"relation": [{"id": client_id}]}
        if link:
            properties["Ish havolasi"] = {"url": link}
        if note:
            properties["Izoh"] = {"rich_text": [{"text": {"content": note}}]}

        return await notion_service.client.pages.create(
            parent={"database_id": config.DB_COMPLETED_JOBS},
            properties=properties,
        )

    # ==================== OYLIK HISOB ====================

    @classmethod
    async def calculate_employee_monthly_earnings(
        cls,
        employee_id: str,
        month_start: str,
        month_end: str,
    ) -> dict:
        """
        Xodim uchun oylik daromad hisoblash.
        Bajarilgan ishlar yig'iladi + oylik bonus.
        """
        try:
            response = await notion_service.client.databases.query(
                database_id=config.DB_COMPLETED_JOBS,
                filter={
                    "and": [
                        {
                            "property": "Xodim",
                            "relation": {"contains": employee_id},
                        },
                        {"property": "Sana", "date": {"on_or_after": month_start}},
                        {"property": "Sana", "date": {"on_or_before": month_end}},
                    ]
                },
            )
            jobs = response.get("results", [])
        except Exception:
            return {
                "jobs_count": 0,
                "subtotal": 0,
                "volume_bonus_percent": 0,
                "volume_bonus_uzs": 0,
                "total": 0,
                "by_type": {},
            }

        total_jobs = len(jobs)
        subtotal = 0
        by_type = {"Syomka": {"count": 0, "sum": 0}, "Montaj": {"count": 0, "sum": 0}}

        for job in jobs:
            price = (
                job.get("properties", {})
                .get("Yakuniy narx UZS", {})
                .get("number")
                or 0
            )
            job_type = notion_service._get_select_value(job, "Tur") or "Boshqa"

            subtotal += price
            if job_type in by_type:
                by_type[job_type]["count"] += 1
                by_type[job_type]["sum"] += price

        # Oylik son bonusi
        volume_bonus_percent = 0
        if total_jobs >= 70:
            volume_bonus_percent = 0.15
        elif total_jobs >= 50:
            volume_bonus_percent = 0.10
        elif total_jobs >= 30:
            volume_bonus_percent = 0.05

        volume_bonus_uzs = int(subtotal * volume_bonus_percent)
        total = subtotal + volume_bonus_uzs

        return {
            "jobs_count": total_jobs,
            "subtotal": subtotal,
            "volume_bonus_percent": int(volume_bonus_percent * 100),
            "volume_bonus_uzs": volume_bonus_uzs,
            "total": total,
            "by_type": by_type,
        }

    @classmethod
    async def find_top_performer(
        cls, month_start: str, month_end: str
    ) -> Optional[dict]:
        """
        Oyning eng yaxshi xodimini topish.
        Eng katta daromadli (jami) xodimni qaytaradi.
        """
        employees = await notion_service.get_all_employees()
        if not employees:
            return None

        rankings = []
        for emp in employees:
            earnings = await cls.calculate_employee_monthly_earnings(
                employee_id=emp["id"],
                month_start=month_start,
                month_end=month_end,
            )
            if earnings["jobs_count"] > 0:
                rankings.append((emp, earnings))

        if not rankings:
            return None

        rankings.sort(key=lambda x: x[1]["total"], reverse=True)
        return {
            "employee": rankings[0][0],
            "earnings": rankings[0][1],
        }


# Singleton
payment_service = PaymentService()
