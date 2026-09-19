import dotenv
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
