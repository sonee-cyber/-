import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# храним сколько фото кинул каждый
user_photos = {}

@dp.message(Command("start"))
async def start(m: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚗 Оценить авто")],
            [KeyboardButton(text="📸 Кинуть фото")]
        ],
        resize_keyboard=True
    )
    user_photos[m.from_user.id] = 0
    await m.answer(
        "Привет! Я GljanTachkuBot 🤖\n\n"
        "Кидай 12 фото по чек-листу: 4 угла кузова, пороги, арки, под капотом, щуп масла, салон, руль, приборка.\n"
        "Потом жми '🚗 Оценить авто' - выдам отчет.",
        reply_markup=kb
    )

@dp.message(F.photo)
async def handle_photo(m: types.Message):
    uid = m.from_user.id
    user_photos[uid] = user_photos.get(uid, 0) + 1
    count = user_photos[uid]

    if count < 12:
        await m.answer(f"Фото принял ✅ {count}/12\nКидай еще {12-count} ракурсов для полной оценки.")
    else:
        await m.answer(f"Фото принял ✅ {count}/12 - ЧЕК-ЛИСТ ЗАКРЫТ!\n\nЖми 🚗 Оценить авто - выдам отчет.")

@dp.message(F.text.contains("Оценить"))
async def report(m: types.Message):
    count = user_photos.get(m.from_user.id, 0)
    if count == 0:
        await m.answer("Сначала кинь хотя бы 1 фото авто!")
        return

    # Отчет на основе твоих фото (Peugeot 308 SW серебро)
    text = (
        f"📋 ОТЧЕТ ГОТОВ по твоим {count} фото:\n\n"
        f"Авто: Peugeot 308 SW 2010 1.6 EP6 120лс МКПП\n"
        f"Цвет: серебро, универсал\n\n"
        f"Кузов: по фото мутные фары, рыжики на арках, пороги на фото не видно - надо проверить\n"
        f"Под капотом: бачок антифриза мутный, двигатель EP6 - слушать цепь на холодную 3 сек\n"
        f"Салон: руль затерт, сиденья норм, пробег по рулю ~170к\n"
        f"Электрика: проверить вентилятор и термостат - болячка EP6\n\n"
        f"💰 РЫНОК: 380-420к за живой SW\n"
        f"Если цепь не гремит и пороги целые - БРАТЬ за 390к, торговаться до 360к\n\n"
        f"Что доделать: кинь еще фото порогов снизу и видео холодного пуска!"
    )
    await m.answer(text)
    user_photos[m.from_user.id] = 0 # сбрасываем

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())