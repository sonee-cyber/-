import asyncio
import aiohttp
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(m: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚗 Оценить авто")],
            [KeyboardButton(text="📸 Кинуть фото"), KeyboardButton(text="🔍 Пробить VIN")]
        ],
        resize_keyboard=True
    )
    await m.answer(
        "Привет! Я бот-оценщик авто.\n\n"
        "Кидай фото авто, VIN или напиши: год пробег хозяев цена\n"
        "Например: 2010 170000 3 390000",
        reply_markup=kb
    )

@dp.message(F.text.len() == 17)
async def handle_vin(m: types.Message):
    vin = m.text.strip().upper()
    await m.answer(f"Пробиваю {vin}...")
    url = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{vin}?format=json"
    async with aiohttp.ClientSession() as s:
        async with s.get(url) as r:
            j = await r.json()
            d = j["Results"][0]
            await m.answer(f"Марка: {d.get('Make')}\nМодель: {d.get('Model')}\nГод: {d.get('ModelYear')}")

@dp.message(F.photo)
async def handle_photo(m: types.Message):
    await m.answer("Фото принял ✅ Кидай еще 11 ракурсов для полной оценки.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())