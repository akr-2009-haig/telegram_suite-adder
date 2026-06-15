import asyncio
import os
import shutil
from pathlib import Path
from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError, PhoneCodeInvalidError,
    PhoneNumberInvalidError, FloodWaitError, PasswordHashInvalidError,
    PhoneCodeExpiredError,
)
from rich.table import Table
from rich import box
from rich.console import Console

import config
from modules.utils import (
    console, print_header, print_success, print_error, print_warn,
    print_info, prompt, prompt_secret, menu_choice, confirm,
    status_icon, now_str, progress_bar, wait_countdown,
)
from modules.database import (
    load_accounts, save_accounts, add_account, remove_account,
    update_account, get_account, reset_daily_counters,
)

SESSIONS_DIR = config.SESSIONS_DIR


def account_manager_menu():
    while True:
        print_header("👤  Account Manager", "Manage connected Telegram accounts")
        accounts = load_accounts()
        active = sum(1 for a in accounts if a.get("status") == "active")
        total = len(accounts)
        console.print(f"  Active Accounts: [bold green]{active}[/bold green] / [white]{total}[/white]")
        console.print()

        choice = menu_choice([
            ("1", "➕  Add New Account"),
            ("2", "📂  Import Sessions"),
            ("3", "📋  View All Accounts"),
            ("4", "✅  Validate Accounts"),
            ("5", "❌  Remove Account"),
            ("6", "🗑️  Auto Remove Banned Accounts"),
            ("7", "📤  Export Sessions"),
            ("8", "🔥  Account Warm-Up"),
        ])

        if choice == "1":
            asyncio.run(add_new_account())
        elif choice == "2":
            import_sessions()
        elif choice == "3":
            view_accounts()
        elif choice == "4":
            asyncio.run(validate_accounts())
        elif choice == "5":
            remove_account_menu()
        elif choice == "6":
            auto_remove_banned()
        elif choice == "7":
            export_sessions()
        elif choice == "8":
            asyncio.run(account_warmup())
        elif choice == "0":
            break


# ─── Add New Account ─────────────────────────────────────────────────────────

async def add_new_account():
    print_header("➕  Add New Account", "Authenticate via phone number")
    api_id, api_hash = config.get_api_credentials()
    if not api_id or not api_hash:
        print_error("API credentials not configured. Go to Settings first.")
        input("\n  Press ENTER to continue...")
        return

    phone = prompt("📱 Phone Number (e.g. +966501234567)")
    if not phone:
        return
    if not phone.startswith("+"):
        print_error("Phone must include country code (e.g. +966...)")
        input("\n  Press ENTER to continue...")
        return

    session_path = str(SESSIONS_DIR / phone)
    client = TelegramClient(session_path, int(api_id), api_hash)

    try:
        await client.connect()
        console.print(f"\n  [dim]Sending verification code to [bold]{phone}[/bold]...[/dim]")
        result = await client.send_code_request(phone)
        phone_code_hash = result.phone_code_hash

        console.print(f"\n  ✅ Code sent to [bold]{phone}[/bold]")
        console.print()
        console.print("  How did you receive the code?")
        console.print("  [cyan][1][/cyan] Telegram App")
        console.print("  [cyan][2][/cyan] SMS Message")
        console.print()

        code = prompt("🔢 Enter Verification Code")
        if not code:
            await client.disconnect()
            return

        try:
            await client.sign_in(phone, code, phone_code_hash=phone_code_hash)

        except SessionPasswordNeededError:
            console.print("\n  [yellow]🔐 Two-Factor Authentication required[/yellow]")
            password = prompt_secret("🔑 Enter 2FA Password")
            try:
                await client.sign_in(password=password)
            except PasswordHashInvalidError:
                print_error("Incorrect 2FA password.")
                await client.disconnect()
                input("\n  Press ENTER to continue...")
                return

        except PhoneCodeInvalidError:
            print_error("Invalid verification code.")
            await client.disconnect()
            input("\n  Press ENTER to continue...")
            return

        except PhoneCodeExpiredError:
            print_error("Code expired. Please try again.")
            await client.disconnect()
            input("\n  Press ENTER to continue...")
            return

        me = await client.get_me()
        console.print()
        console.print("  ┌──────────────────────────────────────────┐")
        console.print("  │  🎉  Login Successful                    │")
        console.print("  ├──────────────────────────────────────────┤")
        console.print(f"  │  Name     : [bold]{me.first_name or ''} {me.last_name or ''}[/bold]")
        console.print(f"  │  Username : [bold]@{me.username or 'N/A'}[/bold]")
        console.print(f"  │  Phone    : [bold]{phone}[/bold]")
        console.print(f"  │  User ID  : [dim]{me.id}[/dim]")
        console.print(f"  │  Session  : [dim]sessions/{phone}.session[/dim]")
        console.print("  └──────────────────────────────────────────┘")
        console.print()

        account_data = {
            "phone": phone,
            "name": f"{me.first_name or ''} {me.last_name or ''}".strip(),
            "username": me.username or "",
            "user_id": me.id,
            "status": "active",
            "proxy_id": None,
            "added_at": now_str(),
            "last_used": now_str(),
            "today_imports": 0,
            "today_collections": 0,
            "today_messages": 0,
            "warmup_done": False,
        }

        assign = prompt("🌐 Assign a proxy to this account? [Y/N]", "N").upper()
        if assign == "Y":
            from modules.proxy_manager import assign_proxy_to_account
            assign_proxy_to_account(phone)

        add_account(account_data)
        print_success(f"Account {phone} saved successfully.")

        another = prompt("\n  Add another account? [Y/N]", "N").upper()
        if another == "Y":
            await client.disconnect()
            await add_new_account()

    except PhoneNumberInvalidError:
        print_error("Invalid phone number format.")
    except FloodWaitError as e:
        print_warn(f"FloodWait: Please wait {e.seconds} seconds before retrying.")
    except Exception as e:
        print_error(f"Unexpected error: {e}")
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

    input("\n  Press ENTER to continue...")


# ─── Import Sessions ─────────────────────────────────────────────────────────

def import_sessions():
    print_header("📂  Import Sessions", "Import existing .session files")

    choice = menu_choice([
        ("1", "📁  Import from Folder (All .session Files)"),
        ("2", "📄  Import Single Session File"),
        ("3", "📋  Import from Text File (Session Strings)"),
    ])

    if choice == "1":
        folder = prompt("📁 Enter Folder Path")
        if not folder:
            return
        folder_path = Path(folder.strip())
        if not folder_path.exists():
            print_error("Folder not found.")
            input("\n  Press ENTER...")
            return

        files = list(folder_path.glob("*.session"))
        console.print(f"\n  🔍 Found [bold]{len(files)}[/bold] .session files")

        valid, dupes = [], []
        for f in files:
            phone = f.stem
            if get_account(phone):
                dupes.append(f)
            else:
                valid.append(f)

        console.print(f"  Valid Sessions     : [green]{len(valid)}[/green]")
        console.print(f"  Already Imported   : [dim]{len(dupes)}[/dim]")
        console.print()

        if not valid:
            print_info("No new sessions to import.")
            input("\n  Press ENTER...")
            return

        if confirm(f"  Import {len(valid)} valid sessions?"):
            imported = 0
            for f in valid:
                dest = SESSIONS_DIR / f.name
                shutil.copy2(f, dest)
                phone = f.stem
                add_account({
                    "phone": phone,
                    "name": "Imported",
                    "username": "",
                    "user_id": None,
                    "status": "active",
                    "proxy_id": None,
                    "added_at": now_str(),
                    "last_used": now_str(),
                    "today_imports": 0,
                    "today_collections": 0,
                    "today_messages": 0,
                    "warmup_done": False,
                })
                imported += 1

            print_success(f"Imported {imported} sessions successfully.")
        input("\n  Press ENTER...")

    elif choice == "2":
        file_path = prompt("📄 Enter .session File Path")
        if not file_path:
            return
        fp = Path(file_path.strip())
        if not fp.exists() or fp.suffix != ".session":
            print_error("Invalid .session file.")
            input("\n  Press ENTER...")
            return
        dest = SESSIONS_DIR / fp.name
        shutil.copy2(fp, dest)
        phone = fp.stem
        add_account({
            "phone": phone,
            "name": "Imported",
            "username": "",
            "user_id": None,
            "status": "active",
            "proxy_id": None,
            "added_at": now_str(),
            "last_used": now_str(),
            "today_imports": 0,
            "today_collections": 0,
            "today_messages": 0,
            "warmup_done": False,
        })
        print_success(f"Session {phone} imported.")
        input("\n  Press ENTER...")


# ─── View Accounts ───────────────────────────────────────────────────────────

def view_accounts():
    while True:
        print_header("📋  Account List")
        accounts = load_accounts()

        if not accounts:
            print_info("No accounts found. Add accounts first.")
            input("\n  Press ENTER to continue...")
            return

        table = Table(box=box.SIMPLE_HEAVY, border_style="cyan", show_header=True)
        table.add_column("#",        style="dim",        width=4, justify="right")
        table.add_column("Phone",    style="bold white",  width=16)
        table.add_column("Name",     style="white",       width=18)
        table.add_column("Status",   style="white",       width=18)
        table.add_column("Proxy",    style="dim",         width=12)
        table.add_column("Last Used",style="dim",         width=16)

        active = banned = restricted = 0
        for i, a in enumerate(accounts, 1):
            st = a.get("status", "unknown")
            if st == "active":       active += 1;      sc = "green"
            elif st == "banned":     banned += 1;      sc = "red"
            elif st == "restricted": restricted += 1;  sc = "yellow"
            else:                                       sc = "dim"

            proxy = f"✅ #{a['proxy_id']}" if a.get("proxy_id") else "❌ None"
            table.add_row(
                str(i),
                a["phone"],
                a.get("name", "N/A")[:17],
                f"[{sc}]{status_icon(st)}[/{sc}]",
                proxy,
                a.get("last_used", "N/A")[:16],
            )

        console.print(table)
        console.print(f"  ✅ Active: [green]{active}[/green]  ⛔ Banned: [red]{banned}[/red]  ⚠️  Restricted: [yellow]{restricted}[/yellow]")

        choice = menu_choice([
            ("F", "🔍  Filter by Status"),
            ("D", "🗑️  Delete Account"),
        ])
        if choice.upper() == "F":
            status_filter = prompt("Filter by (active/banned/restricted)").lower()
            accounts = [a for a in accounts if a.get("status") == status_filter]
            continue
        elif choice.upper() == "D":
            phone = prompt("Enter phone number to delete")
            if remove_account(phone):
                print_success(f"Account {phone} removed.")
            else:
                print_error("Account not found.")
            input("\n  Press ENTER...")
        elif choice == "0":
            break


# ─── Validate Accounts ───────────────────────────────────────────────────────

async def validate_accounts():
    print_header("✅  Validate Accounts", "Checking connectivity and authorization")
    api_id, api_hash = config.get_api_credentials()
    if not api_id or not api_hash:
        print_error("API credentials not set.")
        input("\n  Press ENTER...")
        return

    accounts = load_accounts()
    if not accounts:
        print_info("No accounts to validate.")
        input("\n  Press ENTER...")
        return

    results = []
    with progress_bar(len(accounts), "Validating") as prog:
        task = prog.add_task("Validating", total=len(accounts))
        for acc in accounts:
            phone = acc["phone"]
            session = str(SESSIONS_DIR / phone)
            try:
                client = TelegramClient(session, int(api_id), api_hash)
                await client.connect()
                if await client.is_user_authorized():
                    me = await client.get_me()
                    update_account(phone, {"status": "active", "name": f"{me.first_name or ''} {me.last_name or ''}".strip()})
                    results.append((phone, "active"))
                else:
                    update_account(phone, {"status": "banned"})
                    results.append((phone, "banned"))
                await client.disconnect()
            except Exception as e:
                update_account(phone, {"status": "error"})
                results.append((phone, "error"))
            prog.advance(task)

    console.print()
    for phone, status in results:
        icon = "✅" if status == "active" else ("⛔" if status == "banned" else "❌")
        color = "green" if status == "active" else ("red" if status == "banned" else "yellow")
        console.print(f"  {icon} [{color}]{phone}[/{color}]  →  {status.upper()}")

    input("\n  Press ENTER to continue...")


# ─── Remove Account ──────────────────────────────────────────────────────────

def remove_account_menu():
    print_header("❌  Remove Account")
    accounts = load_accounts()
    for i, a in enumerate(accounts, 1):
        console.print(f"  [{i}] {a['phone']}  ({a.get('name','N/A')})")
    console.print()
    phone = prompt("Enter phone number (or # number)")
    if not phone:
        return
    if phone.isdigit():
        idx = int(phone) - 1
        if 0 <= idx < len(accounts):
            phone = accounts[idx]["phone"]
        else:
            print_error("Invalid selection.")
            input("\n  Press ENTER...")
            return
    if confirm(f"  Permanently delete account {phone}?"):
        if remove_account(phone):
            session_file = SESSIONS_DIR / f"{phone}.session"
            if session_file.exists():
                session_file.unlink()
            print_success(f"Account {phone} removed.")
        else:
            print_error("Account not found.")
    input("\n  Press ENTER...")


# ─── Auto Remove Banned ──────────────────────────────────────────────────────

def auto_remove_banned():
    print_header("🗑️  Auto Remove Banned Accounts")
    accounts = load_accounts()
    banned = [a for a in accounts if a.get("status") in ("banned", "error")]
    console.print(f"  Found [red]{len(banned)}[/red] banned/restricted accounts.")
    if not banned:
        print_info("No banned accounts found.")
        input("\n  Press ENTER...")
        return
    for b in banned:
        console.print(f"  ⛔ {b['phone']}  ({b.get('name','N/A')})")
    console.print()
    if confirm(f"  Remove all {len(banned)} banned accounts?"):
        for b in banned:
            remove_account(b["phone"])
        print_success(f"Removed {len(banned)} accounts.")
    input("\n  Press ENTER...")


# ─── Export Sessions ─────────────────────────────────────────────────────────

def export_sessions():
    print_header("📤  Export Sessions")
    dest = prompt("📁 Export to Folder Path", "./exported_sessions")
    dest_path = Path(dest)
    dest_path.mkdir(parents=True, exist_ok=True)

    accounts = load_accounts()
    exported = 0
    for a in accounts:
        src = SESSIONS_DIR / f"{a['phone']}.session"
        if src.exists():
            shutil.copy2(src, dest_path / src.name)
            exported += 1
    print_success(f"Exported {exported} session files to {dest_path}")
    input("\n  Press ENTER...")


# ─── Account Warm-Up ─────────────────────────────────────────────────────────

async def account_warmup():
    print_header("🔥  Account Warm-Up", "Make accounts appear natural and trustworthy")

    console.print("  Select Warm-Up Actions:\n")
    console.print("  [1] Join Random Popular Channels")
    console.print("  [2] View Messages in Groups")
    console.print("  [3] Update Profile Bio")
    console.print("  [4] Add Random Contacts")
    console.print()

    console.print("  Duration:")
    console.print("  [1] Light   — 1 Day")
    console.print("  [2] Moderate — 3 Days")
    console.print("  [3] Intensive — 7 Days  ⭐ Recommended")
    console.print()
    duration_choice = prompt("⏱ Select Duration", "3")
    durations = {"1": 1, "2": 3, "3": 7}
    days = durations.get(duration_choice, 7)

    accounts = load_accounts()
    active = [a for a in accounts if a.get("status") == "active"]
    console.print(f"\n  Active Accounts Available: [green]{len(active)}[/green]")
    scope = prompt("  [A] All Accounts  /  [M] Manual Selection", "A").upper()

    if scope == "M":
        phones_input = prompt("  Enter phone numbers (comma-separated)")
        phones = [p.strip() for p in phones_input.split(",")]
        active = [a for a in active if a["phone"] in phones]

    if not active:
        print_error("No valid accounts selected.")
        input("\n  Press ENTER...")
        return

    print_info(f"Starting warm-up for {len(active)} accounts over {days} days...")

    popular_channels = [
        "telegram", "durov", "tginfo", "bbcarabic", "aljazeeraenglish"
    ]

    api_id, api_hash = config.get_api_credentials()
    for acc in active:
        phone = acc["phone"]
        session = str(config.SESSIONS_DIR / phone)
        try:
            client = TelegramClient(session, int(api_id), api_hash)
            await client.connect()
            if not await client.is_user_authorized():
                print_warn(f"{phone} — not authorized, skipping")
                await client.disconnect()
                continue

            console.print(f"\n  🔥 Warming up [bold]{phone}[/bold]...")
            for ch in popular_channels[:2]:
                try:
                    await client.get_entity(ch)
                    console.print(f"      ✅ Viewed channel @{ch}")
                    await asyncio.sleep(5)
                except Exception:
                    pass

            update_account(phone, {"warmup_done": True})
            await client.disconnect()
            print_success(f"{phone} warm-up sequence completed.")
        except Exception as e:
            print_error(f"{phone} — {e}")

    print_success(f"Warm-up started for {len(active)} accounts. Duration: {days} days.")
    input("\n  Press ENTER...")
