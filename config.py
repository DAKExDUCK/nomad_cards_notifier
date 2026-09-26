import json
import os
from datetime import datetime
from urllib.parse import urlparse

import dotenv
from pytz import timezone

from modules.utils.config_utils import get_from_env
from modules.utils.exceptions import ConfigFieldWrongType

dotenv.load_dotenv()


def _get_int_env(field: str, default: int) -> int:
    value = os.getenv(field)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError as error:
        raise ConfigFieldWrongType(field, value, int) from error


def _get_json_object_env(field: str, default: str) -> dict[str, str]:
    value = os.getenv(field, default)
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise ConfigFieldWrongType(field, value, dict) from error
    if not isinstance(parsed, dict) or not all(
        isinstance(key, str) and isinstance(item, str) for key, item in parsed.items()
    ):
        raise ConfigFieldWrongType(field, value, dict)
    return parsed


def _validate_url(field: str, value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigFieldWrongType(field, value, str)
    return value.rstrip("/")


TOKEN = str(get_from_env("TOKEN"))

RATE = 0.25

TZ_RAW = str(get_from_env("TZ", "Asia/Almaty"))
TZ = timezone(TZ_RAW)

# Database config
DB_USER = str(get_from_env("DB_USER", "postgres"))
DB_PASSWORD = str(get_from_env("DB_PASSWORD", "postgres"))
DB_HOST = str(get_from_env("DB_HOST", "localhost"))
DB_PORT = str(get_from_env("DB_PORT", "5432"))
DB_NAME = str(get_from_env("DB_NAME", "nomad_cards"))

DB_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Nomad fuel-card collector. It is disabled until explicitly configured.
NOMAD_COLLECTOR_ENABLED = os.getenv("NOMAD_COLLECTOR_ENABLED", "false").lower() == "true"
IS_TEST = os.getenv("IS_TEST", os.getenv("is_test", "false")).strip().lower() == "true"
NOMAD_TEST_BASE_URL = _validate_url("NOMAD_TEST_BASE_URL", os.getenv("NOMAD_TEST_BASE_URL", "http://127.0.0.1:8080"))
NOMAD_BASE_URL = (
    NOMAD_TEST_BASE_URL
    if IS_TEST
    else _validate_url("NOMAD_BASE_URL", os.getenv("NOMAD_BASE_URL", "https://ur.nomadoil.kz"))
)
NOMAD_USERNAME = os.getenv("NOMAD_USERNAME", "")
NOMAD_PASSWORD = os.getenv("NOMAD_PASSWORD", "")
NOMAD_CLID = os.getenv("NOMAD_CLID", "")
NOMAD_NOTIFY_CHAT_ID = os.getenv("NOMAD_NOTIFY_CHAT_ID", "")
NOMAD_BOT_CHAT_ID = _get_int_env("NOMAD_BOT_CHAT_ID", _get_int_env("NOMAD_NOTIFY_CHAT_ID", 0))
NOMAD_DAILY_REPORT_CHAT_ID = _get_int_env("NOMAD_DAILY_REPORT_CHAT_ID", 0)
NOMAD_DAILY_REPORT_TIME = os.getenv("NOMAD_DAILY_REPORT_TIME", "").strip()
if NOMAD_DAILY_REPORT_TIME:
    try:
        datetime.strptime(NOMAD_DAILY_REPORT_TIME, "%H:%M")
    except ValueError as error:
        raise ConfigFieldWrongType("NOMAD_DAILY_REPORT_TIME", NOMAD_DAILY_REPORT_TIME, str) from error
NOMAD_COLLECT_INTERVAL = _get_int_env("NOMAD_COLLECT_INTERVAL", 300)
if NOMAD_COLLECT_INTERVAL <= 0:
    raise ConfigFieldWrongType("NOMAD_COLLECT_INTERVAL", NOMAD_COLLECT_INTERVAL, int)
NOMAD_SALES_FROM = os.getenv("NOMAD_SALES_FROM", "") or None
NOMAD_SALES_TO = os.getenv("NOMAD_SALES_TO", "") or None
NOMAD_STATION_URLS = _get_json_object_env("NOMAD_STATION_URLS", "{}")
