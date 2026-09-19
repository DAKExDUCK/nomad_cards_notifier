from aiogram import F, Router, types

from modules.bot.functions import count_active_user
from modules.bot.keyborads.default import main_menu
from modules.logger import Logger


@count_active_user
async def last_handler(message: types.Message):
    await message.reply(
        "Пожалуйста, строго следуйте инструкции или же используйте команды",
        reply_markup=main_menu().as_markup(),
    )


async def all_errors_from_msg(event: types.ErrorEvent, message: types.Message):
    await message.answer("Ошибка, если у Вас есть проблемы используйте /help")
    chat_id = message.chat.id
    text = message.text
    Logger.error(f"{chat_id} {text} {event.exception}", exc_info=True)


async def all_errors_from_callback_query(event: types.ErrorEvent, callback_query: types.CallbackQuery):
    try:
        await callback_query.answer("Ошибка, если у Вас есть проблемы используйте /help")
    except:
        if isinstance(callback_query.message, types.Message):
            await callback_query.message.answer("Ошибка, если у Вас есть проблемы используйте /help")

    chat_id = callback_query.from_user.id
    text = callback_query.data
    Logger.error(f"{chat_id} {text} {event.exception}", exc_info=True)


def register_handlers_errors(router: Router):
    router.errors.register(all_errors_from_msg, F.update.message.as_("message"))
    router.errors.register(all_errors_from_callback_query, F.update.callback_query.as_("callback_query"))
