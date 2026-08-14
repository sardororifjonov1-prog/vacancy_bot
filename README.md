# Vakansiya bot + sayt

Ish beruvchi Telegram bot orqali hududini tanlab vakansiya joylaydi → admin
tasdiqlaydi/rad etadi → tasdiqlangan vakansiyalar botda (`/vacancies`) va
saytda (bir xil SQLite bazadan) ko'rinadi.

## Fayllar

- `database.py` — umumiy SQLite baza (bot va sayt shu bazani ishlatadi)
- `bot.py` — Telegram bot (aiogram 3)
- `web/app.py` — Flask sayt (`web/templates/index.html`)
- `vacancy_bot.db` — ishga tushirilganda avtomatik yaratiladi

## O'rnatish

```bash
cd vacancy_bot
pip install -r requirements.txt
```

## Botni ishga tushirish

1. @BotFather orqali bot yarating, tokenni oling
2. O'zingizning Telegram ID'ingizni bilib oling (masalan @userinfobot orqali)
3. Muhit o'zgaruvchilarini o'rnating va ishga tushiring:

```bash
export BOT_TOKEN="123456:ABC-your-token"
export ADMIN_ID="123456789"
python3 bot.py
```

Admin sifatida siz yangi vakansiyalar haqida xabar olasiz, har birida
✅ **Qabul qilish** / ❌ **Rad etish** tugmalari bo'ladi.

## Saytni ishga tushirish

```bash
cd web
python3 app.py
```

`http://localhost:5000` manzilida ochiladi, yuqorida hudud bo'yicha filtr
(chip)lar bor. Faqat admin tasdiqlagan vakansiyalar ko'rinadi.

## Ishlash tartibi

1. Foydalanuvchi botga `/start` yozadi → "📢 Vakansiya joylash" tugmasini bosadi
2. Kompaniya nomi → hudud (14 ta hudud: 12 viloyat + Qoraqalpog'iston
   Respublikasi + Toshkent shahri) → lavozim → tavsif → maosh → aloqa
3. E'lon `pending` holatda bazaga yoziladi va adminga yuboriladi
4. Admin ✅/❌ bossa, holat yangilanadi va ish beruvchiga xabar boradi
5. Tasdiqlangan e'lonlar botda `/vacancies` va saytda ko'rinadi

## Kengaytirish g'oyalari

- Har bir hudud uchun alohida Telegram kanalga avtomatik post qilish
- Bir nechta admin qo'shish (ADMIN_ID ro'yxati)
- Ish beruvchi o'z e'lonlarini o'chira olishi
- Saytda qidiruv (kalit so'z bo'yicha)
