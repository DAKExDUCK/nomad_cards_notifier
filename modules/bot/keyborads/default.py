from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu(kb: InlineKeyboardBuilder | None = None) -> InlineKeyboardBuilder:
    if kb is None:
        kb = InlineKeyboardBuilder()

    kb.row(InlineKeyboardButton(text="Назад", callback_data="main_menu"))

    return kb


def register_nomad_account_btn(kb: InlineKeyboardBuilder | None = None) -> InlineKeyboardBuilder:
    if kb is None:
        kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="Зарегестрировать аккаунт Nomad", callback_data="register"))

    return kb


def profile_btns(kb: InlineKeyboardBuilder | None = None) -> InlineKeyboardBuilder:
    if kb is None:
        kb = InlineKeyboardBuilder()

    settings_btn = InlineKeyboardButton(text="⚙️", callback_data="settings")
    profile_btn = InlineKeyboardButton(text="👤", callback_data="profile")
    kb.row(settings_btn, profile_btn)

    return kb
