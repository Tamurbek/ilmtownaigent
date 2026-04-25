# 🤖 Biznestown Agency Telegram Bot

SMM agentligi uchun Notion bilan to'liq integratsiyalangan Telegram bot.

## 🎯 Imkoniyatlar

1. **🔔 Avtomatik vazifa eslatmalari** — Notion'dagi vazifa muddati yaqinlashganda xodimga Telegram orqali xabar yuboradi
2. **📥 Mijozdan brief olish** — bot orqali mijoz savol-javob tariqasida o'z ma'lumotlarini kiritadi, natija Notion'ga yoziladi
3. **📊 Kunlik va haftalik hisobotlar** — har kuni/hafta direktor guruhiga avtomatik statistika
4. **👷 Xodim hisobotlari** — xodimlar bot orqali kunlik hisobot topshiradi, Notion'ga yoziladi
5. **🎬 Mijozga loyiha bosqichlari** — Notion'da loyiha bosqichi o'zgarganda mijozning Telegram guruhiga avtomatik xabar

## 📋 O'rnatish

### 1. Talablar
- Python 3.10+
- Notion integratsiya token
- Telegram bot token

### 2. Notion integratsiya yaratish
1. [notion.so/my-integrations](https://www.notion.so/my-integrations) ga o'ting
2. "New integration" bosing
3. Nom: `Biznestown Bot`, ruxsat turi: `Internal`
4. `Internal Integration Token` ni nusxalang → `.env` ga qo'ying
5. Biznestown Agency HQ sahifasini oching
6. O'ng yuqorida `···` → `Connections` → `Biznestown Bot` ni ulang

### 3. Ishga tushirish

```bash
# Repozitoriyni yuklash
cd biznestown_bot

# Virtual environment yaratish
python -m venv venv
source venv/bin/activate   # Linux/Mac
# yoki
venv\Scripts\activate      # Windows

# Kutubxonalarni o'rnatish
pip install -r requirements.txt

# .env faylni sozlash (env.example'dan nusxa oling)
cp env.example .env
# .env faylni ochib ma'lumotlaringizni kiriting

# Botni ishga tushirish
python -m bot.main
```

## 🚀 Deploy qilish

### Railway.app (bepul, eng oson)
1. [railway.app](https://railway.app) ga ro'yxatdan o'ting
2. "New Project" → "Deploy from GitHub repo"
3. Environment Variables bo'limiga `.env`dagi barcha o'zgaruvchilarni qo'shing
4. Deploy — bot 24/7 ishlaydi

### VPS (DigitalOcean, Hetzner, Timeweb)
```bash
# Server'da
git clone <your-repo>
cd biznestown_bot
pip install -r requirements.txt
# .env faylni tayyorlang
# systemd service yarating (quyida)
```

systemd service fayli: `/etc/systemd/system/biznestown-bot.service`
```ini
[Unit]
Description=Biznestown Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/biznestown_bot
ExecStart=/usr/bin/python3 -m bot.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Keyin:
```bash
systemctl enable biznestown-bot
systemctl start biznestown-bot
systemctl status biznestown-bot
```

## 📂 Loyiha tuzilmasi

```
biznestown_bot/
├── bot/
│   ├── main.py              # Asosiy kirish nuqtasi
│   ├── config.py            # Sozlamalar (.env dan o'qiydi)
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── start.py         # /start, /help buyruqlari
│   │   ├── employee.py      # Xodim buyruqlari (hisobot berish)
│   │   ├── client_brief.py  # Mijozdan brief olish
│   │   └── admin.py         # Direktor buyruqlari
│   ├── services/
│   │   ├── __init__.py
│   │   ├── notion_service.py    # Notion API bilan ishlash
│   │   └── scheduler.py         # Avtomatik vazifalar (eslatmalar, hisobotlar)
│   └── utils/
│       ├── __init__.py
│       ├── keyboards.py     # Telegram tugmalar
│       └── messages.py      # Xabar shablonlari
├── requirements.txt
├── .env.example
└── README.md
```

## 🔧 Bot buyruqlari

### Hamma uchun
- `/start` — botni boshlash
- `/help` — yordam

### Xodimlar uchun
- `/vazifalarim` — mening faol vazifalarim
- `/hisobot` — kunlik hisobot topshirish
- `/loyihalarim` — men boshqarayotgan loyihalar

### Direktor uchun
- `/statistika` — bugungi statistika
- `/hafta_hisoboti` — haftalik umumiy hisobot
- `/mijozlar` — mijozlar ro'yxati

### Mijozlar uchun (guruhida)
- `/brief` — brief to'ldirish
- `/status` — loyiham qaysi bosqichda

## ⚠️ Xavfsizlik

- `.env` faylni HECH QACHON Git'ga yuklamang (`.gitignore`da bor)
- Bot tokenini hech kimga bermang
- Notion integratsiyasiga faqat kerakli sahifalarni ulang
- Admin Telegram ID orqali faqat o'zingiz buyruq bera olasiz

## 📞 Qo'llab-quvvatlash

Savollar bo'lsa, Notion'dagi "Bilimlar Bazasi"ga qarang yoki direktorga murojaat qiling.
