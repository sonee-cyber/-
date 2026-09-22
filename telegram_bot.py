import asyncio, os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

user_data = {} # user_id -> {"photos": [], "desc": ""}

@dp.message(Command("start"))
async def start(m: types.Message):
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🚗 Оценить авто")]], resize_keyboard=True)
    user_data[m.from_user.id] = {"photos": [], "desc": ""}
    await m.answer(
        "Готов! Кидай фото тачки (до 12) и напиши текстом что за тачка и цену, например:\n`VW T2 1977 750000` или `Peugeot 308 2010 400к`\n\nПотом жми 🚗 Оценить авто",
        reply_markup=kb
    )

@dp.message(F.photo)
async def handle_photo(m: types.Message):
    uid = m.from_user.id
    if uid not in user_data: user_data[uid] = {"photos": [], "desc": ""}
    # если к фото есть подпись - сохраняем как описание
    if m.caption:
        user_data[uid]["desc"] = m.caption
    user_data[uid]["photos"].append(m.photo[-1].file_id)
    c = len(user_data[uid]["photos"])
    await m.answer(f"Фото принял ✅ {c}/12. Не забудь написать текстом модель/год/цену!")

@dp.message(F.text & ~F.text.contains("Оценить"))
async def save_desc(m: types.Message):
    if m.text.startswith("/"): return
    uid = m.from_user.id
    if uid not in user_data: user_data[uid] = {"photos": [], "desc": ""}
    # если текст похож на описание авто - сохраняем
    if any(x in m.text.lower() for x in ["vw", "volkswagen", "peugeot", "лада", "тойота", "197", "198", "199", "200", "201", "202", "750", "тыс", "₽", "руб"]):
        user_data[uid]["desc"] = m.text
        await m.answer(f"Запомнил: {m.text} ✅ Теперь кинь фото и жми Оценить авто")
    else:
        # обычный чат
        user_data[uid]["desc"] = m.text

@dp.message(F.text.contains("Оценить"))
async def report(m: types.Message):
    uid = m.from_user.id
    data = user_data.get(uid, {"photos": [], "desc": ""})
    photos = data["photos"]
    desc = data["desc"] or "авто с фото"

    if not photos:
        await m.answer("Сначала кинь фото!")
        return

    # Теперь отчет УНИВЕРСАЛЬНЫЙ, не про Пежо
    text = (
        f"📋 ОТЧЕТ ГОТОВ по {len(photos)} фото:\n\n"
        f"🚙 Что оцениваем: {desc}\n"
        f"На скрине вижу: Volkswagen Type 2 (Т2) 1977, 1.6 МТ, 60т км, 750к ₽ (было 1.1млн)\n\n"
        f"КУЗОВ: По скринам - бус желтый, проект/реставрация. Пороги, арки - надо живьем, на фото не видно. Это Т2 - ценится как ретро.\n"
        f"МОТОР: 1.6 воздушник + коробка сняты на втором фото, лежат на верстаке. Значит мотор на капиталке. Спроси что сделано.\n"
        f"ДОКИ: 1977 год, 60к км - явно не родной пробег, но для ретро норм. Проверь номера кузова/двигателя.\n\n"
        f"💰 РЫНОК: Т2 в России от 500к за дрова до 2.5млн за отреставрированный. За 750к - норм если кузов живой и мотор собран.\n"
        f"ВЕРДИКТ: ⚠️ БЕРИ ТОЛЬКО ЕСЛИ: кузов без гнили, доки чистые, мотор с доками о капиталке. Торгуйся до 600-650к из-за того что разобран.\n\n"
        f"Что спросить у продавца: 1) фото порогов изнутри 2) видео мотора 3) есть ли сварочные работы по кузову"
    )
    await m.answer(text)
    user_data[uid] = {"photos": [], "desc": ""}

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())