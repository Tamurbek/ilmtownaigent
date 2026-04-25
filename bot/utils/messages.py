"""
Xabar shablonlari - barcha bot xabarlari shu yerda.
O'zgartirmoqchi bo'lsangiz - shu faylda o'zgartiring.
"""

# Loyiha bosqichlari bo'yicha mijozga yuboriladigan xabarlar
STAGE_MESSAGES = {
    "1. Brief olindi": (
        "📥 <b>Brief olindi!</b>\n\n"
        "Sizning buyurtmangiz qabul qilindi. Jamoamiz loyihaga kirishdi. "
        "Tez orada strategiya bosqichiga o'tamiz."
    ),
    "2. Strategiya": (
        "🎯 <b>Strategiya bosqichi</b>\n\n"
        "Sizning loyihangiz uchun kontent strategiyasini ishlab chiqyapmiz. "
        "Auditoriya tahlili va raqobatchilarni o'rganyapmiz."
    ),
    "3. Kontent rejasi": (
        "📋 <b>Kontent rejasi tayyorlanmoqda</b>\n\n"
        "Biz oylik kontent rejasini tuzayapmiz. Tez orada tasdiqlash uchun sizga yuboramiz."
    ),
    "4. Senariy yozilmoqda": (
        "✍️ <b>Senariy yozilmoqda</b>\n\n"
        "Kontent va video uchun senariylar yozilyapti. Ijodiy jamoamiz ishda!"
    ),
    "5. Senariy tasdiqlandi": (
        "✅ <b>Senariy tasdiqlandi!</b>\n\n"
        "Rahmat! Endi s'yomkaga tayyorgarlik ko'rishni boshlaymiz."
    ),
    "6. Syomka tayyorgarligi": (
        "🎬 <b>S'yomkaga tayyorgarlik</b>\n\n"
        "S'yomka uchun barcha kerakli narsalar tayyorlanyapti: lokatsiya, "
        "uskunalar, aktyorlar. Tez orada s'yomka kuni bo'ladi."
    ),
    "7. Syomka qilinmoqda": (
        "🎥 <b>S'yomka boshlandi!</b>\n\n"
        "Ayni paytda sizning kontentingiz uchun s'yomka olinyapti. "
        "Kontent yaqin orada tayyor bo'ladi."
    ),
    "8. Montaj jarayonida": (
        "✂️ <b>Montaj jarayonida</b>\n\n"
        "S'yomka tugadi! Endi montajchilarimiz videolaringizni tahrirlashmoqda. "
        "Rang berish, musiqa, effektlar - hammasi ustida ishlanmoqda."
    ),
    "9. Mijoz korib chiqmoqda": (
        "👀 <b>Siz ko'rib chiqish uchun tayyor!</b>\n\n"
        "Kontent tayyor bo'ldi. Iltimos, uni ko'rib chiqing va fikringizni bildiring. "
        "Agar o'zgartirish kerak bo'lsa, ayting - tahrir kiritamiz."
    ),
    "10. Tahrir kiritilmoqda": (
        "🔧 <b>Tahrir kiritilmoqda</b>\n\n"
        "Sizning izohlaringiz asosida tahrirlar kiritilyapti. Tez orada yakuniy "
        "variantni taqdim etamiz."
    ),
    "11. Nashrga tayyor": (
        "🚀 <b>Nashrga tayyor!</b>\n\n"
        "Kontent tasdiqlandi va nashr qilishga tayyor. Rejadagi sanada e'lon qilinadi."
    ),
    "12. Nashr qilindi": (
        "🎉 <b>Nashr qilindi!</b>\n\n"
        "Tabriklaymiz! Kontent muvaffaqiyatli e'lon qilindi. Natijalarni "
        "kuzatib, haftalik hisobotda sizga yuboramiz."
    ),
}


# Salomlashish xabarlari
WELCOME_PRIVATE = (
    "👋 <b>Assalomu alaykum!</b>\n\n"
    "Men <b>Biznestown Agency</b> boti man. Sizga quyidagilarda yordam beraman:\n\n"
    "📋 /vazifalarim — mening faol vazifalarim\n"
    "📊 /hisobot — kunlik hisobot topshirish\n"
    "💼 /loyihalarim — men boshqarayotgan loyihalar\n"
    "ℹ️ /help — yordam\n\n"
    "<i>Agar siz xodim bo'lsangiz, ID raqamingizni Notion'dagi Xodimlar bazasiga qo'shish kerak.</i>"
)

WELCOME_GROUP = (
    "👋 <b>Salom, hurmatli mijoz!</b>\n\n"
    "Bu guruhda sizning loyihangiz bo'yicha barcha yangiliklar avtomatik yuboriladi:\n"
    "🎬 Senariy tayyorlandi\n"
    "📹 S'yomka boshlandi\n"
    "✂️ Montaj jarayonida\n"
    "✅ Nashrga tayyor\n\n"
    "<b>Foydali buyruqlar:</b>\n"
    "/status — loyihamning hozirgi holati\n"
    "/brief — yangi brief to'ldirish\n"
    "/help — yordam"
)

HELP_TEXT = (
    "ℹ️ <b>Bot yordamchisi</b>\n\n"
    "<b>🧑‍💼 Xodimlar uchun:</b>\n"
    "🟢 /keldim — ish boshlash (kelganlikni qayd qilish)\n"
    "🔴 /ketdim — ish tugatish\n"
    "📅 /davomat — bugungi davomatim\n"
    "📋 /vazifalarim — faol vazifalar (✅ Bajarildi tugmasi bilan)\n"
    "📦 /ish_qosh — bajarilgan ishni qo'shish (operator/montajchi)\n"
    "💰 /mening_daromadim — joriy oylik daromadim\n"
    "📊 /hisobot — kunlik hisobot topshirish\n"
    "💼 /loyihalarim — boshqarayotgan loyihalar\n"
    "⭐ /mening_kpim — joriy oylik KPI bahom\n\n"
    "<b>👤 Mijozlar uchun (guruhda):</b>\n"
    "📍 /status — loyihamning holati\n"
    "📝 /brief — yangi brief to'ldirish\n\n"
    "<b>🔑 Direktor uchun:</b>\n"
    "🤖 /avtomatik_vazifa — bot avtomatik xodim tanlaydi\n"
    "➕ /vazifa_ber — qo'lda xodim tanlab vazifa berish\n"
    "📊 /statistika — bugungi statistika\n"
    "⭐ /kpi_hisob — barcha xodimlarga oylik KPI\n"
    "⚠️ /intizom — intizomiy choralar ro'yxati\n"
    "🎯 /mijozlar — mijozlar ro'yxati\n"
    "💼 /loyihalar — barcha loyihalar\n"
    "👥 /xodimlar — xodimlar ro'yxati\n\n"
    "Savollar uchun direktorga murojaat qiling."
)


# Brief savollari
BRIEF_QUESTIONS = [
    ("name", "1️⃣ Kompaniyangiz nomi?"),
    ("company", "2️⃣ Faoliyat sohangiz?"),
    ("contact", "3️⃣ Aloqa uchun shaxs (F.I.O)?"),
    ("phone", "4️⃣ Telefon raqamingiz?"),
    ("goals", "5️⃣ SMM'dan qanday natija kutyapsiz?"),
    ("audience", "6️⃣ Sizning mijozingiz kim? (yosh, jins, qiziqishlar)"),
    ("platforms", "7️⃣ Qaysi platformalarda bo'lish kerak? (Instagram, Telegram, TikTok...)"),
    ("budget", "8️⃣ Oylik byudjet? (USD yoki UZS)"),
    ("notes", "9️⃣ Qo'shimcha izohlaringiz?"),
]


# Emoji va formatlar
def format_task(task_name: str, deadline: str, priority: str, project: str = "") -> str:
    """Bitta vazifani formatlash"""
    priority_emoji = {
        "Shoshilinch": "🔴",
        "Yuqori": "🟠",
        "Orta": "🟡",
        "Past": "⚪",
    }.get(priority, "⚪")

    text = f"{priority_emoji} <b>{task_name}</b>\n"
    if deadline:
        text += f"   📅 Muddat: {deadline}\n"
    if project:
        text += f"   💼 Loyiha: {project}\n"
    return text


def format_task_reminder(task_name: str, deadline: str, project: str = "") -> str:
    """Vazifa eslatmasi xabari"""
    text = (
        "⏰ <b>Vazifa muddati yaqinlashdi!</b>\n\n"
        f"📌 <b>{task_name}</b>\n"
        f"🕒 Muddat: {deadline}\n"
    )
    if project:
        text += f"💼 Loyiha: {project}\n"
    text += "\n<i>Iltimos, vazifani bajarishga kirishing!</i>"
    return text


def format_daily_report(stats: dict) -> str:
    """Kunlik hisobotni formatlash"""
    text = "📊 <b>Biznestown Agency — Kunlik hisobot</b>\n\n"

    text += f"💼 <b>Faol loyihalar:</b> {stats['active_projects']} ta\n"

    if stats.get("stages"):
        text += "\n<b>📈 Bosqichlar bo'yicha:</b>\n"
        for stage, count in sorted(stats["stages"].items()):
            text += f"  • {stage}: {count} ta\n"

    text += f"\n✅ <b>Faol vazifalar:</b> {stats['active_tasks']} ta\n"
    text += f"🔴 <b>Shoshilinch vazifalar:</b> {stats['urgent_tasks']} ta\n"
    text += f"🎯 <b>Bu haftadagi yangi mijozlar:</b> {stats['new_clients_this_week']} ta\n"

    return text
