import dotenv
import json
import os
from pytz import timezone

from modules.utils.config_utils import get_from_env

dotenv.load_dotenv()


TOKEN = str(get_from_env("TOKEN"))

RATE = 0.25

TZ_RAW = str(get_from_env("TZ", "Asia/Aqtobe"))
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
NOMAD_BASE_URL = os.getenv("NOMAD_BASE_URL", "https://ur.nomadoil.kz")
NOMAD_USERNAME = os.getenv("NOMAD_USERNAME", "")
NOMAD_PASSWORD = os.getenv("NOMAD_PASSWORD", "")
NOMAD_CLID = os.getenv("NOMAD_CLID", "")
NOMAD_NOTIFY_CHAT_ID = os.getenv("NOMAD_NOTIFY_CHAT_ID", "")
NOMAD_BOT_CHAT_ID = int(os.getenv("NOMAD_BOT_CHAT_ID", NOMAD_NOTIFY_CHAT_ID or "0"))
NOMAD_COLLECT_INTERVAL = int(os.getenv("NOMAD_COLLECT_INTERVAL", "300"))
NOMAD_SALES_FROM = os.getenv("NOMAD_SALES_FROM", "") or None
NOMAD_SALES_TO = os.getenv("NOMAD_SALES_TO", "") or None
NOMAD_STATION_URLS = json.loads(os.getenv("NOMAD_STATION_URLS", "{}"))
