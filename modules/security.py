import asyncio
import json
import shutil
from datetime import datetime
from pathlib import Path
from rich.table import Table
from rich import box

import config
from modules.utils import (
    console, print_header, print_success, print_error, print_info, print_warn,
    prompt, menu_choice, confirm, now_str, date_str,
)
from modules.database import (
    load_accounts, load_blacklist, add_to_blacklist, remove_from_blacklist,
    load_proxies,
)


def security_menu():
    while True:
        print_header("🛡️  Security Tools", "Account protection and security utilities")
        choice = menu_choice([
            ("1", "📋  Blacklist Manager"),
            ("2", "⏱️  Smart Limits"),
            ("3", "🔍  Account Health Check"),
            ("4", "🧹  Account Cleanup"),
            ("5", "📊  Ban Monitor"),
            ("6", "🔐  Backup"),
        ])
        if choice == "1":
            blacklist_menu()
        elif choice == "2":
            smart_limits()
        elif choice == "3":
            asyncio.run(health_check())
        elif choice == "4":
            asyncio.run(account_cleanup())
        elif choice == "5":
            asyncio.run(ban_monitor())
        elif choice == "6":
            backup_menu()
        elif choice == "0":
            break


# ─── Blacklist ────────────────────────────────────────────────────────────────

def blacklist_menu():
    while True:
        print_header("📋  Blacklist", "Users who will never be imported or messaged")
        bl = load_blacklist()
        console.print(f"  Total Blacklisted: [bold red]{len(bl)}[/bold red]")
        console.print()

        choice = menu_choice([
            ("1", "➕  Add to Blacklist"),
            ("2", "❌  Remove from Blacklist"),
            ("3", "📋  View Blacklist"),
            ("4", "📥  Import Blacklist from File"),
            ("5", "🗑️  Clear Entire Blacklist"),
        ])
        if choice == "1":
            uid = prompt("  Enter User ID or @username to blacklist")
            if uid:
                add_to_blacklist(uid.strip().strip("@"))
                print_success(f"Added {uid} to blacklist.")
            input("\n  Press ENTER...")

        elif choice == "2":
            uid = prompt("  Enter User ID or @username to remove")
            if uid:
                remove_from_blacklist(uid.strip().strip("@"))
                print_success(f"Removed from blacklist.")
            input("\n  Press ENTER...")

        elif choice == "3":
            bl = load_blacklist()
            if not bl:
                print_info("Blacklist is empty.")
            else:
                console.print()
                for i, uid in enumerate(bl[:50], 1):
                    console.print(f"  [{i}] {uid}")
                if len(bl) > 50:
                    console.print(f"  [dim]... and {len(bl)-50} more[/dim]")
            input("\n  Press ENTER...")

        elif choice == "4":
            fpath = prompt("  Path to file (one ID per line)")
            try:
                with open(fpath, "r") as f:
                    ids = [l.strip().strip("@") for l in f if l.strip()]
                for uid in ids:
                    add_to_blacklist(uid)
                print_success(f"Imported {len(ids)} IDs to blacklist.")
            except Exception as e:
                print_error(str(e))
            input("\n  Press ENTER...")

        elif choice == "5":
            if confirm("  Clear entire blacklist?"):
                from modules.utils import write_json
                write_json(config.DATA_DIR / "blacklist.json", [])
                print_success("Blacklist cleared.")
            input("\n  Press ENTER...")

        elif choice == "0":
            break


# ─── Smart Limits ─────────────────────────────────────────────────────────────

def smart_limits():
    print_header("⏱️  Smart Limits", "Automatic protection system")

    settings = config.load_settings()
    sec_level = settings.get("security_level", "balanced")
    accounts  = load_accounts()

    console.print("  🧠 Smart Protection System Automatically:")
    console.print("  [✓] Reduces speed on repeated FloodWait warnings")
    console.print("  [✓] Increases delays when an account is restricted")
    console.print("  [✓] Pauses all ops if multiple accounts become restricted")
    console.print("  [✓] Lowers daily limits for new accounts (<30 days)")
    console.print("  [✓] Increases limits for older accounts (>6 months)")
    console.print()

    console.print("  ⚙️  Security Level:")
    console.print("  [1] 🟢 Conservative (Slower but Safer)")
    console.print("  [2] 🟡 Balanced (Recommended)  ⭐")
    console.print("  [3] 🔴 Aggressive (Faster, Higher Risk)")
    console.print()
    console.print(f"  Current: [bold]{'Conservative' if sec_level=='conservative' else ('Balanced' if sec_level=='balanced' else 'Aggressive')}[/bold]")
    console.print()

    sl_map = {"1": "conservative", "2": "balanced", "3": "aggressive"}
    sel = prompt("  Select Level (ENTER to keep current)")
    if sel in sl_map:
        settings["security_level"] = sl_map[sel]
        config.save_settings(settings)
        print_success(f"Security level set to: {sl_map[sel].title()}")

    console.print("\n  ─── Smart Limits Per Account ──────────────")
    table = Table(box=box.SIMPLE_HEAVY, border_style="cyan")
    table.add_column("Account",     width=17, style="bold white")
    table.add_column("Age",         width=12)
    table.add_column("Daily Limit", width=13, justify="right")
    table.add_column("Delay Range", width=16)

    for a in accounts[:8]:
        added = a.get("added_at", "")
        try:
            age_days = (datetime.now() - datetime.strptime(added[:10], "%Y-%m-%d")).days
        except Exception:
            age_days = 0

        if age_days < 30:
            limit  = 10
            delay  = "90–180s"
            age_s  = f"[red]{age_days}d[/red]"
        elif age_days < 180:
            limit  = 20
            delay  = "60–120s"
            age_s  = f"[yellow]{age_days}d[/yellow]"
        else:
            limit  = 30
            delay  = "45–90s"
            age_s  = f"[green]{age_days}d[/green]"

        table.add_row(a["phone"][-12:], age_s, str(limit), delay)

    console.print(table)
    input("\n  Press ENTER...")


# ─── Health Check ────────────────────────────────────────────────────────────

async def health_check():
    print_header("🔍  Account Health Check")
    api_id, api_hash = config.get_api_credentials()
    if not api_id or not api_hash:
        print_error("API credentials not configured.")
        input("\n  Press ENTER...")
        return

    accounts = load_accounts()
    if not accounts:
        print_info("No accounts to check.")
        input("\n  Press ENTER...")
        return

    console.print(f"  Checking {len(accounts)} accounts...\n")

    from telethon import TelegramClient
    from modules.database import update_account

    results = []
    for acc in accounts:
        phone   = acc["phone"]
        session = str(config.SESSIONS_DIR / phone)
        try:
            client = TelegramClient(session, int(api_id), api_hash)
            await client.connect()
            if await client.is_user_authorized():
                me = await client.get_me()
                status = "active"
                name = f"{me.first_name or ''} {me.last_name or ''}".strip()
                update_account(phone, {"status": "active", "name": name})
            else:
                status = "banned"
                update_account(phone, {"status": "banned"})
            await client.disconnect()
        except Exception as e:
            status = "error"
        results.append((phone, status))

    for phone, status in results:
        icon  = "✅" if status == "active" else ("⛔" if status == "banned" else "❌")
        color = "green" if status == "active" else ("red" if status == "banned" else "yellow")
        console.print(f"  {icon} [{color}]{phone}[/{color}]  →  {status.upper()}")

    active_count = sum(1 for _, s in results if s == "active")
    console.print(f"\n  Healthy: [bold green]{active_count}[/bold green] / {len(results)}")
    input("\n  Press ENTER...")


# ─── Account Cleanup ─────────────────────────────────────────────────────────

async def account_cleanup():
    print_header("🧹  Account Cleanup")
    api_id, api_hash = config.get_api_credentials()
    if not api_id or not api_hash:
        print_error("API credentials not set.")
        input("\n  Press ENTER...")
        return

    accounts = load_accounts()
    active = [a for a in accounts if a.get("status") == "active"]
    if not active:
        print_info("No active accounts.")
        input("\n  Press ENTER...")
        return

    for i, a in enumerate(active, 1):
        console.print(f"  [{i}] {a['phone']}  ({a.get('name','N/A')})")
    sel = prompt("  Select Account #", "all")

    selected = active
    if sel.isdigit():
        idx = int(sel) - 1
        if 0 <= idx < len(active):
            selected = [active[idx]]

    console.print("\n  Cleanup Actions:")
    leave_groups = confirm("  Leave all joined groups?")
    del_msgs     = confirm("  Delete recent messages?")

    from telethon import TelegramClient

    for acc in selected:
        phone   = acc["phone"]
        session = str(config.SESSIONS_DIR / phone)
        console.print(f"\n  🧹 Cleaning {phone}...")
        try:
            client = TelegramClient(session, int(api_id), api_hash)
            await client.connect()
            if not await client.is_user_authorized():
                console.print(f"  [red]{phone} — not authorized[/red]")
                await client.disconnect()
                continue

            if leave_groups:
                async for dialog in client.iter_dialogs():
                    if dialog.is_group or dialog.is_channel:
                        try:
                            await client.delete_dialog(dialog)
                            console.print(f"  [dim]Left: {dialog.title}[/dim]")
                            import asyncio as _asyncio
                            await _asyncio.sleep(1)
                        except Exception:
                            pass

            if del_msgs:
                from telethon.tl.functions.messages import DeleteHistoryRequest
                async for dialog in client.iter_dialogs():
                    if dialog.is_user:
                        try:
                            await client(DeleteHistoryRequest(peer=dialog.input_entity, max_id=0, revoke=True))
                        except Exception:
                            pass

            await client.disconnect()
            print_success(f"{phone} cleanup completed.")
        except Exception as e:
            print_error(f"{phone}: {e}")

    input("\n  Press ENTER...")


# ─── Ban Monitor ─────────────────────────────────────────────────────────────

async def ban_monitor():
    print_header("📊  Ban Monitor", "Instant alerts when an account is restricted")
    api_id, api_hash = config.get_api_credentials()
    if not api_id or not api_hash:
        print_error("API credentials not set.")
        input("\n  Press ENTER...")
        return

    interval = int(prompt("  Check every N minutes", "30") or "30")
    console.print(f"\n  [bold]Starting ban monitor...[/bold] (Ctrl+C to stop)")
    console.print(f"  Checking every {interval} minutes.\n")

    from telethon import TelegramClient
    from modules.database import update_account
    import asyncio

    try:
        while True:
            accounts = load_accounts()
            for acc in accounts:
                phone   = acc["phone"]
                session = str(config.SESSIONS_DIR / phone)
                try:
                    client = TelegramClient(session, int(api_id), api_hash)
                    await client.connect()
                    authorized = await client.is_user_authorized()
                    await client.disconnect()
                    if not authorized:
                        prev_status = acc.get("status")
                        if prev_status != "banned":
                            update_account(phone, {"status": "banned"})
                            console.print(f"  ⛔ [bold red]ALERT: {phone} was BANNED at {now_str()}[/bold red]")
                    else:
                        if acc.get("status") == "banned":
                            update_account(phone, {"status": "active"})
                            console.print(f"  ✅ [green]{phone} is now active again[/green]")
                except Exception:
                    pass

            console.print(f"  [dim]Checked at {now_str()} — Next check in {interval} min[/dim]")
            await asyncio.sleep(interval * 60)

    except KeyboardInterrupt:
        console.print("\n  [dim]Ban monitor stopped.[/dim]")
    input("\n  Press ENTER...")


# ─── Backup ──────────────────────────────────────────────────────────────────

def backup_menu():
    print_header("🔐  Backup", "Create backups of sessions, settings, and data")

    backup_dir = config.BASE_DIR / "backups"
    backup_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"backup_{timestamp}"
    archive_path = backup_dir / archive_name

    console.print("  Creating backup...")
    try:
        shutil.make_archive(
            str(archive_path), "zip",
            root_dir=str(config.BASE_DIR),
            base_dir=".",
        )
        final_path = str(archive_path) + ".zip"
        size_mb = Path(final_path).stat().st_size / 1024 / 1024
        print_success(f"Backup created: {final_path}  ({size_mb:.2f} MB)")
    except Exception as e:
        print_error(f"Backup failed: {e}")

    existing = sorted(backup_dir.glob("backup_*.zip"), reverse=True)
    if len(existing) > 5:
        console.print(f"  [dim]Keeping last 5 backups, removing {len(existing)-5} old ones...[/dim]")
        for old in existing[5:]:
            old.unlink()

    input("\n  Press ENTER...")
