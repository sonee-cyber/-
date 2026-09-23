import os, asyncio, logging
logging.basicConfig(level=logging.INFO)
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

BOT_TOKEN = os.getenv("BOT_TOKEN")
print(f"BOOT MINIMAL | BOT_TOKEN set={bool(BOT_TOKEN)}")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN env is empty!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(m: types.Message):
    await m.answer("Bot minimal ALIVE ✅\nSend VIN test")

@dp.message()
async def echo(m: types.Message):
    await m.answer(f"Got: {m.text[:100]}")

async def main():
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        print("Webhook deleted")
    except Exception as e:
        print(f"delete webhook error: {e}")
    print("Start polling minimal...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())