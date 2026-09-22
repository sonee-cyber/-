import asyncio, os, base64
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from openai import AsyncOpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
OR_KEY = os.getenv("OPENAI_API_KEY")

print(f"KEY EXISTS: {bool(OR_KEY)}") # для логов Railway

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
client = AsyncOpenAI(api_key=OR_KEY, base_url="https://openrouter.ai/api/v1") if OR_KEY else None

user_data = {}

@dp.message(Command("start"))
async def start(m: types.Message):
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🚗 Оценить авто")]], resize_keyboard=True)
    user_data[m.from_user.id] = {"photos": [], "desc": ""}
    await m.answer(f"Бот перезапущен! Ключ подключен: {bool(OR_KEY)} ✅\nКидай фото до 12 штук и жми 🚗 Оценить авто", reply_markup=kb)

@dp.message(F.photo)
async def handle_photo(m: types.Message):
    uid = m.from_user.id
    if uid not in user_data: user_data[uid] = {"photos": [], "desc": ""}
    if m.caption:
        user_data[uid]["desc"] = m.caption
    user_data[uid]["photos"].append(m.photo[-1].file_id)
    await m.answer(f"Фото принял ✅ {len(user_data[uid]['photos'])}/12")

@dp.message(F.text & ~F.text.contains("Оценить"))
async def save_desc(m: types.Message):
    if m.text.startswith("/"): return
    uid = m.from_user.id
    if uid not in user_data: user_data[uid] = {"photos": [], "desc": ""}
    user_data[uid]["desc"] += " " + m.text

@dp.message(F.text.contains("Оценить"))
async def report(m: types.Message):
    uid = m.from_user.id
    data = user_data.get(uid, {"photos": [], "desc": ""})
    photos = data["photos"]
    desc = data["desc"] or "авто с фото"

    if not OR_KEY or not client:
        await m.answer("❌ Ключ не подключен! Иди в Railway -> Variables -> проверь что есть OPENAI_API_KEY = sk-or-v1-...")
        return
    if not photos:
        await m.answer("Кинь фото сначала!")
        return

    await m.answer(f"Смотрю твои {len(photos)} фото... делаю отчет как перекуп ⏳")

    try:
        imgs = []
        for fid in photos[-5:]:
            file = await bot.get_file(fid)
            fb = await bot.download_file(file.file_path)
            b64 = base64.b64encode(fb.read()).decode()
            imgs.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

        prompt = f"""Ты - жесткий автоподборщик-перекуп, 20 лет опыта. Авто клиента: {desc}. 
Изучи ФОТО внимательно.

Дай отчет СТРОГО в таком формате, на русском, коротко и по делу:

🚗 ЧТО ЗА ТАЧКА: модель, год на глаз, комплектация

🔍 КУЗОВ: есть ли перекрасы, вмятины, ржавчина, зазоры, состояние порогов/арок. Что видно по фото.

🛋️ САЛОН: износ руля, сидений, кнопок. Что с чистотой, курил ли.

⚠️ КОСЯКИ И РИСКИ: топ-3 на что обратить при осмотре вживую именно для этой модели.

💰 ЦЕНА И ТОРГ: рыночная цена такой, за сколько брать, на что давить для скидки 20-50к.

✅ ВЕРДИКТ: БРАТЬ / НЕ БРАТЬ / БРАТЬ ЕСЛИ...

Пиши как свой, без воды, как в гараже."""

        resp = await client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}] + imgs}]
        )
        answer = resp.choices[0].message.content
        await m.answer(f"📋 ОТЧЕТ ГОТОВ:\n\n{answer}")
        user_data[uid] = {"photos": [], "desc": ""}
    except Exception as e:
        await m.answer(f"Ошибка AI: {e}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())