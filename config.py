import os
import json
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
ENV_FILE = BASE_DIR / ".env"
CONFIG_FILE = BASE_DIR / "data" / "settings.json"
SESSIONS_DIR = BASE_DIR / "sessions"
EXPORTS_DIR = BASE_DIR / "exports"
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"

for d in [SESSIONS_DIR, EXPORTS_DIR, LOGS_DIR, DATA_DIR]:
    d.mkdir(parents=True, exist_ok=True)

load_dotenv(ENV_FILE)

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")


def get_api_credentials() -> tuple[str | None, str | None]:
    load_dotenv(ENV_FILE)
    return os.getenv("API_ID"), os.getenv("API_HASH")


def save_api_credentials(api_id: str, api_hash: str) -> None:
    with open(ENV_FILE, "w") as f:
        f.write(f"API_ID={api_id}\n")
        f.write(f"API_HASH={api_hash}\n")
    global API_ID, API_HASH
    API_ID = api_id
    API_HASH = api_hash


def load_settings() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return default_settings()


def save_settings(settings: dict) -> None:
    with open(CONFIG_FILE, "w") as f:
        json.dump(settings, f, indent=2)


def default_settings() -> dict:
    return {
        "daily_import_limit": 20,
        "daily_collection_limit": 500,
        "daily_message_limit": 30,
        "delay_min": 60,
        "delay_max": 120,
        "sessions_dir": str(SESSIONS_DIR),
        "exports_dir": str(EXPORTS_DIR),
        "logs_dir": str(LOGS_DIR),
        "language": "English",
        "notifications": True,
        "detailed_logging": True,
        "rotation_mode": "smart",
        "switch_after_ops": 5,
        "switch_after_minutes": 10,
        "security_level": "balanced",
    }
