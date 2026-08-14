import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

import database as db

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "PUT_YOUR_BOT_TOKEN_HERE")

# Bir nechta admin: ADMIN_IDS="111,222,333" (ustuvor) yoki eski ADMIN_ID="111"
_admin_ids_raw = os.environ.get("ADMIN_IDS") or os.environ.get("ADMIN_ID", "0")
ADMIN_IDS = {int(x.strip()) for x in _admin_ids_raw.split(",") if x.strip().lstrip("-").isdigit()}
ADMIN_IDS.discard(0)

# Tasdiqlangan vakansiyalar avtomatik post qilinadigan kanal (ixtiyoriy)
# Kanal username (@mychannel) yoki raqamli ID (-100...) bo'lishi mumkin
CHANNEL_ID = os.environ.get("CHANNEL_ID", "").strip() or None

router = Router()

CANCEL_TEXT = "❌ Bekor qilish"
MENU_POST = "📢 Vakansiya joylash"
MENU_BROWSE = "🔎 Vakansiyalarni ko'rish"
MENU_MY = "🧾 Mening e'lonlarim"
MENU_SUBSCRIBE = "🔔 Obuna"
MENU_ADMIN = "👨‍💼 Admin panel"

STATUS_LABEL = {
    "pending": "⏳ Kutilmoqda",
    "approved": "✅ Tasdiqlangan",
    "rejected": "❌ Rad etilgan",
}


# ---------- Klaviaturalar ----------

def main_menu_keyboard(is_admin_user: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=MENU_POST)],
        [KeyboardButton(text=MENU_BROWSE), KeyboardButton(text=MENU_MY)],
        [KeyboardButton(text=MENU_SUBSCRIBE)],
    ]
    if is_admin_user:
        rows.append([KeyboardButton(text=MENU_ADMIN)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=CANCEL_TEXT)]], resize_keyboard=True
    )


def regions_keyboard(prefix: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=region, callback_data=f"{prefix}:{i}")]
        for i, region in enumerate(db.REGIONS)
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_decision_keyboard(vacancy_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Qabul qilish", callback_data=f"approve:{vacancy_id}"),
                InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject:{vacancy_id}"),
            ]
        ]
    )


def delete_keyboard(vacancy_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"delete:{vacancy_id}")]]
    )


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Kutayotgan e'lonlar", callback_data="admin_pending")],
            [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
        ]
    )


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def subscribe_keyboard(tg_user_id: int) -> InlineKeyboardMarkup:
    subscribed = db.get_user_subscriptions(tg_user_id)
    buttons = []
    for i, region in enumerate(db.REGIONS):
        mark = "✅ " if region in subscribed else ""
        buttons.append([InlineKeyboardButton(text=f"{mark}{region}", callback_data=f"sub:{i}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ---------- FSM holatlar ----------

class PostVacancy(StatesGroup):
    company_name = State()
    region = State()
    title = State()
    description = State()
    salary = State()
    contact = State()


class BrowseVacancies(StatesGroup):
    region = State()


# ---------- Bekor qilish (istalgan holatda ishlaydi) ----------

@router.message(F.text == CANCEL_TEXT)
async def cancel_any(message: Message, state: FSMContext):
    current = await state.get_state()
    if current is None:
        return
    await state.clear()
    await message.answer(
        "Bekor qilindi. Bosh menyuga qaytdingiz.",
        reply_markup=main_menu_keyboard(is_admin(message.from_user.id)),
    )


# ---------- /start va bosh menyu ----------

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Salom! Bu — vakansiyalar bo'yicha bot.\n\n"
        "📢 Ish beruvchi bo'lsangiz — vakansiya joylashingiz mumkin (admin tasdiqlagandan so'ng e'lon qilinadi).\n"
        "🔎 Ish qidiruvchi bo'lsangiz — hududingiz bo'yicha vakansiyalarni ko'rishingiz mumkin.\n"
        "🧾 \"Mening e'lonlarim\" bo'limidan joylagan vakansiyalaringiz holatini kuzatib borishingiz mumkin.",
        reply_markup=main_menu_keyboard(is_admin(message.from_user.id)),
    )


@router.message(F.text == MENU_POST)
async def start_post_vacancy(message: Message, state: FSMContext):
    await state.set_state(PostVacancy.company_name)
    await message.answer("Kompaniya nomini kiriting:", reply_markup=cancel_keyboard())


@router.message(PostVacancy.company_name)
async def get_company_name(message: Message, state: FSMContext):
    await state.update_data(company_name=message.text.strip())
    await state.set_state(PostVacancy.region)
    await message.answer("Qaysi viloyat uchun vakansiya?", reply_markup=regions_keyboard("vacregion"))


@router.callback_query(PostVacancy.region, F.data.startswith("vacregion:"))
async def get_region(callback: CallbackQuery, state: FSMContext):
    idx = int(callback.data.split(":")[1])
    region = db.REGIONS[idx]
    await state.update_data(region=region)
    await state.set_state(PostVacancy.title)
    await callback.message.answer(
        f"Hudud: {region}\n\nEndi lavozim nomini kiriting (masalan: SMM menejer):",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@router.message(PostVacancy.title)
async def get_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(PostVacancy.description)
    await message.answer("Vakansiya tavsifini kiriting (talablar, ish sharoiti va h.k.):")


@router.message(PostVacancy.description)
async def get_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await state.set_state(PostVacancy.salary)
    await message.answer("Maosh miqdorini kiriting (ko'rsatmoqchi bo'lmasangiz — \"-\" deb yozing):")


@router.message(PostVacancy.salary)
async def get_salary(message: Message, state: FSMContext):
    salary = message.text.strip()
    if salary in ("-", "yo'q", "yoq"):
        salary = "Kelishilgan holda"
    await state.update_data(salary=salary)
    await state.set_state(PostVacancy.contact)
    await message.answer("Aloqa uchun telefon raqam yoki username kiriting:")


@router.message(PostVacancy.contact)
async def get_contact(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    contact = message.text.strip()

    employer_id = db.upsert_employer(message.from_user.id, data["company_name"])
    vacancy_id = db.create_vacancy(
        employer_id=employer_id,
        region=data["region"],
        title=data["title"],
        description=data["description"],
        salary=data["salary"],
        contact=contact,
    )
    await state.clear()

    await message.answer(
        "✅ Vakansiyangiz qabul qilindi va admin ko'rib chiqishi uchun yuborildi.\n"
        "Tasdiqlangandan so'ng e'lon qilinadi va sizga xabar beriladi.\n"
        "Holatini \"🧾 Mening e'lonlarim\" bo'limidan kuzatishingiz mumkin.",
        reply_markup=main_menu_keyboard(is_admin(message.from_user.id)),
    )

    if ADMIN_IDS:
        text = (
            f"🆕 Yangi vakansiya (#{vacancy_id})\n\n"
            f"🏢 Kompaniya: {data['company_name']}\n"
            f"📍 Hudud: {data['region']}\n"
            f"💼 Lavozim: {data['title']}\n"
            f"📝 Tavsif: {data['description']}\n"
            f"💰 Maosh: {data['salary']}\n"
            f"📞 Aloqa: {contact}"
        )
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, text, reply_markup=admin_decision_keyboard(vacancy_id))
            except Exception as e:
                log.warning("Adminga (%s) xabar yuborilmadi: %s", admin_id, e)


# ---------- Admin qaror qabul qilishi ----------

@router.callback_query(F.data.startswith("approve:"))
async def approve_vacancy(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer("Bu tugma faqat admin uchun.", show_alert=True)
        return
    vacancy_id = int(callback.data.split(":")[1])
    db.set_vacancy_status(vacancy_id, "approved")
    vac = db.get_vacancy(vacancy_id)

    await callback.message.edit_text(callback.message.text + "\n\n✅ QABUL QILINDI")
    await callback.answer("Qabul qilindi")

    try:
        await bot.send_message(
            vac["employer_tg_id"],
            f"✅ \"{vac['title']}\" vakansiyangiz tasdiqlandi va endi ko'rinadi.",
        )
    except Exception as e:
        log.warning("Ish beruvchiga xabar yuborilmadi: %s", e)

    public_text = (
        f"💼 {vac['title']}\n"
        f"🏢 {vac['company_name']}\n"
        f"📍 {vac['region']}\n"
        f"💰 {vac['salary']}\n"
        f"📝 {vac['description']}\n"
        f"📞 {vac['contact']}"
    )

    # Kanalga avtomatik post
    if CHANNEL_ID:
        try:
            await bot.send_message(CHANNEL_ID, public_text)
        except Exception as e:
            log.warning("Kanalga post qilinmadi: %s", e)

    # Shu hudud obunachilariga xabar
    for sub_id in db.get_subscribers(vac["region"]):
        try:
            await bot.send_message(sub_id, f"🔔 Yangi vakansiya!\n\n{public_text}")
        except Exception as e:
            log.warning("Obunachiga (%s) xabar yuborilmadi: %s", sub_id, e)


@router.callback_query(F.data.startswith("reject:"))
async def reject_vacancy(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer("Bu tugma faqat admin uchun.", show_alert=True)
        return
    vacancy_id = int(callback.data.split(":")[1])
    db.set_vacancy_status(vacancy_id, "rejected")
    vac = db.get_vacancy(vacancy_id)

    await callback.message.edit_text(callback.message.text + "\n\n❌ RAD ETILDI")
    await callback.answer("Rad etildi")

    try:
        await bot.send_message(
            vac["employer_tg_id"],
            f"❌ \"{vac['title']}\" vakansiyangiz rad etildi. Qayta tekshirib, qaytadan yuborishingiz mumkin.",
        )
    except Exception as e:
        log.warning("Ish beruvchiga xabar yuborilmadi: %s", e)


# ---------- Vakansiyalarni ko'rish (ish qidiruvchi) ----------

@router.message(F.text == MENU_BROWSE)
async def browse_start(message: Message, state: FSMContext):
    await state.set_state(BrowseVacancies.region)
    await message.answer(
        "Qaysi hudud bo'yicha vakansiyalarni ko'rmoqchisiz?",
        reply_markup=regions_keyboard("browseregion"),
    )


@router.callback_query(BrowseVacancies.region, F.data.startswith("browseregion:"))
async def browse_region(callback: CallbackQuery, state: FSMContext):
    idx = int(callback.data.split(":")[1])
    region = db.REGIONS[idx]
    await state.clear()

    vacancies = db.get_approved_vacancies(region)
    if not vacancies:
        await callback.message.answer(f"Hozircha \"{region}\" bo'yicha tasdiqlangan vakansiya yo'q.")
        await callback.answer()
        return

    for v in vacancies:
        text = (
            f"💼 {v['title']}\n"
            f"🏢 {v['company_name']}\n"
            f"📍 {v['region']}\n"
            f"💰 {v['salary']}\n"
            f"📝 {v['description']}\n"
            f"📞 {v['contact']}"
        )
        await callback.message.answer(text)
    await callback.answer()


@router.message(Command("vacancies"))
async def cmd_vacancies(message: Message, state: FSMContext):
    await state.set_state(BrowseVacancies.region)
    await message.answer("Qaysi hudud bo'yicha vakansiyalarni ko'rmoqchisiz?", reply_markup=regions_keyboard("browseregion"))


# ---------- Mening e'lonlarim ----------

@router.message(F.text == MENU_MY)
async def my_listings(message: Message):
    vacancies = db.get_vacancies_by_tg_user(message.from_user.id)
    if not vacancies:
        await message.answer("Siz hali birorta ham vakansiya joylamagansiz.")
        return

    await message.answer(f"Sizning e'lonlaringiz ({len(vacancies)} ta):")
    for v in vacancies:
        text = (
            f"{STATUS_LABEL.get(v['status'], v['status'])}\n"
            f"💼 {v['title']}\n"
            f"📍 {v['region']}\n"
            f"💰 {v['salary']}"
        )
        await message.answer(text, reply_markup=delete_keyboard(v["id"]))


@router.callback_query(F.data.startswith("delete:"))
async def delete_listing(callback: CallbackQuery):
    vacancy_id = int(callback.data.split(":")[1])
    ok = db.delete_vacancy(vacancy_id, callback.from_user.id)
    if ok:
        await callback.message.edit_text(callback.message.text + "\n\n🗑 O'CHIRILDI")
        await callback.answer("O'chirildi")
    else:
        await callback.answer("Bu e'lon topilmadi yoki sizga tegishli emas.", show_alert=True)


# ---------- Obuna (hudud bo'yicha bildirishnoma) ----------

@router.message(F.text == MENU_SUBSCRIBE)
async def subscribe_menu(message: Message):
    await message.answer(
        "Qaysi hududlar bo'yicha yangi vakansiyalardan xabardor bo'lishni xohlaysiz?\n"
        "Hududni bosing — obuna yoqiladi, qayta bossangiz — o'chadi.",
        reply_markup=subscribe_keyboard(message.from_user.id),
    )


@router.callback_query(F.data.startswith("sub:"))
async def toggle_subscription(callback: CallbackQuery):
    idx = int(callback.data.split(":")[1])
    region = db.REGIONS[idx]
    now_subscribed = db.toggle_subscription(callback.from_user.id, region)
    await callback.message.edit_reply_markup(reply_markup=subscribe_keyboard(callback.from_user.id))
    if now_subscribed:
        await callback.answer(f"✅ \"{region}\" bo'yicha obuna yoqildi")
    else:
        await callback.answer(f"Obuna o'chirildi: {region}")


# ---------- Admin panel ----------

@router.message(F.text == MENU_ADMIN)
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("Bu bo'lim faqat admin uchun.")
        return
    await message.answer("Admin panel:", reply_markup=admin_panel_keyboard())


@router.callback_query(F.data == "admin_pending")
async def admin_pending(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Faqat admin uchun.", show_alert=True)
        return
    vacancies = db.get_pending_vacancies()
    await callback.answer()
    if not vacancies:
        await callback.message.answer("Hozircha kutilayotgan e'lon yo'q.")
        return
    for v in vacancies:
        text = (
            f"🆕 (#{v['id']})\n"
            f"🏢 {v['company_name']}\n"
            f"📍 {v['region']}\n"
            f"💼 {v['title']}\n"
            f"📝 {v['description']}\n"
            f"💰 {v['salary']}\n"
            f"📞 {v['contact']}"
        )
        await callback.message.answer(text, reply_markup=admin_decision_keyboard(v["id"]))


@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Faqat admin uchun.", show_alert=True)
        return
    stats = db.get_stats()
    await callback.answer()
    await callback.message.answer(
        "📊 Statistika:\n\n"
        f"Jami: {stats['total'] or 0}\n"
        f"⏳ Kutilmoqda: {stats['pending'] or 0}\n"
        f"✅ Tasdiqlangan: {stats['approved'] or 0}\n"
        f"❌ Rad etilgan: {stats['rejected'] or 0}"
    )


async def main():
    if BOT_TOKEN == "PUT_YOUR_BOT_TOKEN_HERE":
        raise SystemExit("BOT_TOKEN muhit o'zgaruvchisini o'rnating (BotFather'dan oling).")
    if not ADMIN_IDS:
        log.warning("ADMIN_IDS/ADMIN_ID o'rnatilmagan — admin funksiyalari ishlamaydi!")
    if not CHANNEL_ID:
        log.info("CHANNEL_ID o'rnatilmagan — kanalga avtomatik post o'chirilgan.")

    db.init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
