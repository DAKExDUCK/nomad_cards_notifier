import asyncio

from aiogram import Bot, Dispatcher

from config import TOKEN
from modules.bot import register_bot_handlers
from modules.database import close_db, init_db
from modules.logger import Logger


async def main():
    Logger.load_config()

    # Initialize database
    await init_db()
    Logger.logger.info("Database initialized")

    # Bot setup
    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    await register_bot_handlers(bot, dp)

    try:
        await dp.start_polling(bot)
    finally:
        await close_db()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
