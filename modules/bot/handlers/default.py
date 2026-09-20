from html import escape
import re
from datetime import datetime, timezone

from aiogram import F, Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import LinkPreviewOptions

from config import NOMAD_BOT_CHAT_ID, NOMAD_STATION_URLS, TZ
from modules.bot.keyborads.default import balance_keyboard, card_details_keyboard, cards_keyboard
from modules.database import DatabaseService
from modules.logger import Logger


def _allowed(chat_id: int) -> bool:
    return NOMAD_BOT_CHAT_ID != 0 and chat_id == NOMAD_BOT_CHAT_ID


def _format_balance(balance: str | None) -> str:
    return f"{balance} л" if balance else "не указан"


def _format_updated_at(updated_at: datetime | None) -> str:
    if not updated_at:
        return "время неизвестно"
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return f"{updated_at.astimezone(TZ):%d.%m.%Y %H:%M}"


def _log_bot_error(context: str) -> None:
    Logger.error(f"Bot data request failed: {context}", exc_info=True)


def _is_message_not_modified(error: TelegramBadRequest) -> bool:
    return "message is not modified" in str(error)


def _cards_selection_text() -> str:
    return (
        "💳 <b>Ваши карты</b>\n\n"
        "Выберите карту, чтобы посмотреть остаток и последние операции:"
    )


def _station_link(station: str | None) -> str:
    if not station:
        return "АЗС не указана"
    station_name = escape(station)
    normalized_name = re.sub(r"\s+", " ", station.strip()).casefold()
    station_url = next(
        (
            url
            for name, url in NOMAD_STATION_URLS.items()
            if re.sub(r"\s+", " ", str(name).strip()).casefold() == normalized_name
        ),
        None,
    )
    if not station_url:
        return station_name
    return f'<a href="{escape(str(station_url), quote=True)}">{station_name}</a>'


def _operation_text(operation) -> str:
    is_income = operation.operation_type == "1"
    operation_type = "Пополнение" if is_income else "Заправка"
    operation_icon = "➕" if is_income else "⛽"
    movement = (
        f"{operation.quantity} л"
        if operation.quantity
        else f"{operation.amount} ₸"
        if operation.amount
        else "данные об объёме не указаны"
    )
    date_text = operation.occurred_at or "дата не указана"
    if operation.occurred_at:
        date_text = f"{date_text}"
    station_text = f"\n  📍 {_station_link(operation.station)}"
    return (
        f"{operation_icon} <b>{escape(operation_type)}</b> · {escape(date_text)}\n"
        f"  {escape(operation.fuel or 'Топливо не указано')} · {escape(movement)}\n"
        f"  Остаток после операции: <b>{escape(_format_balance(operation.fuel_balance))}</b>"
        f"{station_text}\n"
    )


async def get_balance(message: types.Message) -> None:
    if not _allowed(message.chat.id):
        return
    try:
        cards = await DatabaseService.get_fuel_cards_with_balances()
        if not cards:
            await message.answer("Карточки пока не загружены.")
            return
        lines = ["⛽ <b>Баланс топлива</b>", ""]
        for card, balance in cards:
            lines.append(
                f"💳 <b>{escape(card.name)}</b>\n"
                f"   Остаток: <b>{escape(_format_balance(balance))}</b>"
            )
        updated_at = max((card.updated_at for card, _ in cards), default=None)
        lines.extend(("", f"Обновлено: {_format_updated_at(updated_at)}"))
        await message.answer(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=balance_keyboard().as_markup(),
        )
    except Exception:
        _log_bot_error("get_balance")
        await message.answer("Не удалось загрузить баланс. Попробуйте ещё раз позже.")


async def get_cards(message: types.Message) -> None:
    if not _allowed(message.chat.id):
        return
    try:
        cards = await DatabaseService.get_fuel_cards()
        if not cards:
            await message.answer("Карточки пока не загружены.")
            return
        await message.answer(
            _cards_selection_text(),
            parse_mode="HTML",
            reply_markup=cards_keyboard(cards).as_markup(),
        )
    except Exception:
        _log_bot_error("get_cards")
        await message.answer("Не удалось загрузить список карт. Попробуйте ещё раз позже.")


async def card_details(query: types.CallbackQuery) -> None:
    if not query.message or isinstance(query.message, types.InaccessibleMessage):
        return
    if not _allowed(query.message.chat.id) or not query.data:
        await query.answer()
        return
    parts = query.data.split(":")
    is_refresh = len(parts) == 3 and parts[1] == "refresh"
    try:
        card_id = int(parts[2] if is_refresh else parts[1])
    except (IndexError, ValueError):
        await query.answer("Некорректная карта", show_alert=True)
        return
    try:
        cards = await DatabaseService.get_fuel_cards()
        card = next((item for item in cards if item.id == card_id), None)
        if card is None:
            await query.answer("Карта не найдена", show_alert=True)
            return
        operations = await DatabaseService.get_card_operations(card.id)
        balance = await DatabaseService.get_card_balance(card.id)
        lines = [
            f"💳 <b>{escape(card.name)}</b>",
            f"⛽ Текущий остаток: <b>{escape(_format_balance(balance))}</b>",
            "",
            "🧾 <b>Последние операции</b>",
        ]
        if operations:
            lines.extend(_operation_text(operation) for operation in operations)
        else:
            lines.append("Пока операций нет.")
        await query.message.edit_text(
            "\n".join(lines),
            parse_mode="HTML",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
            reply_markup=card_details_keyboard(card.id).as_markup(),
        )
        await query.answer("Данные обновлены" if is_refresh else None)
    except TelegramBadRequest as error:
        if _is_message_not_modified(error):
            await query.answer("Данные карты уже актуальны")
            return
        _log_bot_error(f"card_details:{card_id}")
        await query.answer("Не удалось загрузить данные карты", show_alert=True)
    except Exception:
        _log_bot_error(f"card_details:{card_id}")
        await query.answer("Не удалось загрузить данные карты", show_alert=True)


async def cards_back(query: types.CallbackQuery) -> None:
    if not query.message or isinstance(query.message, types.InaccessibleMessage):
        return
    if not _allowed(query.message.chat.id):
        await query.answer()
        return
    await _show_cards(query)


async def _show_cards(query: types.CallbackQuery) -> None:
    try:
        cards = await DatabaseService.get_fuel_cards()
        if not cards:
            await query.message.edit_text("Карточки пока не загружены.")
        else:
            await query.message.edit_text(
                _cards_selection_text(),
                parse_mode="HTML",
                reply_markup=cards_keyboard(cards).as_markup(),
            )
        await query.answer()
    except TelegramBadRequest as error:
        if _is_message_not_modified(error):
            await query.answer("Список уже актуален")
            return
        _log_bot_error("show_cards")
        await query.answer("Не удалось загрузить список карт", show_alert=True)
    except Exception:
        _log_bot_error("show_cards")
        await query.answer("Не удалось загрузить список карт", show_alert=True)


async def refresh_balance(query: types.CallbackQuery) -> None:
    if not query.message or isinstance(query.message, types.InaccessibleMessage):
        return
    if not _allowed(query.message.chat.id):
        await query.answer()
        return
    try:
        cards = await DatabaseService.get_fuel_cards_with_balances()
        if not cards:
            await query.message.edit_text("Карточки пока не загружены.")
            await query.answer()
            return
        lines = ["⛽ <b>Баланс топлива</b>", ""]
        for card, balance in cards:
            lines.append(
                f"💳 <b>{escape(card.name)}</b>\n"
                f"   Остаток: <b>{escape(_format_balance(balance))}</b>"
            )
        updated_at = max((card.updated_at for card, _ in cards), default=None)
        lines.extend(("", f"Обновлено: {_format_updated_at(updated_at)}"))
        await query.message.edit_text(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=balance_keyboard().as_markup(),
        )
        await query.answer("Баланс обновлён")
    except TelegramBadRequest as error:
        if _is_message_not_modified(error):
            await query.answer("Баланс уже актуален")
            return
        _log_bot_error("refresh_balance")
        await query.answer("Не удалось обновить баланс", show_alert=True)
    except Exception:
        _log_bot_error("refresh_balance")
        await query.answer("Не удалось обновить баланс", show_alert=True)


async def refresh_cards(query: types.CallbackQuery) -> None:
    if not query.message or isinstance(query.message, types.InaccessibleMessage):
        return
    if not _allowed(query.message.chat.id):
        await query.answer()
        return
    await _show_cards(query)


def register_handlers_default(router: Router) -> None:
    router.message.register(get_balance, Command("get_balance"))
    router.message.register(get_cards, Command("get_cards"))
    router.callback_query.register(refresh_balance, F.data == "balance:refresh")
    router.callback_query.register(refresh_cards, F.data == "cards:refresh")
    router.callback_query.register(cards_back, F.data == "cards:back")
    router.callback_query.register(card_details, F.data.startswith("card:"))
