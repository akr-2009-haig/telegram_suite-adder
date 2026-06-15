import asyncio
import csv
import random
from pathlib import Path
from datetime import datetime
from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError, UserPrivacyRestrictedError, InputUserDeactivatedError,
    PeerFloodError, UserIsBlockedError,
)

import config
from modules.utils import (
    console, print_header, print_success, print_error, print_warn,
    print_info, prompt, menu_choice, confirm, now_str, date_str, wait_countdown,
)
from modules.database import (
    get_active_accounts, increment_account_counter, increment_stat,
    is_blacklisted, load_proxies,
)

EXPORTS_DIR = config.EXPORTS_DIR
LOGS_DIR    = config.LOGS_DIR


def bulk_messaging_menu():
    while True:
        print_header("💬  Bulk Messaging", "Send messages to multiple users")
        choice = menu_choice([
            ("1", "📋  Send to User List (CSV)"),
            ("2", "✍️  Send to Specific Usernames"),
            ("3", "🔄  Send to Group Members"),
            ("4", "🕐  Scheduled Messaging"),
            ("5", "📊  Messaging Logs"),
        ])
        if choice == "1":
            asyncio.run(send_from_csv())
        elif choice == "2":
            asyncio.run(send_manual())
        elif choice == "3":
            asyncio.run(send_to_group_members())
        elif choice == "4":
            asyncio.run(scheduled_messaging())
        elif choice == "5":
            view_messaging_logs()
        elif choice == "0":
            break


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


def _configure_msg_settings() -> dict | None:
    console.print("\n  ─── Account Selection ────────────────────")
    active = get_active_accounts()
    if not active:
        print_error("No active accounts.")
        return None

    console.print(f"  [1] Single Account")
    console.print(f"  [2] Rotate Between All ({len(active)} accounts)  ⭐")
    mode = prompt("  Select", "2")
    accounts = active if mode != "1" else [active[0]]

    console.print("\n  ─── Delay Between Messages ───────────────")
    console.print("  [1] 60–120s  (Safest)  ⭐")
    console.print("  [2] 30–60s")
    console.print("  [3] 15–30s")
    console.print("  [4] Custom")
    dc = prompt("  Select", "1")
    delays = {"1": (60, 120), "2": (30, 60), "3": (15, 30)}
    if dc == "4":
        dmin = int(prompt("  Min (seconds)", "30") or "30")
        dmax = int(prompt("  Max (seconds)", "60") or "60")
        delay = (dmin, dmax)
    else:
        delay = delays.get(dc, (60, 120))

    console.print("\n  ─── Messages Per Account Per Day ─────────")
    daily_limit = int(prompt("  Limit (recommended: 30)", "30") or "30")

    switch_after = int(prompt("  Switch account after N messages", "10") or "10")

    return {
        "accounts":     accounts,
        "delay":        delay,
        "daily_limit":  daily_limit,
        "switch_after": switch_after,
    }


async def _send_messages(targets: list[str], message: str, cfg: dict, source_label: str):
    accounts    = cfg["accounts"]
    delay       = cfg["delay"]
    daily_limit = cfg["daily_limit"]
    switch_after = cfg["switch_after"]

    acc_idx  = 0
    acc_ops  = 0
    sent_ok  = 0
    skipped  = 0
    failed   = 0

    client = _build_client(accounts[acc_idx])
    await client.connect()

    log_path = LOGS_DIR / f"messaging_{date_str()}.log"

    console.print(f"\n  🚀 Sending to [bold]{len(targets)}[/bold] users...\n")

    for target in targets:
        target = target.strip().strip("@")
        if not target:
            continue

        current = accounts[acc_idx]

        if current.get("today_messages", 0) >= daily_limit:
            acc_idx = (acc_idx + 1) % len(accounts)
            if acc_idx == 0:
                print_warn("All accounts reached daily message limit.")
                break
            await client.disconnect()
            client = _build_client(accounts[acc_idx])
            await client.connect()
            acc_ops = 0
            current = accounts[acc_idx]

        if acc_ops >= switch_after and len(accounts) > 1:
            acc_idx = (acc_idx + 1) % len(accounts)
            await client.disconnect()
            client = _build_client(accounts[acc_idx])
            await client.connect()
            acc_ops = 0
            current = accounts[acc_idx]
            print_info(f"Rotated to {accounts[acc_idx]['phone']}")

        if is_blacklisted(target):
            console.print(f"  [dim]{target} — Blacklisted, skipped[/dim]")
            skipped += 1
            continue

        try:
            entity = await client.get_entity(target if target.startswith("+") else f"@{target}")
            await client.send_message(entity, message)
            console.print(f"  [dim]{now_str()[:19]}[/dim]  ✅ [green]{target}[/green]")
            increment_account_counter(current["phone"], "messages")
            increment_stat("message", "sent")
            sent_ok  += 1
            acc_ops  += 1

            with open(log_path, "a") as lf:
                lf.write(f"[{now_str()}] SENT → {target} via {current['phone']}\n")

        except UserPrivacyRestrictedError:
            console.print(f"  [dim]{target} — Privacy restricted[/dim]")
            skipped += 1
        except InputUserDeactivatedError:
            console.print(f"  [dim]{target} — Deleted account[/dim]")
            skipped += 1
        except UserIsBlockedError:
            console.print(f"  [dim]{target} — Has blocked you[/dim]")
            skipped += 1
        except PeerFloodError:
            print_warn(f"PeerFlood on {current['phone']} — switching")
            acc_idx = (acc_idx + 1) % len(accounts)
            await client.disconnect()
            client = _build_client(accounts[acc_idx])
            await client.connect()
            acc_ops = 0
            failed += 1
        except FloodWaitError as e:
            print_warn(f"FloodWait {e.seconds}s on {current['phone']} — switching")
            acc_idx = (acc_idx + 1) % len(accounts)
            await client.disconnect()
            wait_countdown(min(e.seconds, 60), "FloodWait pause")
            client = _build_client(accounts[acc_idx])
            await client.connect()
            acc_ops = 0
        except Exception as e:
            console.print(f"  ❌ [red]{target} — {type(e).__name__}[/red]")
            failed += 1

        await asyncio.sleep(random.randint(*delay))

    await client.disconnect()

    console.print(f"\n  ─── Messaging Summary ───────────────────")
    console.print(f"  ✅ Sent    : [green]{sent_ok}[/green]")
    console.print(f"  ⚠️  Skipped : [yellow]{skipped}[/yellow]")
    console.print(f"  ❌ Failed  : [red]{failed}[/red]")


async def send_from_csv():
    print_header("📋  Send Message to User List (CSV)")
    files = list(EXPORTS_DIR.glob("*.csv"))
    if not files:
        print_error("No CSV files found. Run member scraper first.")
        input("\n  Press ENTER...")
        return

    for i, f in enumerate(files, 1):
        console.print(f"  [{i}] {f.name}")
    sel = prompt("  Select file", "1")
    try:
        filepath = files[int(sel) - 1]
    except Exception:
        print_error("Invalid selection.")
        input("\n  Press ENTER...")
        return

    targets = []
    with open(filepath, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            u = row.get("username") or row.get("user_id") or row.get("phone")
            if u:
                targets.append(str(u))

    console.print(f"\n  [bold]{len(targets)}[/bold] recipients loaded.")

    console.print("\n  ─── Compose Message ──────────────────────")
    console.print("  [1] Single message")
    console.print("  [2] Random from message list (anti-spam)")
    msg_mode = prompt("  Select", "1")

    if msg_mode == "1":
        message = prompt("  Type your message")
        if not message:
            input("\n  Press ENTER...")
            return
        messages = [message]
    else:
        console.print("  Enter messages (type 'done' to finish):")
        messages = []
        i = 1
        while True:
            m = prompt(f"  Message {i}")
            if m.lower() in ("done", ""):
                break
            messages.append(m)
            i += 1

    cfg = _configure_msg_settings()
    if not cfg:
        input("\n  Press ENTER...")
        return

    if confirm("\n  Start sending?"):
        for i, target in enumerate(targets):
            msg = random.choice(messages)
            await _send_messages([target], msg, cfg, filepath.name)
    input("\n  Press ENTER...")


async def send_manual():
    print_header("✍️  Send to Specific Users")
    console.print("  Enter @usernames or phone numbers (type 'done' to finish):\n")
    targets = []
    i = 1
    while True:
        u = prompt(f"  {i}")
        if u.lower() in ("done", ""):
            break
        targets.append(u)
        i += 1

    if not targets:
        return

    message = prompt("  Type your message")
    if not message:
        return

    cfg = _configure_msg_settings()
    if not cfg:
        input("\n  Press ENTER...")
        return

    if confirm(f"\n  Send to {len(targets)} users?"):
        await _send_messages(targets, message, cfg, "manual")
    input("\n  Press ENTER...")


async def send_to_group_members():
    print_header("🔄  Send to Group Members")
    group_link = prompt("🔗 Group link or @username")
    if not group_link:
        return

    active = get_active_accounts()
    if not active:
        print_error("No active accounts.")
        input("\n  Press ENTER...")
        return

    api_id, api_hash = config.get_api_credentials()
    client = TelegramClient(str(config.SESSIONS_DIR / active[0]["phone"]), int(api_id), api_hash)
    await client.connect()
    targets = []
    try:
        entity = await client.get_entity(group_link.strip())
        async for user in client.iter_participants(entity):
            if user.username:
                targets.append(user.username)
        print_info(f"Loaded {len(targets)} members from group.")
    except Exception as e:
        print_error(f"Could not fetch group: {e}")
        await client.disconnect()
        input("\n  Press ENTER...")
        return
    await client.disconnect()

    message = prompt("  Message to send")
    if not message:
        return

    cfg = _configure_msg_settings()
    if not cfg:
        input("\n  Press ENTER...")
        return

    if confirm(f"\n  Send to {len(targets)} members?"):
        await _send_messages(targets, message, cfg, group_link)
    input("\n  Press ENTER...")


async def scheduled_messaging():
    print_header("🕐  Scheduled Messaging")
    targets_input = prompt("  Targets (comma-separated @usernames)")
    targets = [t.strip() for t in targets_input.split(",") if t.strip()]

    message = prompt("  Message")
    if not message or not targets:
        return

    delay_hours = float(prompt("  Send after how many hours?", "1") or "1")

    console.print(f"\n  Will send to [bold]{len(targets)}[/bold] users after [bold]{delay_hours}h[/bold]")
    if confirm("  Schedule?"):
        wait_countdown(int(delay_hours * 3600), "Scheduled message")
        cfg = _configure_msg_settings()
        if cfg:
            await _send_messages(targets, message, cfg, "scheduled")
    input("\n  Press ENTER...")


def view_messaging_logs():
    print_header("📊  Messaging Logs")
    logs = sorted(LOGS_DIR.glob("messaging_*.log"), reverse=True)
    if not logs:
        print_info("No messaging logs yet.")
        input("\n  Press ENTER...")
        return
    for i, f in enumerate(logs[:10], 1):
        console.print(f"  [{i}] {f.name}")
    sel = prompt("  Select #", "1")
    try:
        log = logs[int(sel) - 1]
        lines = log.read_text(encoding="utf-8").strip().split("\n")
        display = lines[-40:] if len(lines) > 40 else lines
        console.print()
        for line in display:
            console.print(f"  [dim]{line}[/dim]")
    except Exception:
        print_error("Invalid selection.")
    input("\n  Press ENTER...")
