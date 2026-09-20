import asyncio
from contextlib import suppress

from aiogram import Bot, Dispatcher

from config import (
    NOMAD_BASE_URL,
    NOMAD_COLLECT_INTERVAL,
    NOMAD_COLLECTOR_ENABLED,
    NOMAD_CLID,
    NOMAD_NOTIFY_CHAT_ID,
    NOMAD_PASSWORD,
    NOMAD_SALES_FROM,
    NOMAD_SALES_TO,
    NOMAD_STATION_URLS,
    NOMAD_USERNAME,
    TOKEN,
)
from modules.bot import register_bot_handlers
from modules.database import close_db, init_db
from modules.fuel_cards import NomadCardsCollector
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
    collector_task = None

    if NOMAD_COLLECTOR_ENABLED and NOMAD_USERNAME and NOMAD_PASSWORD and NOMAD_CLID and NOMAD_NOTIFY_CHAT_ID:
        async def notify(text: str) -> None:
            await bot.send_message(chat_id=int(NOMAD_NOTIFY_CHAT_ID), text=text, parse_mode="HTML")

        collector = NomadCardsCollector(
            base_url=NOMAD_BASE_URL,
            username=NOMAD_USERNAME,
            password=NOMAD_PASSWORD,
            clid=NOMAD_CLID,
            notify=notify,
            interval_seconds=NOMAD_COLLECT_INTERVAL,
            sales_from=NOMAD_SALES_FROM,
            sales_to=NOMAD_SALES_TO,
            station_urls=NOMAD_STATION_URLS,
        )
        collector_task = asyncio.create_task(collector.run_forever(), name="nomad-cards-collector")
        Logger.info("Nomad fuel-card collector started")

    try:
        await dp.start_polling(bot)
    finally:
        if collector_task:
            collector_task.cancel()
            with suppress(asyncio.CancelledError):
                await collector_task
        await close_db()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
