from aiogram import F, Router, types

from modules.logger import Logger


async def last_handler(message: types.Message):
    await message.reply("Используйте команды /get_balance или /get_cards.")


async def all_errors_from_msg(event: types.ErrorEvent, message: types.Message):
    await message.answer("Не удалось выполнить запрос. Попробуйте ещё раз позже.")
    chat_id = message.chat.id
    text = message.text
    Logger.error(f"{chat_id} {text} {event.exception}", exc_info=True)


async def all_errors_from_callback_query(event: types.ErrorEvent, callback_query: types.CallbackQuery):
    try:
        await callback_query.answer("Не удалось выполнить запрос. Попробуйте ещё раз.")
    except:
        if isinstance(callback_query.message, types.Message):
            await callback_query.message.answer("Не удалось выполнить запрос. Попробуйте ещё раз позже.")

    chat_id = callback_query.from_user.id
    text = callback_query.data
    Logger.error(f"{chat_id} {text} {event.exception}", exc_info=True)


def register_handlers_errors(router: Router):
    router.errors.register(all_errors_from_msg, F.update.message.as_("message"))
    router.errors.register(all_errors_from_callback_query, F.update.callback_query.as_("callback_query"))
