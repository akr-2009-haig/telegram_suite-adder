import asyncio
import os
import shutil
from pathlib import Path
from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError, PhoneCodeInvalidError,
    PhoneNumberInvalidError, FloodWaitError, PasswordHashInvalidError,
    PhoneCodeExpiredError, PhoneNumberBannedError, AuthRestartError,
    RPCError,
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

    # Phone number input
    phone = prompt("📱 Phone Number (e.g. +966501234567)")
    if not phone:
        return
    phone = phone.strip()
    if not phone.startswith("+"):
        print_error("Phone must include country code (e.g. +966...)")
        input("\n  Press ENTER to continue...")
        return

    # Remove old partial session if exists
    session_path = str(SESSIONS_DIR / phone)
    session_file = Path(session_path + ".session")

    client = TelegramClient(session_path, int(api_id), api_hash)

    try:
        print_info("Connecting to Telegram...")
        await client.connect()

        # Check if already authorized
        if await client.is_user_authorized():
            me = await client.get_me()
            print_warn(f"This account is already logged in as: {me.first_name} (@{me.username})")
            if not confirm("  Re-authenticate this account?"):
                await client.disconnect()
                input("\n  Press ENTER to continue...")
                return
            await client.log_out()
            await client.disconnect()
            # Remove old session
            if session_file.exists():
                session_file.unlink()
            client = TelegramClient(session_path, int(api_id), api_hash)
            await client.connect()

        # Send verification code
        console.print(f"\n  [dim]Sending verification code to [bold]{phone}[/bold]...[/dim]")
        try:
            result = await client.send_code_request(phone)
        except PhoneNumberBannedError:
            print_error("This phone number is banned from Telegram.")
            await client.disconnect()
            input("\n  Press ENTER to continue...")
            return
        except FloodWaitError as e:
            print_warn(f"Too many requests. Please wait {e.seconds} seconds before retrying.")
            await client.disconnect()
            input("\n  Press ENTER to continue...")
            return

        phone_code_hash = result.phone_code_hash

        console.print(f"\n  ✅ Code sent to [bold]{phone}[/bold]")
        console.print()
        console.print("  How did you receive the code?")
        console.print("  [cyan][1][/cyan] Telegram App")
        console.print("  [cyan][2][/cyan] SMS Message")
        console.print()

        # Get verification code
        code = prompt("🔢 Enter Verification Code (digits only)")
        if not code:
            print_error("No code entered. Cancelled.")
            await client.disconnect()
            return
        code = code.strip().replace(" ", "")

        # Sign in
        try:
            await client.sign_in(phone, code, phone_code_hash=phone_code_hash)

        except SessionPasswordNeededError:
            # Two-Factor Authentication required
            console.print()
            console.print("  ┌──────────────────────────────────────────────┐")
            console.print("  │  🔐  Two-Factor Authentication Required      │")
            console.print("  └──────────────────────────────────────────────┘")
            console.print()
            password = prompt_secret("🔑 Enter 2FA Password")
            if not password:
                print_error("No password entered. Cancelled.")
                await client.disconnect()
                input("\n  Press ENTER to continue...")
                return
            try:
                await client.sign_in(password=password)
            except PasswordHashInvalidError:
                print_error("Incorrect 2FA password. Please try again.")
                await client.disconnect()
                if session_file.exists():
                    session_file.unlink()
                input("\n  Press ENTER to continue...")
                return

        except PhoneCodeInvalidError:
            print_error("Invalid verification code. Please check and try again.")
            await client.disconnect()
            if session_file.exists():
                session_file.unlink()
            input("\n  Press ENTER to continue...")
            return

        except PhoneCodeExpiredError:
            print_error("Verification code has expired. Please start over.")
            await client.disconnect()
            if session_file.exists():
                session_file.unlink()
            input("\n  Press ENTER to continue...")
            return

        except AuthRestartError:
            print_warn("Telegram requested auth restart. Retrying...")
            await client.disconnect()
            if session_file.exists():
                session_file.unlink()
            input("\n  Press ENTER to try again...")
            return

        # Get account info
        me = await client.get_me()
        if not me:
            print_error("Could not retrieve account info. Please try again.")
            await client.disconnect()
            input("\n  Press ENTER to continue...")
            return

        # Display success
        console.print()
        console.print("  ┌──────────────────────────────────────────────┐")
        console.print("  │  🎉  Login Successful!                        │")
        console.print("  ├──────────────────────────────────────────────┤")
        fname = (me.first_name or "")
        lname = (me.last_name or "")
        full_name = f"{fname} {lname}".strip() or "N/A"
        uname = me.username or "N/A"
        console.print(f"  │  Name     : [bold]{full_name}[/bold]")
        console.print(f"  │  Username : [bold]@{uname}[/bold]")
        console.print(f"  │  Phone    : [bold]{phone}[/bold]")
        console.print(f"  │  User ID  : [dim]{me.id}[/dim]")
        console.print(f"  │  Session  : [dim]sessions/{phone}.session[/dim]")
        console.print("  └──────────────────────────────────────────────┘")
        console.print()

        # Save account to database
        account_data = {
            "phone": phone,
            "name": full_name,
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

        # Assign proxy optionally
        assign = prompt("🌐 Assign a proxy to this account? [Y/N]", "N").upper()
        if assign == "Y":
            from modules.proxy_manager import assign_proxy_to_account
            await client.disconnect()
            assign_proxy_to_account(phone)
            client = None

        add_account(account_data)
        print_success(f"Account {phone} saved successfully.")

        if client:
            await client.disconnect()

        # Ask to add another
        console.print()
        another = prompt("  Add another account? [Y/N]", "N").upper()
        if another == "Y":
            await add_new_account()
        else:
            input("\n  Press ENTER to continue...")

    except PhoneNumberInvalidError:
        print_error("Invalid phone number format. Use international format: +966XXXXXXXXX")
        await _safe_disconnect(client)
        if session_file.exists():
            session_file.unlink()
        input("\n  Press ENTER to continue...")
    except FloodWaitError as e:
        print_warn(f"Flood protection — wait {e.seconds} seconds before retrying.")
        await _safe_disconnect(client)
        input("\n  Press ENTER to continue...")
    except RPCError as e:
        print_error(f"Telegram error: {e.message}")
        await _safe_disconnect(client)
        if session_file.exists():
            session_file.unlink()
        input("\n  Press ENTER to continue...")
    except ConnectionError as e:
        print_error(f"Connection failed: {e}\nCheck your internet connection.")
        await _safe_disconnect(client)
        input("\n  Press ENTER to continue...")
    except Exception as e:
        print_error(f"Unexpected error: {type(e).__name__}: {e}")
        await _safe_disconnect(client)
        input("\n  Press ENTER to continue...")


async def _safe_disconnect(client):
    try:
        if client and client.is_connected():
            await client.disconnect()
    except Exception:
        pass


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

    elif choice == "0":
        return


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
    console.print(f"  Checking [bold]{len(accounts)}[/bold] accounts...\n")

    for i, acc in enumerate(accounts, 1):
        phone = acc["phone"]
        session = str(SESSIONS_DIR / phone)
        console.print(f"  [{i}/{len(accounts)}] {phone} ... ", end="")
        try:
            client = TelegramClient(session, int(api_id), api_hash)
            await client.connect()
            if await client.is_user_authorized():
                me = await client.get_me()
                name = f"{me.first_name or ''} {me.last_name or ''}".strip()
                update_account(phone, {"status": "active", "name": name})
                results.append((phone, "active"))
                console.print("[bold green]✅ Active[/bold green]")
            else:
                update_account(phone, {"status": "banned"})
                results.append((phone, "banned"))
                console.print("[bold red]⛔ Not Authorized[/bold red]")
            await client.disconnect()
        except Exception as e:
            update_account(phone, {"status": "error"})
            results.append((phone, "error"))
            console.print(f"[bold yellow]❌ Error: {type(e).__name__}[/bold yellow]")

    active_c  = sum(1 for _, s in results if s == "active")
    banned_c  = sum(1 for _, s in results if s == "banned")
    error_c   = sum(1 for _, s in results if s == "error")

    console.print()
    console.print(f"  ─── Summary ───────────────────────────────")
    console.print(f"  ✅ Active   : [green]{active_c}[/green]")
    console.print(f"  ⛔ Banned   : [red]{banned_c}[/red]")
    console.print(f"  ❌ Errors   : [yellow]{error_c}[/yellow]")

    input("\n  Press ENTER to continue...")


# ─── Remove Account ──────────────────────────────────────────────────────────

def remove_account_menu():
    print_header("❌  Remove Account")
    accounts = load_accounts()
    if not accounts:
        print_info("No accounts to remove.")
        input("\n  Press ENTER...")
        return
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
    console.print(f"  Found [red]{len(banned)}[/red] banned/error accounts.")
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
            sf = SESSIONS_DIR / f"{b['phone']}.session"
            if sf.exists():
                sf.unlink()
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
    console.print("  [1] Light    — 1 Day")
    console.print("  [2] Moderate — 3 Days")
    console.print("  [3] Intensive — 7 Days  ⭐ Recommended")
    console.print()
    duration_choice = prompt("⏱ Select Duration", "3")
    durations = {"1": 1, "2": 3, "3": 7}
    days = durations.get(duration_choice, 7)

    accounts = load_accounts()
    active = [a for a in accounts if a.get("status") == "active"]
    console.print(f"\n  Active Accounts Available: [green]{len(active)}[/green]")

    if not active:
        print_error("No active accounts found.")
        input("\n  Press ENTER...")
        return

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
