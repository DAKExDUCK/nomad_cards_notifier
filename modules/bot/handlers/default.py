from aiogram import F, Router, types
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext

import global_vars
from config import RATE
from modules.bot.functions import count_active_user
from modules.bot.keyborads.default import main_menu, profile_btns, register_nomad_account_btn
from modules.bot.throttling import rate_limit
from modules.database import DatabaseService
from modules.logger import Logger


@rate_limit(limit=RATE)
@Logger.log_msg
async def start(message: types.Message, state: FSMContext):
    if not message.from_user:
        return

    user_id = message.from_user.id
    user = await DatabaseService.get_user(user_id)

    kb = None
    if not user:
        text = "Приветствую\! Я бот для быстрого и удобного получения нотификаций об операциях с топливными карточками Nomad АЗС\.\n\n"
        await message.answer(text, parse_mode="MarkdownV2")

        text = (
            "*Что я могу*:\n"
            "1\. Показывать *текущий баланс* на карточке\n"
            "2\. Операции по пополнению и использования карточки для заправки\n\n"
            "Все указанные функции *БЕСПЛАТНЫЕ*"
        )
        await message.answer(text, parse_mode="MarkdownV2")

        text = (
            "Чтобы начать пользоваться функционалом нужно выполнить следующие шаги:\n"
            "1\. Ввести данные *личного кабинета* \(логин и пароль\)\n"
            "2\. Дождаться подтверждения входа в кабинет\n"
            "3\. Настроить карточки для отслеживания и получать нотификации о всех операциях с ними"
        )
        kb = register_nomad_account_btn(kb)
    elif user.has_account():
        kb = profile_btns(kb)
        text = "Выберите и нажмите:"
    else:
        kb = register_nomad_account_btn(kb)

    await message.answer(text, reply_markup=kb.as_markup(), parse_mode="MarkdownV2")
    await state.clear()


@rate_limit(limit=RATE)
@Logger.log_msg
async def help_msg(message: types.Message, state: FSMContext):
    text = (
        "Я бот для быстрого и удобного получения нотификаций об операциях с топливными карточками Nomad АЗС\.\n\n"
        "*Что я могу*:\n"
        "1\. Показывать *текущий баланс* на карточке\n"
        "2\. Операции по пополнению и использования карточки для заправки\n\n"
        "Все указанные функции *БЕСПЛАТНЫЕ*\n\n"
        "Чтобы начать пользоваться функционалом нужно выполнить следующие шаги:\n"
        "1\. Ввести данные *личного кабинета* \(логин и пароль\)\n"
        "2\. Дождаться подтверждения входа в кабинет\n"
        "3\. Настроить карточки для отслеживания и получать нотификации о всех операциях с ними\n\n"
        "Если у вас остались вопросы, вы можете обратиться в поддержку по электронной почте: example@example\.com"
    )
    kb = main_menu()

    await message.answer(text, reply_markup=kb.as_markup(), parse_mode="MarkdownV2")
    await state.clear()


@rate_limit(limit=RATE)
@count_active_user
@Logger.log_msg
async def profile(query: types.CallbackQuery):
    if not query.message:
        return
    if isinstance(query.message, types.InaccessibleMessage):
        return
    if not query.data:
        return

    user_id = query.from_user.id
    user = await DatabaseService.get_user(user_id)
    if not user:
        return

    text = ""
    text += f"User ID: `{user_id}`\n"

    await query.message.edit_text(
        text, reply_markup=profile_btns().as_markup(), parse_mode="MarkdownV2", disable_web_page_preview=True
    )


@rate_limit(limit=RATE)
@count_active_user
@Logger.log_msg
async def back_to_main_menu(query: types.CallbackQuery, state: FSMContext):
    if not query.message:
        return
    if isinstance(query.message, types.InaccessibleMessage):
        return
    if not query.data:
        return

    user_id = query.from_user.id
    user = await DatabaseService.get_user(user_id)

    kb = None
    if not user or not user.has_account():
        text = "Приветствую\! Я бот для быстрого и удобного получения нотификаций об операциях с топливными карточками Nomad АЗС\.\n\n"
        kb = register_nomad_account_btn(kb)
    else:
        if user.has_account():
            kb = profile_btns(kb)
        else:
            kb = register_nomad_account_btn(kb)

        text = "Выберите и нажмите:"

    await query.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="MarkdownV2")
    await state.clear()


@rate_limit(limit=RATE)
@count_active_user
async def delete_msg(query: types.CallbackQuery):
    if not query.message:
        return
    if isinstance(query.message, types.InaccessibleMessage):
        return
    if not query.data:
        return

    try:
        await global_vars.bot.delete_message(query.message.chat.id, query.message.message_id)
        await query.answer()
    except Exception:
        await query.answer("Ошибка!")


def register_handlers_default(router: Router):
    router.message.register(start, Command("start"))
    router.message.register(help_msg, Command("help"))

    router.callback_query.register(back_to_main_menu, F.func(lambda c: c.data == "main_menu"))
    router.callback_query.register(profile, F.func(lambda c: c.data == "profile"))

    router.callback_query.register(delete_msg, F.func(lambda c: c.data == "delete"))
