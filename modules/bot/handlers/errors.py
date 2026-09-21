from functools import partial

from aiogram import F, Router, types

from modules.logger import Logger


async def last_handler(message: types.Message):
    await message.reply("Используйте команды /get_balance или /get_cards.")


async def _report_error(error_reporter, context: str, error: BaseException) -> None:
    if error_reporter:
        try:
            await error_reporter(context, error)
        except Exception:
            Logger.error("Failed to send bot error report", exc_info=True)


async def all_errors_from_msg(event: types.ErrorEvent, message: types.Message, error_reporter=None):
    await message.answer("Не удалось выполнить запрос. Попробуйте ещё раз позже.")
    chat_id = message.chat.id
    text = message.text
    Logger.error(f"{chat_id} {text} {event.exception}", exc_info=True)
    await _report_error(error_reporter, "telegram_message_handler", event.exception)


async def all_errors_from_callback_query(
    event: types.ErrorEvent, callback_query: types.CallbackQuery, error_reporter=None
):
    try:
        await callback_query.answer("Не удалось выполнить запрос. Попробуйте ещё раз.")
    except:
        if isinstance(callback_query.message, types.Message):
            await callback_query.message.answer("Не удалось выполнить запрос. Попробуйте ещё раз позже.")

    chat_id = callback_query.from_user.id
    text = callback_query.data
    Logger.error(f"{chat_id} {text} {event.exception}", exc_info=True)
    await _report_error(error_reporter, "telegram_callback_handler", event.exception)


def register_handlers_errors(router: Router, error_reporter=None):
    router.errors.register(
        partial(all_errors_from_msg, error_reporter=error_reporter),
        F.update.message.as_("message"),
    )
    router.errors.register(
        partial(all_errors_from_callback_query, error_reporter=error_reporter),
        F.update.callback_query.as_("callback_query"),
    )
