import asyncio, os, base64
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from openai import AsyncOpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
OR_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
client = AsyncOpenAI(api_key=OR_KEY, base_url="https://openrouter.ai/api/v1") if OR_KEY else None

user_data = {}

@dp.message(Command("start"))
async def start(m: types.Message):
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🚗 Оценить авто")]], resize_keyboard=True)
    user_data[m.from_user.id] = {"photos": [], "desc": ""}
    await m.answer("Готово! Я теперь вижу авто 👀\nКидай до 12 фото ЛЮБОЙ тачки + напиши модель/цену если есть.\nПотом жми 🚗 Оценить авто - разберу как эксперт.", reply_markup=kb)

@dp.message(F.photo)
async def handle_photo(m: types.Message):
    uid = m.from_user.id
    if uid not in user_data: user_data[uid] = {"photos": [], "desc": ""}
    if m.caption:
        user_data[uid]["desc"] = m.caption
    user_data[uid]["photos"].append(m.photo[-1].file_id)
    c = len(user_data[uid]["photos"])
    await m.answer(f"Фото принял ✅ {c}/12")

@dp.message(F.text & ~F.text.contains("Оценить"))
async def save_desc(m: types.Message):
    if m.text.startswith("/"): return
    uid = m.from_user.id
    if uid not in user_data: user_data[uid] = {"photos": [], "desc": ""}
    user_data[uid]["desc"] += " " + m.text
    await m.answer(f"Запомнил: {m.text}")

@dp.message(F.text.contains("Оценить"))
async def report(m: types.Message):
    uid = m.from_user.id
    data = user_data.get(uid, {"photos": [], "desc": ""})
    photos = data["photos"]
    desc = data["desc"]

    if not photos:
        await m.answer("Кинь фото сначала!")
        return

    await m.answer(f"Смотрю твои {len(photos)} фото... делаю отчет как перекуп ⏳")

    try:
        imgs = []
        for fid in photos[-6:]: # берем последние 6 фото
            file = await bot.get_file(fid)
            fb = await bot.download_file(file.file_path)
            b64 = base64.b64encode(fb.read()).decode()
            imgs.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

        prompt = f"Ты автоэксперт-перекуп. Клиент прислал авто: {desc}. Проанализируй фото. Дай: 1) Что за авто/состояние кузова 2) Что под капотом/салон 3) Косяки и на что торговаться 4) Рыночная цена и вердикт БРАТЬ/НЕ БРАТЬ. Пиши коротко, по-пацански, на русском, как для своих."

        resp = await client.chat.completions.create(
            model="google/gemini-2.0-flash-exp:free",
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}] + imgs}]
        )
        answer = resp.choices[0].message.content
        await m.answer(f"📋 ОТЧЕТ ГОТОВ:\n\n{answer}")
        user_data[uid] = {"photos": [], "desc": ""}
    except Exception as e:
        await m.answer(f"Ошибка AI: {e}\nПопробуй еще раз /start")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())