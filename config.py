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
    base = DEFAULT_SETTINGS.copy() if "DEFAULT_SETTINGS" in dir() else {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                loaded = json.load(f)
                base.update(loaded)
                return base
        except Exception:
            pass
    return base if base else default_settings()


def save_settings(settings: dict) -> None:
    with open(CONFIG_FILE, "w") as f:
        json.dump(settings, f, indent=2)


DEFAULT_SETTINGS: dict = {
    "add_limit":             20,
    "scrape_limit":          500,
    "msg_limit":             30,
    "delay_min":             60,
    "delay_max":             120,
    "sessions_dir":          str(SESSIONS_DIR),
    "exports_dir":           str(EXPORTS_DIR),
    "logs_dir":              str(LOGS_DIR),
    "language":              "English",
    "notifications_enabled": True,
    "verbose_log":           True,
    "rotation_mode":         "smart",
    "switch_trigger":        "ops",
    "switch_after_ops":      5,
    "switch_after_minutes":  10,
    "smart_limit_level":     "balanced",
    "night_mode":            False,
    "auto_backup_freq":      "disabled",
    "auto_backup_upload":    False,
    "log_cleanup":           "weekly",
    "proxy_auto_rotate":     False,
    "proxy_rotate_on_fail":  True,
    "proxy_notify_fail":     True,
    "active_start_hour":     8,
    "active_end_hour":       23,
    "rest_min_minutes":      5,
    "rest_max_minutes":      15,
}


def default_settings() -> dict:
    return DEFAULT_SETTINGS.copy()
