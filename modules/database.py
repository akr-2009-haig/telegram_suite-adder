import json
from pathlib import Path
from datetime import datetime
from config import DATA_DIR
from modules.utils import read_json, write_json, now_str

ACCOUNTS_FILE = DATA_DIR / "accounts.json"
PROXIES_FILE  = DATA_DIR / "proxies.json"
BLACKLIST_FILE = DATA_DIR / "blacklist.json"
STATS_FILE     = DATA_DIR / "stats.json"
CAMPAIGNS_FILE = DATA_DIR / "campaigns.json"


# ─── Accounts ───────────────────────────────────────────────────────────────

def load_accounts() -> list[dict]:
    return read_json(ACCOUNTS_FILE, [])


def save_accounts(accounts: list[dict]):
    write_json(ACCOUNTS_FILE, accounts)


def get_account(phone: str) -> dict | None:
    for acc in load_accounts():
        if acc["phone"] == phone:
            return acc
    return None


def add_account(account: dict):
    accounts = load_accounts()
    for i, a in enumerate(accounts):
        if a["phone"] == account["phone"]:
            accounts[i] = account
            save_accounts(accounts)
            return
    accounts.append(account)
    save_accounts(accounts)


def remove_account(phone: str) -> bool:
    accounts = load_accounts()
    new = [a for a in accounts if a["phone"] != phone]
    if len(new) < len(accounts):
        save_accounts(new)
        return True
    return False


def update_account(phone: str, updates: dict):
    accounts = load_accounts()
    for i, a in enumerate(accounts):
        if a["phone"] == phone:
            accounts[i].update(updates)
            accounts[i]["last_used"] = now_str()
            save_accounts(accounts)
            return True
    return False


def get_active_accounts() -> list[dict]:
    return [a for a in load_accounts() if a.get("status") == "active"]


def increment_account_counter(phone: str, counter: str, amount: int = 1):
    accounts = load_accounts()
    for i, a in enumerate(accounts):
        if a["phone"] == phone:
            key = f"today_{counter}"
            accounts[i][key] = accounts[i].get(key, 0) + amount
            save_accounts(accounts)
            return


def reset_daily_counters():
    accounts = load_accounts()
    for a in accounts:
        a["today_imports"] = 0
        a["today_collections"] = 0
        a["today_messages"] = 0
    save_accounts(accounts)


# ─── Proxies ────────────────────────────────────────────────────────────────

def load_proxies() -> list[dict]:
    return read_json(PROXIES_FILE, [])


def save_proxies(proxies: list[dict]):
    write_json(PROXIES_FILE, proxies)


def add_proxy(proxy: dict):
    proxies = load_proxies()
    proxy["id"] = len(proxies) + 1
    proxy["added_at"] = now_str()
    proxy["status"] = "unknown"
    proxies.append(proxy)
    save_proxies(proxies)


def remove_proxy(proxy_id: int):
    proxies = [p for p in load_proxies() if p.get("id") != proxy_id]
    save_proxies(proxies)


def update_proxy(proxy_id: int, updates: dict):
    proxies = load_proxies()
    for i, p in enumerate(proxies):
        if p.get("id") == proxy_id:
            proxies[i].update(updates)
            save_proxies(proxies)
            return True
    return False


def get_unassigned_proxies() -> list[dict]:
    assigned_ids = {a.get("proxy_id") for a in load_accounts() if a.get("proxy_id")}
    return [p for p in load_proxies() if p["id"] not in assigned_ids and p.get("status") == "alive"]


# ─── Blacklist ───────────────────────────────────────────────────────────────

def load_blacklist() -> list[str]:
    return read_json(BLACKLIST_FILE, [])


def add_to_blacklist(user_id: str):
    bl = load_blacklist()
    if user_id not in bl:
        bl.append(user_id)
        write_json(BLACKLIST_FILE, bl)


def remove_from_blacklist(user_id: str):
    bl = [x for x in load_blacklist() if x != user_id]
    write_json(BLACKLIST_FILE, bl)


def is_blacklisted(user_id: str) -> bool:
    return str(user_id) in load_blacklist()


# ─── Stats ───────────────────────────────────────────────────────────────────

def load_stats() -> dict:
    return read_json(STATS_FILE, {})


def log_stat(category: str, key: str, value):
    stats = load_stats()
    today = datetime.now().strftime("%Y-%m-%d")
    stats.setdefault(today, {}).setdefault(category, {})[key] = value
    write_json(STATS_FILE, stats)


def increment_stat(category: str, key: str, amount: int = 1):
    stats = load_stats()
    today = datetime.now().strftime("%Y-%m-%d")
    stats.setdefault(today, {}).setdefault(category, {})
    stats[today][category][key] = stats[today][category].get(key, 0) + amount
    write_json(STATS_FILE, stats)


def get_today_stats() -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    return load_stats().get(today, {})


# ─── Campaigns ───────────────────────────────────────────────────────────────

def load_campaigns() -> list[dict]:
    return read_json(CAMPAIGNS_FILE, [])


def save_campaigns(campaigns: list[dict]):
    write_json(CAMPAIGNS_FILE, campaigns)


def add_campaign(campaign: dict):
    campaigns = load_campaigns()
    campaign["id"] = len(campaigns) + 1
    campaign["created_at"] = now_str()
    campaign["status"] = "pending"
    campaigns.append(campaign)
    save_campaigns(campaigns)
    return campaign["id"]
