"""
Avtomatik vazifalar (scheduler):
1. Har 30 daqiqada - vazifa eslatmalarini tekshirish
2. Har kuni 09:00 - direktor guruhiga kunlik hisobot
3. Har 5 daqiqada - loyiha bosqichi o'zgargan-o'zgarmaganini tekshirish

APScheduler kutubxonasi ishlatiladi.
"""
import logging
from datetime import datetime
from typing import Optional

import pytz
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from bot.config import config
from bot.services.notion_service import notion_service
from bot.utils.messages import (
    format_task_reminder,
    format_daily_report,
    STAGE_MESSAGES,
)

logger = logging.getLogger(__name__)

# Loyiha bosqichlarini xotirada saqlash uchun (oxirgi holat)
# Keyinchalik bunga database yoki fayl qo'shish mumkin
_project_stages_cache: dict[str, str] = {}


class BotScheduler:
    """Bot uchun avtomatik vazifalar"""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.tz = pytz.timezone(config.TIMEZONE)
        self.scheduler = AsyncIOScheduler(timezone=self.tz)

    def start(self):
        """Schedulerni ishga tushirish"""
        # 1. Vazifa eslatmalari - har 30 daqiqada
        self.scheduler.add_job(
            self.check_task_reminders,
            IntervalTrigger(
                minutes=config.REMINDER_CHECK_INTERVAL_MINUTES, timezone=self.tz
            ),
            id="task_reminders",
            name="Vazifa eslatmalari",
            replace_existing=True,
        )

        # 2. Kunlik hisobot - har kuni 09:00
        hour, minute = config.DAILY_REPORT_TIME.split(":")
        self.scheduler.add_job(
            self.send_daily_report,
            CronTrigger(hour=int(hour), minute=int(minute), timezone=self.tz),
            id="daily_report",
            name="Kunlik hisobot",
            replace_existing=True,
        )

        # 3. Loyiha bosqich o'zgarishlarini kuzatish - har 5 daqiqada
        self.scheduler.add_job(
            self.check_project_stage_changes,
            IntervalTrigger(minutes=5, timezone=self.tz),
            id="project_stages",
            name="Loyiha bosqich o'zgarishlari",
            replace_existing=True,
        )

        # 4. Davomat eslatmasi
        work_hour, work_minute = config.WORK_START_TIME.split(":")
        reminder_minute = (int(work_minute) + 30) % 60
        reminder_hour = int(work_hour) + (int(work_minute) + 30) // 60

        self.scheduler.add_job(
            self.check_check_in_reminders,
            CronTrigger(
                hour=reminder_hour, minute=reminder_minute, timezone=self.tz
            ),
            id="check_in_reminders",
            name="Kelmagan xodimlarga eslatma",
            replace_existing=True,
        )

        # 5. Ish kuni oxirida ketdim qilmaganlar
        end_hour, end_minute = config.WORK_END_TIME.split(":")
        end_reminder_hour = (int(end_hour) + 1) % 24

        self.scheduler.add_job(
            self.check_check_out_reminders,
            CronTrigger(
                hour=end_reminder_hour,
                minute=int(end_minute),
                timezone=self.tz,
            ),
            id="check_out_reminders",
            name="Ketdim qilmaganlarga eslatma",
            replace_existing=True,
        )

        # 6. Kontent plan kechikishini tekshirish - har kuni 21:00 da
        self.scheduler.add_job(
            self.check_content_plan_delays,
            CronTrigger(hour=21, minute=0, timezone=self.tz),
            id="content_plan_delays",
            name="Kontent plan kechikishlarini tekshirish",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info("✅ Scheduler ishga tushdi")
        logger.info(f"   • Vazifa eslatmalari: har {config.REMINDER_CHECK_INTERVAL_MINUTES} daqiqada")
        logger.info(f"   • Kunlik hisobot: {config.DAILY_REPORT_TIME}")
        logger.info("   • Loyiha bosqich tekshiruvi: har 5 daqiqada")
        logger.info(f"   • Kelmaganlar eslatmasi: {reminder_hour:02d}:{reminder_minute:02d}")
        logger.info(f"   • Ketmaganlar eslatmasi: {end_reminder_hour:02d}:{int(end_minute):02d}")
        logger.info("   • Kontent kechikishi: har kuni 21:00")

    def stop(self):
        """Schedulerni to'xtatish"""
        self.scheduler.shutdown()
        logger.info("Scheduler to'xtatildi")

    # ==================== 1. VAZIFA ESLATMALARI ====================

    async def check_task_reminders(self):
        """Muddati yaqinlashgan vazifalarni topib, xodimga xabar yuborish"""
        logger.info("🔔 Vazifa eslatmalarini tekshirmoqda...")

        try:
            tasks = await notion_service.get_upcoming_tasks(hours_ahead=24)
            logger.info(f"   {len(tasks)} ta vazifa topildi")

            sent_count = 0
            for task in tasks:
                await self._send_task_reminder(task)
                sent_count += 1

            if sent_count > 0:
                logger.info(f"   ✅ {sent_count} ta eslatma yuborildi")
        except Exception as e:
            logger.error(f"❌ Eslatma tekshirishda xatolik: {e}")

    async def _send_task_reminder(self, task: dict):
        """Bitta vazifa bo'yicha xodimga eslatma yuborish"""
        try:
            # Vazifa ma'lumotlari
            task_name = notion_service._get_title(task)
            deadline = notion_service._get_date(task, "Muddat") or "Belgilanmagan"
            employee_ids = notion_service._get_relation_ids(task, "Masul xodim")

            if not employee_ids:
                return

            # Loyiha nomini olish
            project_ids = notion_service._get_relation_ids(task, "Loyiha")
            project_name = ""
            if project_ids:
                project = await notion_service.get_project_by_id(project_ids[0])
                if project:
                    project_name = notion_service._get_title(project)

            # Har bir mas'ul xodimga xabar yuborish
            for emp_id in employee_ids:
                try:
                    employee = await notion_service.client.pages.retrieve(page_id=emp_id)
                    telegram_id = notion_service._get_rich_text(employee, "Telegram ID")

                    if not telegram_id:
                        logger.warning(
                            f"   ⚠️ Xodimda Telegram ID yo'q: {notion_service._get_title(employee)}"
                        )
                        continue

                    text = format_task_reminder(task_name, deadline, project_name)
                    await self.bot.send_message(chat_id=int(telegram_id), text=text)

                except Exception as e:
                    logger.error(f"   Xodimga xabar yuborib bo'lmadi: {e}")

            # Notion'ga "eslatma yuborilgan" belgisini qo'yamiz
            await notion_service.mark_task_reminder_sent(task["id"])

        except Exception as e:
            logger.error(f"Vazifa eslatmasida xatolik: {e}")

    # ==================== 2. KUNLIK HISOBOT ====================

    async def send_daily_report(self):
        """Direktor guruhiga kunlik hisobot yuborish"""
        logger.info("📊 Kunlik hisobot yuborilmoqda...")

        if not config.ADMIN_GROUP_ID:
            logger.warning("ADMIN_GROUP_ID sozlanmagan")
            return

        try:
            stats = await notion_service.get_daily_stats()
            text = format_daily_report(stats)

            # Direktor guruhiga yuborish
            await self.bot.send_message(chat_id=config.ADMIN_GROUP_ID, text=text)

            # Direktorga shaxsiy xabar ham
            if config.ADMIN_TELEGRAM_ID:
                await self.bot.send_message(
                    chat_id=config.ADMIN_TELEGRAM_ID, text=text
                )

            logger.info("   ✅ Kunlik hisobot yuborildi")
        except Exception as e:
            logger.error(f"❌ Kunlik hisobot yuborishda xatolik: {e}")

    # ==================== 3. LOYIHA BOSQICH O'ZGARISHLARI ====================

    async def check_project_stage_changes(self):
        """
        Loyihalarning bosqichi o'zgarganini tekshirib, mijozga xabar yuborish.

        Birinchi marta ishga tushganda barcha loyihalarning bosqichlarini
        xotiraga oladi. Keyingi tekshiruvlarda agar bosqich o'zgargan bo'lsa,
        mijozga xabar yuboradi.
        """
        global _project_stages_cache

        try:
            projects = await notion_service.get_active_projects()

            for project in projects:
                project_id = project["id"]
                current_stage = notion_service._get_select_value(project, "Bosqich")

                if not current_stage:
                    continue

                previous_stage = _project_stages_cache.get(project_id)

                # Birinchi marta - faqat xotiraga yozamiz
                if previous_stage is None:
                    _project_stages_cache[project_id] = current_stage
                    continue

                # Bosqich o'zgardi - mijozga xabar yuboramiz
                if current_stage != previous_stage:
                    await self._notify_client_stage_change(project, current_stage)
                    _project_stages_cache[project_id] = current_stage

        except Exception as e:
            logger.error(f"❌ Loyiha bosqich tekshiruvida xatolik: {e}")

    async def _notify_client_stage_change(self, project: dict, new_stage: str):
        """Mijozning Telegram guruhiga loyiha bosqichi o'zgarganligi haqida xabar"""
        try:
            project_name = notion_service._get_title(project)
            client_ids = notion_service._get_relation_ids(project, "Mijoz")

            if not client_ids:
                return

            for client_id in client_ids:
                client = await notion_service.client.pages.retrieve(page_id=client_id)
                group_id = notion_service._get_rich_text(client, "Telegram guruh ID")

                if not group_id:
                    client_name = notion_service._get_title(client)
                    logger.warning(f"   ⚠️ Mijozda guruh ID yo'q: {client_name}")
                    continue

                # Bosqich uchun xabar matnini olamiz
                stage_message = STAGE_MESSAGES.get(new_stage)
                if not stage_message:
                    stage_message = f"📍 Loyiha yangi bosqichga o'tdi: <b>{new_stage}</b>"

                full_message = (
                    f"💼 <b>Loyiha: {project_name}</b>\n\n{stage_message}"
                )

                try:
                    await self.bot.send_message(
                        chat_id=int(group_id), text=full_message
                    )
                    logger.info(
                        f"   ✅ Mijozga xabar yuborildi: {project_name} → {new_stage}"
                    )
                except Exception as e:
                    logger.error(
                        f"   Mijoz guruhiga xabar yuborib bo'lmadi ({group_id}): {e}"
                    )

        except Exception as e:
            logger.error(f"Loyiha bosqich xabarida xatolik: {e}")

    # ==================== 4. KELMAGAN XODIMLARGA ESLATMA ====================

    async def check_check_in_reminders(self):
        """
        Ish vaqti boshlanganidan 30 daqiqa o'tgan, lekin 'Keldim'
        qilmagan xodimlarga eslatma yuborish.
        """
        from datetime import datetime as dt
        logger.info("🔔 Kelmagan xodimlarni tekshirmoqda...")

        try:
            employees = await notion_service.get_all_employees()
            reminded_count = 0
            absent_employees = []

            for employee in employees:
                emp_id = employee["id"]
                emp_name = notion_service._get_title(employee)
                tg_id = notion_service._get_rich_text(employee, "Telegram ID")

                if not tg_id:
                    continue

                # Bugun keldim qilganmi?
                check_ins = await notion_service.get_today_attendance(
                    emp_id, record_type="Kelish"
                )

                if not check_ins:
                    # Eslatma yuboramiz
                    try:
                        await self.bot.send_message(
                            chat_id=int(tg_id),
                            text=(
                                "⏰ <b>Eslatma!</b>\n\n"
                                "Siz hali ish boshlaganingizni qayd etmagansiz.\n"
                                "Ishga kelgan bo'lsangiz, /keldim ni bosing.\n\n"
                                "Agar bugun ish kuningiz bo'lmasa "
                                "(ta'til, dam olish), e'tiborsiz qoldiring."
                            ),
                        )
                        reminded_count += 1
                        absent_employees.append(emp_name)
                    except Exception as e:
                        logger.error(f"   Xodimga ({emp_name}) xabar: {e}")

            # Direktorga umumiy hisobot
            if absent_employees and config.ADMIN_TELEGRAM_ID:
                text = "⚠️ <b>Hali kelmaganlar:</b>\n\n"
                for name in absent_employees:
                    text += f"• {name}\n"
                try:
                    await self.bot.send_message(
                        chat_id=config.ADMIN_TELEGRAM_ID, text=text
                    )
                except Exception:
                    pass

            logger.info(f"   {reminded_count} ta xodimga eslatma yuborildi")

        except Exception as e:
            logger.error(f"❌ Davomat eslatmasida xatolik: {e}")

    # ==================== 5. KETMAGAN XODIMLARGA ESLATMA ====================

    async def check_check_out_reminders(self):
        """
        Ish kuni tugagan, lekin 'Ketdim' qilmagan xodimlarga eslatma.
        """
        logger.info("🔔 Ketmagan xodimlarni tekshirmoqda...")

        try:
            employees = await notion_service.get_all_employees()
            reminded_count = 0

            for employee in employees:
                emp_id = employee["id"]
                emp_name = notion_service._get_title(employee)
                tg_id = notion_service._get_rich_text(employee, "Telegram ID")

                if not tg_id:
                    continue

                # Bugun keldim qilganmi?
                check_ins = await notion_service.get_today_attendance(
                    emp_id, record_type="Kelish"
                )
                if not check_ins:
                    continue  # Bugun kelmagan, eslatma kerak emas

                # Ketdim qilganmi?
                check_outs = await notion_service.get_today_attendance(
                    emp_id, record_type="Ketish"
                )
                if check_outs:
                    continue  # Ketdim qilgan

                # Eslatma yuboramiz
                try:
                    await self.bot.send_message(
                        chat_id=int(tg_id),
                        text=(
                            "🔔 <b>Eslatma!</b>\n\n"
                            "Ish kuni yakunlandi, lekin siz ketganligingizni "
                            "qayd etmagansiz.\n\n"
                            "Iltimos, /ketdim ni bosing."
                        ),
                    )
                    reminded_count += 1
                except Exception as e:
                    logger.error(f"   Xodimga ({emp_name}) xabar: {e}")

            logger.info(f"   {reminded_count} ta xodimga ketdim eslatmasi")

        except Exception as e:
            logger.error(f"❌ Ketdim eslatmasida xatolik: {e}")

    # ==================== 6. KONTENT PLAN KECHIKISHLARI ====================

    async def check_content_plan_delays(self):
        """
        Har kuni 21:00 da kontent plan kechikishlarini tekshirish.
        - Bugun nashr qilinishi kerak edi-yu, hali "Nashr qilindi" emas → kechikish
        - 1 kun: SMM menejerga xabar
        - 3+ kun: direktorga xabar
        """
        from datetime import datetime as dt
        logger.info("📋 Kontent plan kechikishlari tekshirilmoqda...")

        try:
            today = dt.now().strftime("%Y-%m-%d")

            # Sanasi bugun yoki o'tib ketgan, lekin "Nashr qilindi" bo'lmagan postlar
            response = await notion_service.client.databases.query(
                database_id=config.DB_CONTENT_PLAN,
                filter={
                    "and": [
                        {
                            "property": "Sana",
                            "date": {"on_or_before": today},
                        },
                        {
                            "property": "Holat",
                            "select": {"does_not_equal": "Nashr qilindi"},
                        },
                        {
                            "property": "Holat",
                            "select": {"does_not_equal": "Bekor qilindi"},
                        },
                    ]
                },
            )
            delayed_posts = response.get("results", [])

            if not delayed_posts:
                logger.info("   ✅ Kechikkan postlar yo'q")
                return

            logger.info(f"   {len(delayed_posts)} ta kechikkan post topildi")

            # SMM menejerlarni topish
            from bot.services.assignment_service import assignment_service
            smm_managers = await assignment_service.find_smm_managers()

            posts_for_smm = []  # 1+ kun kechikkan
            posts_for_director = []  # 3+ kun kechikkan

            for post in delayed_posts:
                post_name = notion_service._get_title(post)
                planned_date = notion_service._get_date(post, "Sana")

                if not planned_date:
                    continue

                # Kechikish kunini hisoblaymiz
                try:
                    planned = dt.strptime(planned_date, "%Y-%m-%d")
                    delay_days = (dt.now() - planned).days
                    if delay_days < 0:
                        continue  # kelajakdagi sana
                except Exception:
                    continue

                # Notion'da kechikish kun va holatni yangilaymiz
                try:
                    update_props = {
                        "Kechikish kun": {"number": delay_days},
                    }
                    # Holatni "Kechikdi" ga o'tkazamiz (agar hali nashr qilinmagan bo'lsa)
                    current_status = notion_service._get_select_value(
                        post, "Holat"
                    )
                    if current_status not in ["Kechikdi", "Bekor qilindi"]:
                        update_props["Holat"] = {
                            "select": {"name": "Kechikdi"}
                        }

                    await notion_service.client.pages.update(
                        page_id=post["id"],
                        properties=update_props,
                    )
                except Exception as e:
                    logger.error(f"   Postni yangilab bo'lmadi: {e}")

                post_info = {
                    "name": post_name,
                    "delay": delay_days,
                    "planned": planned_date,
                }

                # 1+ kun kechikkan → SMM ga
                if delay_days >= 1:
                    posts_for_smm.append(post_info)

                # 3+ kun kechikkan → direktor ga (avval xabar yuborilmagan bo'lsa)
                already_notified = (
                    post.get("properties", {})
                    .get("Direktor xabardor", {})
                    .get("checkbox", False)
                )
                if delay_days >= 3 and not already_notified:
                    posts_for_director.append(post_info)
                    # Belgilab qo'yamiz
                    try:
                        await notion_service.client.pages.update(
                            page_id=post["id"],
                            properties={
                                "Direktor xabardor": {"checkbox": True}
                            },
                        )
                    except Exception:
                        pass

            # SMM menejerlarga xabar
            if posts_for_smm and smm_managers:
                smm_text = (
                    f"⏰ <b>Kontent plan — kechikishlar</b>\n\n"
                    f"Bugun ({today}) gacha nashr qilinishi kerak edi:\n\n"
                )
                for p in posts_for_smm[:15]:
                    smm_text += (
                        f"🟡 <b>{p['name']}</b>\n"
                        f"   📅 Reja: {p['planned']}\n"
                        f"   ⏱ Kechikish: {p['delay']} kun\n\n"
                    )

                for smm in smm_managers:
                    smm_tg = notion_service._get_rich_text(smm, "Telegram ID")
                    if smm_tg:
                        try:
                            await self.bot.send_message(
                                chat_id=int(smm_tg), text=smm_text
                            )
                        except Exception as e:
                            logger.error(f"   SMM ga xabar: {e}")

            # Direktorga xabar (3+ kun kechikkanlar)
            if posts_for_director and config.ADMIN_TELEGRAM_ID:
                dir_text = (
                    f"🚨 <b>JIDDIY KECHIKISH — direktor diqqati!</b>\n\n"
                    f"Quyidagi postlar 3+ kun kechikdi:\n\n"
                )
                for p in posts_for_director:
                    dir_text += (
                        f"🔴 <b>{p['name']}</b>\n"
                        f"   📅 Reja: {p['planned']}\n"
                        f"   ⏱ Kechikish: <b>{p['delay']} kun</b>\n\n"
                    )

                dir_text += (
                    "\n<i>SMM menejerlarga ham xabar berildi. "
                    "Iltimos, sabablarini aniqlang.</i>"
                )

                try:
                    await self.bot.send_message(
                        chat_id=config.ADMIN_TELEGRAM_ID, text=dir_text
                    )
                except Exception as e:
                    logger.error(f"   Direktor ga xabar: {e}")

            logger.info(
                f"   ✅ {len(posts_for_smm)} ta SMM ga, "
                f"{len(posts_for_director)} ta direktorga xabar yuborildi"
            )

        except Exception as e:
            logger.error(f"❌ Kontent plan tekshiruvida xatolik: {e}")


def setup_scheduler(bot: Bot) -> BotScheduler:
    """Schedulerni sozlash va ishga tushirish"""
    scheduler = BotScheduler(bot)
    scheduler.start()
    return scheduler
