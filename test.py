from aiogram import Bot

from modules.logger import Logger

from modules.database import close_db, init_db
from modules.fuel_cards import NomadCardsCollector
import asyncio
import sys
from config import (
    NOMAD_BASE_URL,
    NOMAD_USERNAME,
    NOMAD_PASSWORD,
    NOMAD_CLID,
    NOMAD_NOTIFY_CHAT_ID,
    NOMAD_COLLECT_INTERVAL,
    NOMAD_SALES_FROM,
    NOMAD_SALES_TO,
    NOMAD_STATION_URLS,
    TOKEN,
)

bot = Bot(token=TOKEN)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def notify(text: str) -> None:
    await bot.send_message(chat_id=int(NOMAD_NOTIFY_CHAT_ID), text=text, parse_mode="HTML")


Logger.load_config()
logger = Logger()

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


async def main() -> None:
    await init_db()
    logger.info("Initialized database")
    try:
        logger.info("Running collector once")
        await collector.run_once()
        logger.info("Collector run completed")
    finally:
        await close_db()
        await bot.close()


if __name__ == "__main__":
    logger.info("Starting main function")
    asyncio.run(main())
    logger.info("Finished main function")
