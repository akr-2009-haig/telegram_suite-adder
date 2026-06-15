import asyncio
import csv
import json
import random
import time
from pathlib import Path
from datetime import datetime
from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError, UserPrivacyRestrictedError, UserAlreadyParticipantError,
    ChatWriteForbiddenError, PeerFloodError, UserNotMutualContactError,
    UserBannedInChannelError, InputUserDeactivatedError, ChatAdminRequiredError,
)
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.functions.messages import AddChatUserRequest

import config
from modules.utils import (
    console, print_header, print_success, print_error, print_warn,
    print_info, prompt, menu_choice, confirm, now_str, wait_countdown,
)
from modules.database import (
    load_accounts, get_active_accounts, increment_account_counter,
    load_proxies, is_blacklisted, increment_stat,
)

EXPORTS_DIR = config.EXPORTS_DIR
DATA_DIR    = config.DATA_DIR
PROGRESS_FILE = DATA_DIR / "import_progress.json"


def member_adder_menu():
    while True:
        print_header("📤  Member Adder", "Add members to target groups")
        choice = menu_choice([
            ("1", "📂  Import from Exported File (CSV)"),
            ("2", "✍️  Manual Import (Enter Usernames)"),
            ("3", "🔄  Resume Previous Import"),
            ("4", "📊  View Import Logs"),
        ])
        if choice == "1":
            asyncio.run(import_from_csv())
        elif choice == "2":
            asyncio.run(import_manual())
        elif choice == "3":
            asyncio.run(resume_import())
        elif choice == "4":
            view_import_logs()
        elif choice == "0":
            break


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _build_client(account: dict) -> TelegramClient:
    api_id, api_hash = config.get_api_credentials()
    session = str(config.SESSIONS_DIR / account["phone"])
    proxy = None
    if account.get("proxy_id"):
        for p in load_proxies():
            if p["id"] == account["proxy_id"]:
                try:
                    import socks
                    ptype = p.get("type", "socks5").lower()
                    pt = socks.SOCKS5 if "socks5" in ptype else (socks.SOCKS4 if "socks4" in ptype else socks.HTTP)
                    proxy = (pt, p["host"], int(p["port"]),
                             True, p.get("username") or None, p.get("password") or None)
                except Exception:
                    pass
                break
    return TelegramClient(session, int(api_id), api_hash, proxy=proxy)


def _load_csv(filepath: Path) -> list[dict]:
    members = []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            members.append(dict(row))
    return members


def _configure_import_settings() -> dict | None:
    console.print("\n  ─── Import Method ────────────────────────")
    console.print("  [1] 📲  Direct Import (Add to Group)")
    console.print("  [2] 📨  Send Invitation via Private Message")
    method = prompt("  Select", "1")

    console.print("\n  ─── Accounts to Use ──────────────────────")
    active = get_active_accounts()
    if not active:
        print_error("No active accounts available.")
        return None

    console.print(f"  [1] Single Account")
    console.print(f"  [2] Rotate Between All Active Accounts ({len(active)})  ⭐")
    console.print(f"  [3] Select Specific Accounts")
    acc_mode = prompt("  Select", "2")

    accounts = active
    if acc_mode == "1":
        for i, a in enumerate(active, 1):
            console.print(f"      [{i}] {a['phone']}")
        idx = int(prompt("  Account #", "1") or "1") - 1
        accounts = [active[idx]] if 0 <= idx < len(active) else [active[0]]
    elif acc_mode == "3":
        phones = prompt("  Enter phones (comma-separated)").split(",")
        accounts = [a for a in active if a["phone"].strip() in [p.strip() for p in phones]]

    console.print("\n  ─── Imports Per Account (before switch) ──")
    console.print("  [1]  5  (Very Safe)  ⭐")
    console.print("  [2] 10  (Safe)")
    console.print("  [3] 20  (Medium Risk)")
    console.print("  [4] Custom")
    lp = prompt("  Select", "1")
    per_acc = {"1": 5, "2": 10, "3": 20}.get(lp)
    if not per_acc:
        per_acc = int(prompt("  Custom amount", "5") or "5")

    console.print("\n  ─── Delay Between Imports ────────────────")
    console.print("  [1] 60–120s  (Safest)  ⭐")
    console.print("  [2] 30–60s   (Safe)")
    console.print("  [3] 15–30s   (Risky)")
    console.print("  [4] 5–15s    (Very Risky)")
    console.print("  [5] Custom")
    dc = prompt("  Select", "1")
    delays = {"1": (60, 120), "2": (30, 60), "3": (15, 30), "4": (5, 15)}
    if dc == "5":
        d_min = int(prompt("  Min seconds", "30") or "30")
        d_max = int(prompt("  Max seconds", "60") or "60")
        delay = (d_min, d_max)
    else:
        delay = delays.get(dc, (60, 120))

    console.print("\n  ─── Switch Delay ─────────────────────────")
    console.print("  [1] 5–10 min  ⭐   [2] 2–5 min   [3] 10–30 min   [4] Custom")
    sd = prompt("  Select", "1")
    switch_delays = {"1": (300, 600), "2": (120, 300), "3": (600, 1800)}
    switch_delay = switch_delays.get(sd, (300, 600))
    if sd == "4":
        sd_min = int(prompt("  Min minutes", "5") or "5") * 60
        sd_max = int(prompt("  Max minutes", "10") or "10") * 60
        switch_delay = (sd_min, sd_max)

    console.print("\n  ─── Daily Limit Per Account ──────────────")
    console.print("  [1] 20  ⭐   [2] 30   [3] 40   [4] 50   [5] Custom")
    dl = prompt("  Select", "1")
    daily_limits = {"1": 20, "2": 30, "3": 40, "4": 50}
    daily_limit = daily_limits.get(dl)
    if not daily_limit:
        daily_limit = int(prompt("  Custom limit", "20") or "20")

    return {
        "method":       method,
        "accounts":     accounts,
        "per_account":  per_acc,
        "delay":        delay,
        "switch_delay": switch_delay,
        "daily_limit":  daily_limit,
    }


def _print_summary(source: str, count: int, target: str, cfg: dict):
    est_daily = len(cfg["accounts"]) * cfg["daily_limit"]
    est_days  = max(1, count // est_daily) if est_daily else "?"
    console.print("\n  ┌─────────────────────────────────────────┐")
    console.print("  │         📋  Import Summary              │")
    console.print("  ├─────────────────────────────────────────┤")
    console.print(f"  │  Source    : {source[:30]}")
    console.print(f"  │  Members   : {count}")
    console.print(f"  │  Target    : {target[:30]}")
    console.print(f"  │  Method    : {'Direct Add' if cfg['method']=='1' else 'Invite Message'}")
    console.print(f"  │  Accounts  : {len(cfg['accounts'])} (rotating)")
    console.print(f"  │  Per Acc   : {cfg['per_account']} imports before switch")
    console.print(f"  │  Daily     : {cfg['daily_limit']} per account")
    console.print(f"  │  Delay     : {cfg['delay'][0]}–{cfg['delay'][1]}s")
    console.print(f"  │  Est. Daily: ~{est_daily} imports")
    console.print(f"  │  Est. Days : ~{est_days} days")
    console.print("  └─────────────────────────────────────────┘")


# ─── Core Import Loop ─────────────────────────────────────────────────────────

async def _run_import(members: list[dict], target_link: str, cfg: dict, source_name: str, start_from: int = 0):
    accounts = cfg["accounts"]
    per_acc   = cfg["per_account"]
    delay     = cfg["delay"]
    switch_delay = cfg["switch_delay"]
    daily_limit  = cfg["daily_limit"]
    method       = cfg["method"]

    acc_idx     = 0
    acc_ops     = 0
    total_ok    = 0
    total_skip  = 0
    total_fail  = 0

    client = _build_client(accounts[acc_idx])
    await client.connect()

    try:
        target = await client.get_entity(target_link.strip())
    except Exception as e:
        print_error(f"Cannot access target: {e}")
        await client.disconnect()
        input("\n  Press ENTER...")
        return

    console.print(f"\n  🚀 Starting import — [bold]{len(members) - start_from}[/bold] members to process\n")

    for i, member in enumerate(members[start_from:], start=start_from):
        current_acc = accounts[acc_idx]
        today_count = current_acc.get("today_imports", 0)

        # rotate on daily limit
        if today_count >= daily_limit:
            console.print(f"\n  💤 [yellow]{current_acc['phone']} daily limit reached ({daily_limit})[/yellow]")
            acc_idx = (acc_idx + 1) % len(accounts)
            if acc_idx == 0:
                print_warn("All accounts reached daily limit. Import paused.")
                break
            sw = random.randint(*switch_delay)
            console.print(f"  Switching to {accounts[acc_idx]['phone']} after {sw}s...")
            await client.disconnect()
            wait_countdown(sw, "Switch delay")
            client = _build_client(accounts[acc_idx])
            await client.connect()
            acc_ops = 0
            current_acc = accounts[acc_idx]

        # rotate on per-account ops
        if acc_ops >= per_acc and len(accounts) > 1:
            acc_idx = (acc_idx + 1) % len(accounts)
            sw = random.randint(*switch_delay)
            await client.disconnect()
            wait_countdown(sw, "Account switch")
            client = _build_client(accounts[acc_idx])
            await client.connect()
            acc_ops = 0
            current_acc = accounts[acc_idx]
            print_info(f"Rotated to {current_acc['phone']}")

        uid      = member.get("user_id", "")
        username = member.get("username", "")
        phone    = member.get("phone", "")
        display  = f"@{username}" if username else uid or phone

        if is_blacklisted(str(uid)):
            console.print(f"  [dim]{now_str()[:19]}[/dim]  ⛔ [dim]{display} — Blacklisted[/dim]")
            total_skip += 1
            continue

        try:
            user_ent = None
            if username:
                user_ent = await client.get_entity(f"@{username}")
            elif uid:
                user_ent = await client.get_entity(int(uid))
            else:
                total_skip += 1
                continue

            if method == "1":
                await client(InviteToChannelRequest(target, [user_ent]))
            else:
                group_link = target_link if "t.me" in target_link else f"https://t.me/{target_link.strip('@')}"
                await client.send_message(user_ent, f"You're invited to join: {group_link}")

            console.print(f"  [dim]{now_str()[:19]}[/dim]  ✅ [green]{display}[/green] — Added")
            total_ok += 1
            acc_ops  += 1
            increment_account_counter(current_acc["phone"], "imports", 1)
            increment_stat("import", "successful", 1)

            # save progress
            _save_progress(source_name, target_link, i + 1, cfg)

        except UserAlreadyParticipantError:
            console.print(f"  [dim]{now_str()[:19]}[/dim]  [dim]{display} — Already in group[/dim]")
            total_skip += 1
        except UserPrivacyRestrictedError:
            console.print(f"  [dim]{now_str()[:19]}[/dim]  ⚠️  [yellow]{display} — Privacy restricted[/yellow]")
            total_skip += 1
        except InputUserDeactivatedError:
            console.print(f"  [dim]{now_str()[:19]}[/dim]  [dim]{display} — Deleted account[/dim]")
            total_skip += 1
        except PeerFloodError:
            print_warn(f"PeerFlood on {current_acc['phone']} — switching account")
            acc_idx = (acc_idx + 1) % len(accounts)
            await client.disconnect()
            client = _build_client(accounts[acc_idx])
            await client.connect()
            acc_ops = 0
            total_fail += 1
        except FloodWaitError as e:
            print_warn(f"FloodWait {e.seconds}s — switching account")
            acc_idx = (acc_idx + 1) % len(accounts)
            await client.disconnect()
            wait_countdown(min(e.seconds, 60), "FloodWait")
            client = _build_client(accounts[acc_idx])
            await client.connect()
            acc_ops = 0
        except Exception as e:
            console.print(f"  [dim]{now_str()[:19]}[/dim]  ❌ [red]{display} — {type(e).__name__}[/red]")
            total_fail += 1

        d = random.randint(*delay)
        await asyncio.sleep(d)

    await client.disconnect()

    console.print(f"\n\n  ─── Import Session Complete ─────────────")
    console.print(f"  ✅ Successful : [green]{total_ok}[/green]")
    console.print(f"  ⚠️  Skipped   : [yellow]{total_skip}[/yellow]")
    console.print(f"  ❌ Failed     : [red]{total_fail}[/red]")

    # log result
    log_path = config.LOGS_DIR / f"import_{date_str()}.log"
    with open(log_path, "a") as lf:
        lf.write(f"[{now_str()}] Source={source_name} Target={target_link} OK={total_ok} Skip={total_skip} Fail={total_fail}\n")


def _save_progress(source: str, target: str, position: int, cfg: dict):
    progress = {
        "source":   source,
        "target":   target,
        "position": position,
        "accounts": [a["phone"] for a in cfg["accounts"]],
        "cfg": {k: v for k, v in cfg.items() if k != "accounts"},
    }
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


# ─── Import from CSV ─────────────────────────────────────────────────────────

async def import_from_csv():
    print_header("📂  Import from CSV File")
    files = list(EXPORTS_DIR.glob("*.csv"))

    if not files:
        print_error("No exported CSV files found. Run Member Scraper first.")
        input("\n  Press ENTER...")
        return

    console.print()
    for i, f in enumerate(files, 1):
        with open(f) as fp:
            count = sum(1 for _ in fp) - 1
        console.print(f"  [{i}] {f.name}  ({count} members)")
    console.print(f"  [B] Browse another location")
    console.print()

    sel = prompt("  Select File #", "1")
    if sel.upper() == "B":
        filepath = Path(prompt("  Full path to CSV file"))
    else:
        idx = int(sel) - 1
        if not (0 <= idx < len(files)):
            print_error("Invalid selection.")
            input("\n  Press ENTER...")
            return
        filepath = files[idx]

    members = _load_csv(filepath)
    target = prompt("🎯 Enter Target Group Link")
    if not target:
        return

    cfg = _configure_import_settings()
    if not cfg:
        input("\n  Press ENTER...")
        return

    _print_summary(filepath.name, len(members), target, cfg)
    console.print()
    action = prompt("  [S] Start   [C] Cancel   [E] Edit", "S").upper()
    if action == "S":
        await _run_import(members, target, cfg, filepath.name)
    input("\n  Press ENTER...")


# ─── Manual Import ───────────────────────────────────────────────────────────

async def import_manual():
    print_header("✍️  Manual Import (Enter Usernames)")
    console.print("  Enter usernames one per line (type 'done' to finish):\n")
    members = []
    i = 1
    while True:
        uname = prompt(f"  {i}")
        if uname.lower() in ("done", ""):
            break
        members.append({"username": uname.strip("@"), "user_id": "", "phone": ""})
        i += 1

    if not members:
        return

    target = prompt("🎯 Target Group Link")
    if not target:
        return

    cfg = _configure_import_settings()
    if not cfg:
        input("\n  Press ENTER...")
        return

    _print_summary("Manual Entry", len(members), target, cfg)
    if confirm("\n  Start import?"):
        await _run_import(members, target, cfg, "manual")
    input("\n  Press ENTER...")


# ─── Resume ──────────────────────────────────────────────────────────────────

async def resume_import():
    print_header("🔄  Resume Previous Import")
    if not PROGRESS_FILE.exists():
        print_info("No saved import progress found.")
        input("\n  Press ENTER...")
        return

    with open(PROGRESS_FILE) as f:
        progress = json.load(f)

    source   = progress.get("source", "?")
    target   = progress.get("target", "?")
    position = progress.get("position", 0)

    console.print(f"  Source   : [bold]{source}[/bold]")
    console.print(f"  Target   : [bold]{target}[/bold]")
    console.print(f"  Position : [bold cyan]{position}[/bold cyan] members already processed")

    # Try to load source
    csv_path = EXPORTS_DIR / source
    if not csv_path.exists():
        print_error(f"Source file not found: {csv_path}")
        input("\n  Press ENTER...")
        return

    members = _load_csv(csv_path)
    console.print(f"  Remaining: [bold]{len(members) - position}[/bold] members")

    if confirm("\n  Resume import?"):
        cfg = _configure_import_settings()
        if cfg:
            await _run_import(members, target, cfg, source, start_from=position)
    input("\n  Press ENTER...")


# ─── View Import Logs ────────────────────────────────────────────────────────

def view_import_logs():
    print_header("📊  Import Logs")
    logs = sorted(config.LOGS_DIR.glob("import_*.log"), reverse=True)
    if not logs:
        print_info("No import logs found.")
        input("\n  Press ENTER...")
        return

    for i, log in enumerate(logs[:10], 1):
        console.print(f"  [{i}] {log.name}")
    console.print()
    sel = prompt("  Select log # to view", "1")
    idx = int(sel) - 1
    if 0 <= idx < len(logs):
        with open(logs[idx], "r") as f:
            content = f.read()
        console.print()
        console.print(content[-3000:] if len(content) > 3000 else content)
    input("\n  Press ENTER...")
