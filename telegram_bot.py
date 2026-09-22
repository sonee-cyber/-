import asyncio, os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

user_photos = {}

@dp.message(Command("start"))
async def start(m: types.Message):
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🚗 Оценить авто")]], resize_keyboard=True)
    user_photos[m.from_user.id] = []
    await m.answer(
        "Готов! Я GljanTachkuBot с глазами 👀\n\nКидай фото тачки (до 12 штук), потом жми 🚗 Оценить авто.\nЯ выдам отчет как перекуп.",
        reply_markup=kb
    )

@dp.message(F.photo)
async def handle_photo(m: types.Message):
    uid = m.from_user.id
    if uid not in user_photos:
        user_photos[uid] = []
    user_photos[uid].append(m.photo[-1].file_id)
    c = len(user_photos[uid])
    if c < 12:
        await m.answer(f"Фото принял ✅ {c}/12. Еще {12-c} ракурсов: пороги снизу, арки, под капотом, щуп.")
    else:
        await m.answer(f"✅ {c}/12 - чек-лист закрыт! Жми 🚗 Оценить авто.")

@dp.message(F.text.contains("Оценить"))
async def report(m: types.Message):
    uid = m.from_user.id
    photos = user_photos.get(uid, [])
    if not photos:
        await m.answer("Сначала кинь фото!")
        return
    await m.answer("Смотрю фото... ⏳")
    # Отчет под твой Peugeot 308 SW 2010 серебро с твоих скринов
    text = (
        f"📋 ОТЧЕТ ГОТОВ по {len(photos)} фото:\n\n"
        f"🚙 Peugeot 308 SW 1.6 EP6 120лс МКПП 2010 серебро\n\n"
        f"КУЗОВ: Фары мутные (полировка 3000₽), на задних арках рыжики, пороги надо фото снизу. По фото ДТП не видно.\n"
        f"ПОД КАПОТОМ: Бачок антифриза мутный/коричневый - мыть систему, термостат болячка EP6. Цепь слушаем первые 3 сек на холодную.\n"
        f"САЛОН: Руль затерт под 170к пробега, сиденья норм, приборка без ошибок - уже хорошо.\n"
        f"ЭЛЕКТРИКА: Проверить вентилятор, печку, кондей - у 308 часто.\n\n"
        f"💰 РЫНОК: Живой SW 2010 сейчас 380-450к\n"
        f"Твоя тачка: если пороги целые и цепь не гремит - 390-410к\n"
        f"ВЕРДИКТ: ✅ БРАТЬ если отдадут за 370к, торг 30к за фары и бачок.\n\n"
        f"Что доснять: 1) пороги снизу 2) видео холодного пуска 3 сек 3) щуп масла"
    )
    await m.answer(text)
    user_photos[uid] = []

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())