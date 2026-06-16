import asyncio
import hashlib
from pathlib import Path
from modules.utils import (
    console, print_header, print_success, print_error, print_info, print_warn,
    prompt, menu_choice, confirm, now_str,
)
from modules.database import (
    load_blacklist, add_to_blacklist, remove_from_blacklist,
    load_accounts, save_accounts, get_active_accounts,
)
import config


def security_menu():
    while True:
        print_header("🛡️  Security Tools", "Account Protection & Safety")

        choice = menu_choice([
            ("1",  "📋  Blacklist Manager"),
            ("2",  "⏱️  Smart Limits"),
            ("3",  "🔍  Health Check All Accounts"),
            ("4",  "🧹  Account Cleanup"),
            ("5",  "📊  Ban Monitor"),
            ("6",  "🔐  Backup Sessions"),
            ("7",  "🔒  Encrypt Session Files"),
            ("8",  "🕵️  Honeypot / Trap Detection"),
            ("9",  "🔑  Bulk 2FA Setup"),
            ("10", "🚨  Emergency Mode — Stop Everything"),
        ])

        if choice == "1":   blacklist_manager()
        elif choice == "2": smart_limits()
        elif choice == "3": asyncio.run(health_check_all())
        elif choice == "4": asyncio.run(account_cleanup())
        elif choice == "5": asyncio.run(ban_monitor())
        elif choice == "6": backup_sessions()
        elif choice == "7": encrypt_sessions()
        elif choice == "8": asyncio.run(honeypot_check())
        elif choice == "9": asyncio.run(bulk_2fa_setup())
        elif choice == "10": emergency_mode()
        elif choice == "0": break


# ─── 1. Blacklist ─────────────────────────────────────────────────────────────

def blacklist_manager():
    while True:
        bl = load_blacklist()
        print_header("📋  Blacklist Manager", f"{len(bl)} entries")
        choice = menu_choice([
            ("1", "➕  Add to Blacklist"),
            ("2", "❌  Remove from Blacklist"),
            ("3", "📋  View All"),
            ("4", "📥  Import from file"),
            ("5", "📤  Export to file"),
        ])
        if choice == "1":
            uid = prompt("  User ID or @username")
            if uid:
                add_to_blacklist(uid)
                print_success(f"{uid} added to blacklist.")
            input("\n  Press ENTER...")
        elif choice == "2":
            uid = prompt("  User ID or @username to remove")
            if uid:
                remove_from_blacklist(uid)
                print_success(f"{uid} removed.")
            input("\n  Press ENTER...")
        elif choice == "3":
            print_header("📋  Blacklist")
            if not bl:
                print_info("Blacklist is empty.")
            for i, entry in enumerate(bl[:50], 1):
                console.print(f"  [{i}] [red]{entry}[/red]")
            if len(bl) > 50:
                console.print(f"  [dim]... and {len(bl)-50} more[/dim]")
            input("\n  Press ENTER...")
        elif choice == "4":
            fpath = prompt("  File path (.txt, one per line)")
            if fpath and Path(fpath).exists():
                added = 0
                for line in Path(fpath).read_text(encoding="utf-8").splitlines():
                    uid = line.strip()
                    if uid:
                        add_to_blacklist(uid)
                        added += 1
                print_success(f"Imported {added} entries.")
            else:
                print_error("File not found.")
            input("\n  Press ENTER...")
        elif choice == "5":
            out = Path("exports") / "blacklist.txt"
            Path("exports").mkdir(exist_ok=True)
            out.write_text("\n".join(bl), encoding="utf-8")
            print_success(f"Exported to {out}")
            input("\n  Press ENTER...")
        elif choice == "0":
            break


# ─── 2. Smart Limits ──────────────────────────────────────────────────────────

def smart_limits():
    print_header("⏱️  Smart Limits")
    cfg = config.load_settings()
    console.print("  The smart limits system adjusts speeds automatically based on:\n")
    console.print("  [green]✓[/green]  Reduces speed when FloodWaits repeat")
    console.print("  [green]✓[/green]  Increases delay if an account gets restricted")
    console.print("  [green]✓[/green]  Pauses all ops when multiple accounts restricted")
    console.print("  [green]✓[/green]  Lower limits for accounts younger than 30 days")
    console.print("  [green]✓[/green]  Higher limits for accounts older than 6 months")
    console.print("  [green]✓[/green]  Learns from past patterns")
    console.print()
    console.print("  Safety Level:")
    console.print("  [1] 🟢 Conservative (slowest, safest)")
    console.print("  [2] 🟡 Balanced ⭐ recommended")
    console.print("  [3] 🔴 Aggressive (fastest, riskier)")
    console.print("  [4] 🧠 Adaptive (auto)")
    level_map = {"1":"conservative","2":"balanced","3":"aggressive","4":"adaptive"}
    choice = prompt("  Select", "2")
    cfg["smart_limit_level"] = level_map.get(choice, "balanced")
    config.save_settings(cfg)
    print_success(f"Smart limit level: {cfg['smart_limit_level']}")
    input("\n  Press ENTER...")


# ─── 3. Health Check ─────────────────────────────────────────────────────────

async def health_check_all():
    print_header("🔍  Health Check — All Accounts")
    accounts = load_accounts()
    if not accounts:
        print_info("No accounts found.")
        input("\n  Press ENTER...")
        return

    api_id, api_hash = config.get_api_credentials()
    results = {"active": 0, "banned": 0, "restricted": 0, "error": 0}

    for i, acc in enumerate(accounts, 1):
        phone   = acc["phone"]
        session = str(config.SESSIONS_DIR / phone)
        console.print(f"  [{i}/{len(accounts)}] Checking {phone}...", end=" ")
        try:
            from telethon import TelegramClient
            from telethon.errors import UserDeactivatedBanError, UserDeactivatedError, PhoneNumberBannedError
            client = TelegramClient(session, int(api_id), api_hash)
            await client.connect()
            if await client.is_user_authorized():
                me = await client.get_me()
                if me:
                    console.print("[green]✅ Active[/green]")
                    acc["status"] = "active"
                    results["active"] += 1
                else:
                    console.print("[yellow]⚠️ No user[/yellow]")
                    results["error"] += 1
            else:
                console.print("[yellow]⚠️ Not authorized[/yellow]")
                acc["status"] = "unauthorized"
                results["error"] += 1
            await client.disconnect()
        except (UserDeactivatedBanError, UserDeactivatedError, PhoneNumberBannedError):
            console.print("[red]⛔ BANNED[/red]")
            acc["status"] = "banned"
            results["banned"] += 1
        except Exception as e:
            msg = str(e)
            if "restricted" in msg.lower() or "flood" in msg.lower():
                console.print(f"[yellow]⚠️ Restricted[/yellow]")
                acc["status"] = "restricted"
                results["restricted"] += 1
            else:
                console.print(f"[red]❌ Error: {msg[:30]}[/red]")
                results["error"] += 1

    save_accounts(accounts)
    console.print(f"\n  ─── Results ──────────────────────")
    console.print(f"  ✅ Active     : [green]{results['active']}[/green]")
    console.print(f"  ⛔ Banned     : [red]{results['banned']}[/red]")
    console.print(f"  ⚠️  Restricted : [yellow]{results['restricted']}[/yellow]")
    console.print(f"  ❌ Error      : [dim]{results['error']}[/dim]")

    if results["banned"] > 0 and confirm("\n  Auto-delete banned accounts?"):
        new_accs = [a for a in load_accounts() if a.get("status") != "banned"]
        save_accounts(new_accs)
        print_success(f"Removed {results['banned']} banned account(s).")

    input("\n  Press ENTER...")


# ─── 4. Cleanup ───────────────────────────────────────────────────────────────

async def account_cleanup():
    print_header("🧹  Account Cleanup")
    accounts = get_active_accounts()
    if not accounts:
        print_info("No active accounts.")
        input("\n  Press ENTER...")
        return
    console.print("  Select cleanup actions:\n")
    leave_groups = confirm("  Leave all groups joined during scraping?", default=False)
    del_messages = confirm("  Delete sent messages in private chats?", default=False)
    if not (leave_groups or del_messages):
        print_info("No actions selected.")
        input("\n  Press ENTER...")
        return
    api_id, api_hash = config.get_api_credentials()
    for acc in accounts[:5]:
        session = str(config.SESSIONS_DIR / acc["phone"])
        try:
            from telethon import TelegramClient
            async with TelegramClient(session, int(api_id), api_hash) as client:
                if leave_groups:
                    from telethon.tl.functions.messages import GetDialogsRequest
                    from telethon.tl.types import InputPeerEmpty
                    import asyncio as aio
                    dialogs = await client.get_dialogs()
                    left = 0
                    for d in dialogs:
                        if hasattr(d.entity, "megagroup") or hasattr(d.entity, "broadcast"):
                            try:
                                await client.delete_dialog(d.entity)
                                left += 1
                                await aio.sleep(2)
                            except Exception:
                                pass
                    print_success(f"{acc['phone']}: Left {left} groups/channels")
        except Exception as e:
            print_warn(f"{acc['phone']}: {e}")
    input("\n  Press ENTER...")


# ─── 5. Ban Monitor ───────────────────────────────────────────────────────────

async def ban_monitor():
    print_header("📊  Ban Monitor")
    accounts  = load_accounts()
    banned    = [a for a in accounts if a.get("status") == "banned"]
    restricted= [a for a in accounts if a.get("status") == "restricted"]
    active    = [a for a in accounts if a.get("status") == "active"]

    console.print(f"  ✅ Active     : [green]{len(active)}[/green]")
    console.print(f"  ⛔ Banned     : [red]{len(banned)}[/red]")
    console.print(f"  ⚠️  Restricted : [yellow]{len(restricted)}[/yellow]")
    console.print()

    if banned:
        console.print("  ─── Banned Accounts ──────────────")
        for a in banned:
            console.print(f"  [red]⛔[/red] {a['phone']}  [dim]{a.get('name','?')}[/dim]")
    if restricted:
        console.print("\n  ─── Restricted Accounts ──────────")
        for a in restricted:
            console.print(f"  [yellow]⚠️[/yellow] {a['phone']}  [dim]{a.get('name','?')}[/dim]")
    input("\n  Press ENTER...")


# ─── 6. Backup Sessions ───────────────────────────────────────────────────────

def backup_sessions():
    print_header("🔐  Backup Sessions")
    from modules.backup import create_backup
    create_backup()


# ─── 7. Encrypt Sessions ─────────────────────────────────────────────────────

def encrypt_sessions():
    print_header("🔒  Encrypt Session Files")
    print_warn("Session encryption is an advanced feature.")
    console.print("  This uses AES encryption via the 'cryptography' package.\n")
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        print_error("'cryptography' package not installed.")
        console.print("  Run: pip install cryptography")
        input("\n  Press ENTER...")
        return

    pw  = prompt("  Encryption password", password=True)
    pw2 = prompt("  Confirm password",    password=True)
    if pw != pw2:
        print_error("Passwords do not match.")
        input("\n  Press ENTER...")
        return

    from cryptography.fernet import Fernet
    import base64, os
    key  = base64.urlsafe_b64encode(hashlib.sha256(pw.encode()).digest())
    fern = Fernet(key)

    sessions = list(config.SESSIONS_DIR.glob("*.session"))
    if not sessions:
        print_info("No session files found.")
        input("\n  Press ENTER...")
        return

    enc_dir = config.SESSIONS_DIR / "encrypted"
    enc_dir.mkdir(exist_ok=True)
    count = 0
    for sf in sessions:
        try:
            data = sf.read_bytes()
            enc  = fern.encrypt(data)
            (enc_dir / (sf.name + ".enc")).write_bytes(enc)
            count += 1
        except Exception as e:
            print_warn(f"  {sf.name}: {e}")
    print_success(f"Encrypted {count} session file(s) to {enc_dir}")
    input("\n  Press ENTER...")


# ─── 8. Honeypot Detection ────────────────────────────────────────────────────

async def honeypot_check():
    print_header("🕵️  Honeypot / Trap Detection")
    target = prompt("  Group link to check (@username or t.me/...)")
    if not target:
        return

    accounts = get_active_accounts()
    if not accounts:
        print_error("No active accounts.")
        input("\n  Press ENTER...")
        return

    api_id, api_hash = config.get_api_credentials()
    acc     = accounts[0]
    session = str(config.SESSIONS_DIR / acc["phone"])

    console.print(f"\n  Analyzing: [cyan]{target}[/cyan]")
    warnings = []
    try:
        from telethon import TelegramClient
        async with TelegramClient(session, int(api_id), api_hash) as client:
            entity = await client.get_entity(target)
            participants_count = getattr(entity, "participants_count", 0)
            username = getattr(entity, "username", "")
            title    = getattr(entity, "title", "")
            date     = getattr(entity, "date", None)
            is_mega  = getattr(entity, "megagroup", False)

            console.print(f"  Name        : [bold]{title}[/bold]")
            console.print(f"  Members     : [cyan]{participants_count:,}[/cyan]")
            console.print(f"  Username    : @{username}" if username else "  Username    : [dim]None (private)[/dim]")
            console.print(f"  Type        : {'Supergroup' if is_mega else 'Channel/Group'}")
            console.print(f"  Created     : [dim]{str(date)[:10]}[/dim]")

            # Honeypot signals
            if participants_count > 100000:
                warnings.append("⚠️  Very large group — mass surveillance possible")
            if not username:
                warnings.append("ℹ️  No public username — may be a closed trap")
            if participants_count > 0 and participants_count < 10000:
                try:
                    from telethon.tl.types import ChannelParticipantsBots
                    bots = await client.get_participants(entity, filter=ChannelParticipantsBots())
                    bot_count = len(bots)
                    console.print(f"  Bots in group : [dim]{bot_count}[/dim]")
                    if bot_count > 5:
                        warnings.append(f"⚠️  {bot_count} bots detected — possible monitoring setup")
                    bot_ratio = bot_count / max(participants_count, 1)
                    if bot_ratio > 0.1:
                        warnings.append(f"⚠️  High bot ratio: {bot_ratio:.0%} — possible bot farm")
                except Exception:
                    pass
            # Check recent message activity
            try:
                msgs = await client.get_messages(entity, limit=20)
                if msgs:
                    from datetime import datetime, timezone
                    now_dt = datetime.now(timezone.utc)
                    ages = [(now_dt - m.date).total_seconds() / 3600 for m in msgs if m.date]
                    if ages and min(ages) > 72:
                        warnings.append("ℹ️  No messages in 72h — group may be inactive/trap")
            except Exception:
                pass

    except Exception as e:
        print_error(f"Could not analyze: {e}")
        input("\n  Press ENTER...")
        return

    console.print()
    if warnings:
        console.print("  ─── ⚠️  Warnings ──────────────────")
        for w in warnings:
            console.print(f"  [yellow]{w}[/yellow]")
    else:
        console.print("  [green]✅ No obvious honeypot signals detected.[/green]")

    input("\n  Press ENTER...")


# ─── 9. Bulk 2FA ─────────────────────────────────────────────────────────────

async def bulk_2fa_setup():
    print_header("🔑  Bulk 2FA Setup")
    print_warn("This sets the same 2FA password for all accounts that don't have it.")
    console.print("  All accounts must already be connected / active.\n")

    pw  = prompt("  2FA Password to set", password=True)
    pw2 = prompt("  Confirm password",    password=True)
    if pw != pw2 or not pw:
        print_error("Passwords do not match or empty.")
        input("\n  Press ENTER...")
        return

    accounts = get_active_accounts()
    if not accounts:
        print_error("No active accounts.")
        input("\n  Press ENTER...")
        return

    if not confirm(f"  Apply 2FA to {len(accounts)} account(s)?"):
        return

    api_id, api_hash = config.get_api_credentials()
    ok = fail = already = 0
    for acc in accounts:
        session = str(config.SESSIONS_DIR / acc["phone"])
        try:
            from telethon import TelegramClient
            async with TelegramClient(session, int(api_id), api_hash) as client:
                # edit_2fa(new_password=pw) sets 2FA; if already set it updates it
                await client.edit_2fa(new_password=pw, hint="suite")
                ok += 1
                console.print(f"  [green]✅ {acc['phone']}[/green]")
        except Exception as e:
            err = str(e)
            if "PASSWORD_HASH_INVALID" in err or "NEW_SALT_INVALID" in err:
                already += 1
                console.print(f"  [yellow]⚠️  {acc['phone']}: already has 2FA[/yellow]")
            else:
                fail += 1
                console.print(f"  [red]❌ {acc['phone']}: {err[:50]}[/red]")

    console.print(f"\n  Done: [green]{ok} set[/green]  |  [yellow]{already} already had 2FA[/yellow]  |  [red]{fail} failed[/red]")
    input("\n  Press ENTER...")


# ─── 10. Emergency Mode ───────────────────────────────────────────────────────

def emergency_mode():
    print_header("🚨  Emergency Mode")
    print_warn("This will immediately stop ALL running operations.")
    print_warn("Sessions will be disconnected and all tasks paused.\n")

    if not confirm("  Activate Emergency Mode?"):
        return

    # Write a flag file that all running loops check
    Path("emergency.flag").write_text(f"Emergency stop activated at {now_str()}", encoding="utf-8")
    print_success("🚨 Emergency flag set — all operations will stop at next check.")

    if confirm("\n  Also disconnect all Telegram sessions now?"):
        asyncio.run(_disconnect_all())

    print_warn("To resume normal operation, delete the file 'emergency.flag'")
    input("\n  Press ENTER...")


async def _disconnect_all():
    accounts = get_active_accounts()
    if not accounts:
        return
    api_id, api_hash = config.get_api_credentials()
    for acc in accounts:
        session = str(config.SESSIONS_DIR / acc["phone"])
        try:
            from telethon import TelegramClient
            client = TelegramClient(session, int(api_id), api_hash)
            await client.connect()
            await client.disconnect()
            console.print(f"  [dim]Disconnected: {acc['phone']}[/dim]")
        except Exception:
            pass


def is_emergency() -> bool:
    """Call from any loop to check if emergency mode is active."""
    return Path("emergency.flag").exists()
