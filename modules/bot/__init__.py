from aiogram import Bot, Dispatcher, Router
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats

from config import RATE
from modules.bot.filters.chat_type import ChatTypeFilter
from modules.bot.handlers.errors import register_handlers_errors

from .handlers.default import register_handlers_default
from .throttling import ThrottlingMiddleware


async def set_commands(bot: Bot):
    # Set commands for private chats
    commands = [
        BotCommand(command="/start", description="Start | Menu"),
        BotCommand(command="/help", description="Help | Commands"),
    ]
    await bot.set_my_commands(commands, BotCommandScopeAllPrivateChats())


async def register_bot_handlers(bot: Bot, dp: Dispatcher):
    dp.message.middleware(ThrottlingMiddleware(limit=RATE, key_prefix="antiflood"))
    dp.callback_query.middleware(ThrottlingMiddleware(limit=RATE, key_prefix="antiflood"))

    # group_chats_router = Router()
    # group_chats_router.message.filter(ChatTypeFilter(chat_type=["group", "supergroup"]))
    # group_chats_router.callback_query.filter(ChatTypeFilter(chat_type=["group", "supergroup"]))
    # register_handlers_groups(group_chats_router)

    personal_chats_router = Router()
    personal_chats_router.message.filter(ChatTypeFilter(chat_type=["sender", "private"]))
    personal_chats_router.callback_query.filter(ChatTypeFilter(chat_type=["sender", "private"]))
    register_handlers_default(personal_chats_router)

    errors_router = Router()
    register_handlers_errors(errors_router)

    dp.include_router(personal_chats_router)
    # dp.include_router(group_chats_router)
    dp.include_router(errors_router)

    await set_commands(bot)
