import dotenv
from pytz import timezone

from modules.utils.config_utils import get_from_env

dotenv.load_dotenv()


TOKEN = str(get_from_env("TOKEN"))

RATE = 0.25

TEST = bool(get_from_env(field="TEST", default="0", value_type=int))

TZ_RAW = str(get_from_env("TZ", "Asia/Aqtobe"))
TZ = timezone(TZ_RAW)
