from aiogram import Bot, Dispatcher, Router
from aiogram.types import BotCommand, BotCommandScopeChat

from config import NOMAD_BOT_CHAT_ID, RATE
from modules.bot.handlers.errors import register_handlers_errors

from .handlers.default import register_handlers_default
from .throttling import ThrottlingMiddleware


async def set_commands(bot: Bot):
    await bot.delete_my_commands()
    if not NOMAD_BOT_CHAT_ID:
        return
    commands = [
        BotCommand(command="get_balance", description="Показать баланс карт"),
        BotCommand(command="get_cards", description="Выбрать карту"),
    ]
    await bot.set_my_commands(commands, BotCommandScopeChat(chat_id=NOMAD_BOT_CHAT_ID))


async def register_bot_handlers(bot: Bot, dp: Dispatcher):
    dp.message.middleware(ThrottlingMiddleware(limit=RATE, key_prefix="antiflood"))
    dp.callback_query.middleware(ThrottlingMiddleware(limit=RATE, key_prefix="antiflood"))

    bot_router = Router()
    register_handlers_default(bot_router)

    errors_router = Router()
    register_handlers_errors(errors_router)

    dp.include_router(bot_router)
    dp.include_router(errors_router)

    await set_commands(bot)
