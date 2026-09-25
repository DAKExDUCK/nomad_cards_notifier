import asyncio
from contextlib import suppress
from collections.abc import Awaitable, Callable

from aiogram import Bot, Dispatcher
from aiogram.types import LinkPreviewOptions

from config import (
    NOMAD_BASE_URL,
    NOMAD_BOT_CHAT_ID,
    NOMAD_COLLECT_INTERVAL,
    NOMAD_COLLECTOR_ENABLED,
    NOMAD_CLID,
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
from modules.notifications import EmailNotifier, EmailSettings


ErrorReporter = Callable[[str, BaseException], Awaitable[None]]


def _create_error_reporter() -> ErrorReporter:
    notifier = EmailNotifier(EmailSettings.from_env())

    async def report_error(context: str, error: BaseException) -> None:
        try:
            await notifier.report_exception(context, error)
        except Exception:
            Logger.error("Failed to send email error report", exc_info=True)

    return report_error


def _create_collector(bot: Bot, report_error: ErrorReporter) -> NomadCardsCollector | None:
    required_settings = (NOMAD_USERNAME, NOMAD_PASSWORD, NOMAD_CLID, NOMAD_BOT_CHAT_ID)
    if not NOMAD_COLLECTOR_ENABLED or not all(required_settings):
        return None

    async def notify(text: str) -> None:
        await bot.send_message(
            chat_id=NOMAD_BOT_CHAT_ID,
            text=text,
            parse_mode="HTML",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )

    return NomadCardsCollector(
        base_url=NOMAD_BASE_URL,
        username=NOMAD_USERNAME,
        password=NOMAD_PASSWORD,
        clid=NOMAD_CLID,
        notify=notify,
        interval_seconds=NOMAD_COLLECT_INTERVAL,
        sales_from=NOMAD_SALES_FROM,
        sales_to=NOMAD_SALES_TO,
        station_urls=NOMAD_STATION_URLS,
        on_error=report_error,
    )


async def main() -> None:
    Logger.load_config()
    report_error = _create_error_reporter()

    # Initialize database
    await init_db()
    Logger.logger.info("Database initialized")

    # Bot setup
    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    await register_bot_handlers(bot, dp, report_error)

    collector = _create_collector(bot, report_error)
    collector_task = asyncio.create_task(collector.run_forever(), name="nomad-cards-collector") if collector else None
    if collector_task:
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
