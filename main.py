# main.py
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.bot import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
from handlers import router
from db import init_db


async def main():
    init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(router)

    print("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
