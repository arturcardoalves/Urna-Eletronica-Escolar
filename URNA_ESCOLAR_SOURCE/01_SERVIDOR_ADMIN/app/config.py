from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
_data_env = os.getenv("URNA_DATA_DIR", "").strip()
DATA_DIR = Path(_data_env).expanduser().resolve() if _data_env else (BASE_DIR / "data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
_db_env = os.getenv("URNA_DB_PATH", "").strip()
DB_PATH = Path(_db_env).expanduser().resolve() if _db_env else (DATA_DIR / "urna_escolar.db")
KEY_DIR = DATA_DIR / "keys"
PUBLIC_KEY_PATH = KEY_DIR / "election_public.pem"
PRIVATE_KEY_PATH = KEY_DIR / "election_private.pem"
PRIVATE_KEY_PASSWORD_PATH = KEY_DIR / "election_private.secret"
APP_VERSION = "2.3.0"
MAX_URNS = 3
