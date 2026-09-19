import math
import re
from datetime import datetime, timedelta
from functools import wraps

from aiogram import types

from modules.database import DatabaseService

user_timers: dict[int, datetime] = {}


def escape_md(value: str | int | float | datetime | timedelta | None) -> str:
    text = str(value)
    symbols = ("_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!")
    for sym in symbols:
        text = text.replace(sym, f"\{sym}")

    return text


def truncate_string(input_str, max_length=15) -> str:
    if len(input_str) > max_length:
        truncated_str = input_str[: max_length - 3] + "..."
        return truncated_str
    return input_str


def truncate_string_in_center(input_str, max_length=15):
    if len(input_str) <= max_length:
        return input_str

    trunc_length = max_length - 3  # 3 for the '...'
    if trunc_length <= 0:
        return input_str  # If max_length is too short to truncate

    start_part = input_str[: trunc_length // 2]
    end_part = input_str[-(trunc_length // 2) :]

    return f"{start_part}...{end_part}"


def convert_size(size_bytes):
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    size = round(size_bytes / p, 1)
    return f"{size} {size_name[i]}"


def count_active_user(func):
    @wraps(func)
    async def wrapper(query: types.Message | types.CallbackQuery, *args, **kwargs):
        res = await func(query, *args, **kwargs)

        if query.from_user:
            user_id = query.from_user.id
            if user_id in user_timers:
                if user_timers[user_id] > datetime.now() + timedelta(hours=3):
                    await DatabaseService.set_user_active(user_id)
                    user_timers[user_id] = datetime.now()
            if user_id not in user_timers:
                await DatabaseService.set_user_active(user_id)
                user_timers[user_id] = datetime.now()

        return res

    return wrapper


async def delete_msg(*msgs: types.Message):
    for msg in reversed(msgs):
        try:
            await msg.delete()
        except Exception:
            ...


def chop_microseconds(delta: timedelta) -> timedelta:
    return delta - timedelta(microseconds=delta.microseconds)


def check_is_valid_mail(mail):
    regex = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"
    return re.match(regex, mail) is not None
