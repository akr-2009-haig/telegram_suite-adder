import json
from pathlib import Path
from datetime import datetime
from config import DATA_DIR
from modules.utils import read_json, write_json, now_str

ACCOUNTS_FILE   = DATA_DIR / "accounts.json"
PROXIES_FILE    = DATA_DIR / "proxies.json"
BLACKLIST_FILE  = DATA_DIR / "blacklist.json"
STATS_FILE      = DATA_DIR / "stats.json"
CAMPAIGNS_FILE  = DATA_DIR / "campaigns.json"
SCHEDULES_FILE  = DATA_DIR / "schedules.json"
NOTIF_LOG_FILE  = DATA_DIR / "notifications_log.json"
TEMPLATES_FILE  = DATA_DIR / "message_templates.json"
AUTOREPLY_FILE  = DATA_DIR / "auto_replies.json"


# ─── Accounts ────────────────────────────────────────────────────────────────
def load_accounts() -> list:
    return read_json(ACCOUNTS_FILE, [])

def save_accounts(accounts: list):
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

def get_active_accounts() -> list:
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
        a["today_imports"]     = 0
        a["today_collections"] = 0
        a["today_messages"]    = 0
    save_accounts(accounts)

# ─── Proxies ─────────────────────────────────────────────────────────────────
def load_proxies() -> list:
    return read_json(PROXIES_FILE, [])

def save_proxies(proxies: list):
    write_json(PROXIES_FILE, proxies)

def add_proxy(proxy: dict):
    proxies = load_proxies()
    proxy["id"]       = len(proxies) + 1
    proxy["added_at"] = now_str()
    proxy["status"]   = "unknown"
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

def get_unassigned_proxies() -> list:
    assigned_ids = {a.get("proxy_id") for a in load_accounts() if a.get("proxy_id")}
    return [p for p in load_proxies() if p["id"] not in assigned_ids and p.get("status") == "alive"]

# ─── Blacklist ────────────────────────────────────────────────────────────────
def load_blacklist() -> list:
    return read_json(BLACKLIST_FILE, [])

def add_to_blacklist(user_id: str):
    bl = load_blacklist()
    if str(user_id) not in bl:
        bl.append(str(user_id))
        write_json(BLACKLIST_FILE, bl)

def remove_from_blacklist(user_id: str):
    bl = [x for x in load_blacklist() if x != str(user_id)]
    write_json(BLACKLIST_FILE, bl)

def is_blacklisted(user_id: str) -> bool:
    return str(user_id) in load_blacklist()

# ─── Stats ────────────────────────────────────────────────────────────────────
def load_stats() -> dict:
    return read_json(STATS_FILE, {})

def increment_stat(category: str, key: str, amount: int = 1):
    stats = load_stats()
    today = datetime.now().strftime("%Y-%m-%d")
    stats.setdefault(today, {}).setdefault(category, {})
    stats[today][category][key] = stats[today][category].get(key, 0) + amount
    write_json(STATS_FILE, stats)

def get_today_stats() -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    return load_stats().get(today, {})

def get_week_stats() -> dict:
    from datetime import timedelta
    stats = load_stats()
    result = {}
    today = datetime.now()
    for i in range(7):
        day = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        result[day] = stats.get(day, {})
    return result

# ─── Campaigns ───────────────────────────────────────────────────────────────
def load_campaigns() -> list:
    return read_json(CAMPAIGNS_FILE, [])

def save_campaigns(campaigns: list):
    write_json(CAMPAIGNS_FILE, campaigns)

def add_campaign(campaign: dict):
    campaigns = load_campaigns()
    campaign["id"]         = len(campaigns) + 1
    campaign["created_at"] = now_str()
    campaign["status"]     = "pending"
    campaigns.append(campaign)
    save_campaigns(campaigns)
    return campaign["id"]

# ─── Schedules ───────────────────────────────────────────────────────────────
def load_schedules() -> list:
    return read_json(SCHEDULES_FILE, [])

def save_schedules(schedules: list):
    write_json(SCHEDULES_FILE, schedules)

def add_schedule(task: dict):
    tasks = load_schedules()
    task["id"]         = len(tasks) + 1
    task["created_at"] = now_str()
    task["status"]     = "pending"
    task["last_run"]   = None
    task["run_count"]  = 0
    tasks.append(task)
    save_schedules(tasks)
    return task["id"]

def remove_schedule(task_id: int):
    tasks = [t for t in load_schedules() if t.get("id") != task_id]
    save_schedules(tasks)

def update_schedule(task_id: int, updates: dict):
    tasks = load_schedules()
    for i, t in enumerate(tasks):
        if t.get("id") == task_id:
            tasks[i].update(updates)
            save_schedules(tasks)
            return True
    return False

# ─── Notification Log ─────────────────────────────────────────────────────────
def load_notif_log() -> list:
    return read_json(NOTIF_LOG_FILE, [])

def add_notification(notif_type: str, message: str, level: str = "info"):
    log = load_notif_log()
    log.append({"type": notif_type, "message": message, "level": level, "time": now_str(), "read": False})
    write_json(NOTIF_LOG_FILE, log[-500:])

def mark_notifications_read():
    log = load_notif_log()
    for n in log:
        n["read"] = True
    write_json(NOTIF_LOG_FILE, log)

def get_unread_notifications() -> list:
    return [n for n in load_notif_log() if not n.get("read")]

# ─── Message Templates ────────────────────────────────────────────────────────
def load_templates() -> list:
    return read_json(TEMPLATES_FILE, [])

def save_templates(templates: list):
    write_json(TEMPLATES_FILE, templates)

def add_template(name: str, text: str, category: str = "general"):
    templates = load_templates()
    templates.append({"id": len(templates)+1, "name": name, "text": text,
                       "category": category, "created_at": now_str(), "used_count": 0})
    save_templates(templates)

def delete_template(template_id: int):
    save_templates([t for t in load_templates() if t.get("id") != template_id])

# ─── Auto-Reply Rules ─────────────────────────────────────────────────────────
def load_auto_replies() -> list:
    return read_json(AUTOREPLY_FILE, [])

def save_auto_replies(rules: list):
    write_json(AUTOREPLY_FILE, rules)

def add_auto_reply(rule: dict):
    rules = load_auto_replies()
    rule["id"]            = len(rules) + 1
    rule["created_at"]    = now_str()
    rule["enabled"]       = True
    rule["trigger_count"] = 0
    rules.append(rule)
    save_auto_replies(rules)
    return rule["id"]

def remove_auto_reply(rule_id: int):
    save_auto_replies([r for r in load_auto_replies() if r.get("id") != rule_id])

def toggle_auto_reply(rule_id: int):
    rules = load_auto_replies()
    for i, r in enumerate(rules):
        if r.get("id") == rule_id:
            rules[i]["enabled"] = not rules[i].get("enabled", True)
            save_auto_replies(rules)
            return rules[i]["enabled"]
    return None
