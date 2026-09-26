import asyncio
from contextlib import suppress
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from html import escape

from aiogram import Bot, Dispatcher
from aiogram.types import LinkPreviewOptions

from config import (
    NOMAD_BASE_URL,
    NOMAD_BOT_CHAT_ID,
    NOMAD_COLLECT_INTERVAL,
    NOMAD_COLLECTOR_ENABLED,
    NOMAD_CLID,
    NOMAD_PASSWORD,
    NOMAD_DAILY_REPORT_CHAT_ID,
    NOMAD_DAILY_REPORT_TIME,
    NOMAD_SALES_FROM,
    NOMAD_SALES_TO,
    NOMAD_STATION_URLS,
    NOMAD_USERNAME,
    TOKEN,
    TZ,
)
from modules.bot import register_bot_handlers
from modules.database import close_db, init_db, DatabaseService
from modules.fuel_cards import NomadCardsCollector
from modules.logger import Logger
from modules.notifications import EmailNotifier, EmailSettings


ErrorReporter = Callable[[str, BaseException], Awaitable[None]]


def _daily_report_delay(now: datetime, report_time: str) -> float:
    hour, minute = (int(part) for part in report_time.split(":"))
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def _send_daily_balance_report(bot: Bot) -> None:
    cards = await DatabaseService.get_fuel_cards_with_balances()
    lines = ["💳 <b>Баланс топливных карт</b>", ""]
    if not cards:
        lines.append("Карточки пока не загружены.")
    else:
        for card, balance in cards:
            card_name = escape(card.name or card.external_id)
            card_balance = escape(balance or "не указан")
            last_operations = await DatabaseService.get_card_operations(card.id, 1)
            last_operation = last_operations[0] if last_operations else None
            card_fuel_type = None
            if last_operation:
                card_fuel_type = escape(last_operation.fuel)
            lines.append(f"• <b>{card_name}</b>: {f'{card_fuel_type} - ' if card_fuel_type else ''}<b>{card_balance} л</b>")
    await bot.send_message(
        chat_id=NOMAD_DAILY_REPORT_CHAT_ID,
        text="\n".join(lines),
        parse_mode="HTML",
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


async def _daily_balance_report_loop(bot: Bot, report_error: ErrorReporter) -> None:
    while True:
        now = datetime.now(TZ)
        await asyncio.sleep(_daily_report_delay(now, NOMAD_DAILY_REPORT_TIME))
        try:
            await _send_daily_balance_report(bot)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            Logger.error("Daily balance report failed", exc_info=True)
            await report_error("daily_balance_report", error)


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

    async def notify(text: str) -> tuple[int, int]:
        message = await bot.send_message(
            chat_id=NOMAD_BOT_CHAT_ID,
            text=text,
            parse_mode="HTML",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        return message.chat.id, message.message_id

    async def edit_notify(chat_id: int, message_id: int, text: str) -> None:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
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
        edit_notify=edit_notify,
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

    daily_report_task = None
    if NOMAD_DAILY_REPORT_TIME and NOMAD_DAILY_REPORT_CHAT_ID:
        daily_report_task = asyncio.create_task(
            _daily_balance_report_loop(bot, report_error), name="daily-balance-report"
        )
        Logger.info(f"Daily balance report scheduled at {NOMAD_DAILY_REPORT_TIME} for chat {NOMAD_DAILY_REPORT_CHAT_ID}")

    try:
        await dp.start_polling(bot)
    finally:
        if collector_task:
            collector_task.cancel()
            with suppress(asyncio.CancelledError):
                await collector_task
        if daily_report_task:
            daily_report_task.cancel()
            with suppress(asyncio.CancelledError):
                await daily_report_task
        await close_db()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
