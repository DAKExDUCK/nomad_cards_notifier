from aiogram.utils.keyboard import InlineKeyboardBuilder


def balance_keyboard() -> InlineKeyboardBuilder:
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔄 Обновить", callback_data="balance:refresh")
    keyboard.button(text="💳 К картам", callback_data="cards:back")
    keyboard.adjust(1)
    return keyboard


def cards_keyboard(cards) -> InlineKeyboardBuilder:
    keyboard = InlineKeyboardBuilder()
    for card in cards:
        keyboard.button(text=f"💳 {card.name}", callback_data=f"card:{card.id}")
    keyboard.button(text="🔄 Обновить список", callback_data="cards:refresh")
    keyboard.adjust(1)
    return keyboard


def card_details_keyboard(card_id: int) -> InlineKeyboardBuilder:
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔄 Обновить", callback_data=f"card:refresh:{card_id}")
    keyboard.button(text="⬅️ Назад", callback_data="cards:back")
    keyboard.adjust(1)
    return keyboard
