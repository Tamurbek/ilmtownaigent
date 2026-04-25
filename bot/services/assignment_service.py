"""
Avtomatik vazifa taqsimlash algoritmi.

Vazifani eng mos xodimga taqsimlaydi quyidagi kriteriylar bo'yicha:
1. Xodim "Qila oladigan ishlar" da kerakli ko'nikma bormi?
2. Xodim "Daraja" si kerakli darajadan past emasmi?
3. Xodim "Holati" "Ishlayapti" mi? (ta'tilda yoki bemor emas)
4. Xodim "Bandlik darajasi" qanday? (Bo'sh > O'rta band > To'liq band)
5. Xodimda hozir nechta faol vazifa bor (kam bo'lganini afzal ko'ramiz)

Daraja tartibi: Boshlovchi < Orta < Tajribali < Ekspert
"""
from typing import Optional
from bot.config import config
from bot.services.notion_service import notion_service


# Daraja tartibi (raqam yuqori = malakali)
LEVEL_RANK = {
    "Boshlovchi": 1,
    "Orta": 2,
    "Tajribali": 3,
    "Ekspert": 4,
    "Har qanday": 0,  # vazifaning kerakli darajasi sifatida
}

# Bandlik bo'yicha ball (yuqori = afzal)
BUSY_RANK = {
    "Bosh": 100,
    "Orta band": 50,
    "Toliq band": 10,
    "Taotil": 0,
    None: 75,  # belgilanmagan = o'rtacha
}


class AssignmentService:
    """Vazifani avtomatik taqsimlash xizmati"""

    @staticmethod
    def _get_employee_skills(employee: dict) -> list[str]:
        """Xodimning ko'nikmalar ro'yxatini olish"""
        prop = employee.get("properties", {}).get("Qila oladigan ishlar", {})
        items = prop.get("multi_select", [])
        return [item.get("name") for item in items]

    @staticmethod
    def _get_employee_level(employee: dict) -> str:
        """Xodim darajasi"""
        return (
            notion_service._get_select_value(employee, "Daraja")
            or "Boshlovchi"
        )

    @staticmethod
    def _get_employee_status(employee: dict) -> str:
        """Xodim holati (Ishlayapti / Ta'tilda / Bemor / Ishdan ketdi)"""
        return notion_service._get_select_value(employee, "Holati") or ""

    @staticmethod
    def _get_employee_busy_level(employee: dict) -> Optional[str]:
        """Xodim bandlik darajasi"""
        return notion_service._get_select_value(employee, "Bandlik darajasi")

    @classmethod
    async def find_best_employee(
        cls,
        required_skill: str,
        required_level: str = "Har qanday",
    ) -> Optional[dict]:
        """
        Eng mos xodimni topish.

        Args:
            required_skill: kerakli ko'nikma (masalan "Reels montaj")
            required_level: kerakli daraja (masalan "Tajribali")

        Returns:
            Eng mos xodim sahifasi yoki None (mos xodim topilmasa)
        """
        # Barcha ishlayotgan xodimlarni olamiz
        employees = await notion_service.get_all_employees()
        if not employees:
            return None

        # Mos keluvchilarni filterlash
        candidates = []
        required_level_rank = LEVEL_RANK.get(required_level, 0)

        for emp in employees:
            # 1-tekshiruv: Holati "Ishlayapti" bo'lishi kerak
            status = cls._get_employee_status(emp)
            if status != "Ishlayapti":
                continue

            # 2-tekshiruv: Ko'nikma bormi
            skills = cls._get_employee_skills(emp)
            if required_skill not in skills:
                continue

            # 3-tekshiruv: Darajasi yetarlimi
            emp_level = cls._get_employee_level(emp)
            emp_level_rank = LEVEL_RANK.get(emp_level, 1)

            if emp_level_rank < required_level_rank:
                continue  # darajasi past

            # 4-tekshiruv: Toliq band emasmi?
            busy = cls._get_employee_busy_level(emp)
            if busy in ["Toliq band", "Taotil"]:
                continue  # ishlay olmaydi

            # Bu xodim mos! Endi ball hisoblaymiz
            score = await cls._calculate_score(emp, required_level_rank)
            candidates.append((emp, score))

        if not candidates:
            return None

        # Eng yuqori ballga ega bo'lganini tanlaymiz
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    @classmethod
    async def _calculate_score(cls, employee: dict, required_level_rank: int) -> int:
        """
        Xodim uchun ball hisoblash.

        Yuqori ball = afzalroq xodim:
        - Bo'sh xodim afzal (band emas)
        - Vazifa kam bo'lganlar afzal
        - Aniq darajaga mos kelganlar afzal (haddan tashqari malakali emas)
        """
        score = 0

        # 1. Bandlik darajasi (max +100)
        busy = cls._get_employee_busy_level(employee)
        score += BUSY_RANK.get(busy, 75)

        # 2. Hozirgi vazifalar soni (kam = afzal)
        current_tasks = await cls._count_active_tasks(employee["id"])
        # Har bir faol vazifa uchun -10 ball
        score -= current_tasks * 10

        # 3. Daraja moslik (haddan tashqari malakali emas, lekin yetarli)
        # Kerakli daraja = 2 (Orta), xodim = 4 (Ekspert) bo'lsa, farq = 2
        # Ekspert har doim mos, lekin Orta darajadagi vazifa uchun
        # Tajribali (farq 1) ham, Orta (farq 0) ham mos
        emp_level = cls._get_employee_level(employee)
        emp_level_rank = LEVEL_RANK.get(emp_level, 1)
        level_gap = emp_level_rank - required_level_rank

        # Aniq mos kelganga +20, har bir ortiqcha daraja uchun -5
        if level_gap == 0:
            score += 20
        else:
            score -= level_gap * 5

        return score

    @staticmethod
    async def _count_active_tasks(employee_id: str) -> int:
        """Xodimning faol vazifalar sonini hisoblash"""
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
                    ]
                },
            )
            return len(response.get("results", []))
        except Exception:
            return 0

    @classmethod
    async def find_pm(cls) -> Optional[dict]:
        """
        PM (Project Manager) xodimini topish.
        "PM hisoblanadi" checkbox belgilangan birinchi xodim.
        """
        try:
            response = await notion_service.client.databases.query(
                database_id=config.DB_EMPLOYEES,
                filter={
                    "and": [
                        {
                            "property": "PM hisoblanadi",
                            "checkbox": {"equals": True},
                        },
                        {
                            "property": "Holati",
                            "select": {"equals": "Ishlayapti"},
                        },
                    ]
                },
            )
            results = response.get("results", [])
            return results[0] if results else None
        except Exception:
            return None

    @classmethod
    async def find_smm_managers(cls) -> list[dict]:
        """SMM menejerlarni topish (vazifani tasdiqlovchilar)"""
        try:
            response = await notion_service.client.databases.query(
                database_id=config.DB_EMPLOYEES,
                filter={
                    "and": [
                        {
                            "property": "Lavozim",
                            "multi_select": {"contains": "SMM Menejer"},
                        },
                        {
                            "property": "Holati",
                            "select": {"equals": "Ishlayapti"},
                        },
                    ]
                },
            )
            return response.get("results", [])
        except Exception:
            return []


# Singleton
assignment_service = AssignmentService()
