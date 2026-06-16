import asyncio
import random
import time
from pathlib import Path
from modules.utils import (
    console, print_header, print_success, print_error, print_info, print_warn,
    prompt, menu_choice, confirm, now_str,
)
from modules.database import (
    load_accounts, get_active_accounts, increment_stat,
    load_templates, save_templates, add_template, delete_template,
)
from modules.security import is_emergency
import config


def bulk_messaging_menu():
    while True:
        print_header("💬  Bulk Messaging", "Send messages to multiple users")

        choice = menu_choice([
            ("1", "📝  Compose & Send New Message"),
            ("2", "📋  Select Recipients List"),
            ("3", "📂  Import Recipients from File"),
            ("4", "⏰  Schedule Message"),
            ("5", "📊  Message History / Log"),
            ("6", "📎  Send with Media (Photo / Video / File)"),
            ("7", "🔄  Message Templates"),
            ("8", "🎲  Spin / Rotate Message Variants"),
            ("9", "📈  Read Rate Tracker"),
        ])

        if choice == "1":   asyncio.run(compose_and_send())
        elif choice == "2": select_recipients()
        elif choice == "3": import_recipients()
        elif choice == "4": schedule_message()
        elif choice == "5": message_history()
        elif choice == "6": asyncio.run(send_with_media())
        elif choice == "7": templates_menu()
        elif choice == "8": spin_message_menu()
        elif choice == "9": read_rate_menu()
        elif choice == "0": break


# ─── 1. Compose & Send ────────────────────────────────────────────────────────

async def compose_and_send(recipients: list = None, text: str = None, media_path: str = None):
    print_header("📝  Compose & Send")

    if text is None:
        console.print("  Available variables: {first_name}, {last_name}, {username}\n")
        text = prompt("  Message text")
        if not text:
            return

    if recipients is None:
        src = prompt("  Recipients CSV file (ENTER to enter usernames manually)")
        if src and Path(src).exists():
            recipients = _load_recipients_file(src)
        else:
            console.print("  Enter usernames (one per line, blank to finish):")
            recipients = []
            while True:
                line = prompt(f"  [{len(recipients)+1}]", "")
                if not line: break
                recipients.append({"username": line.strip("@ ")})

    if not recipients:
        print_error("No recipients.")
        input("\n  Press ENTER...")
        return

    accounts   = get_active_accounts()
    if not accounts:
        print_error("No active accounts.")
        input("\n  Press ENTER...")
        return

    cfg       = config.load_settings()
    delay_min = cfg.get("delay_min", 60)
    delay_max = cfg.get("delay_max", 120)
    msg_limit = cfg.get("msg_limit", 30)
    api_id, api_hash = config.get_api_credentials()

    console.print(f"\n  Recipients : [bold]{len(recipients)}[/bold]")
    console.print(f"  Accounts   : [bold]{len(accounts)}[/bold] (rotating)")
    console.print(f"  Delay      : [bold]{delay_min}–{delay_max}s[/bold]")
    console.print(f"  Limit/acc  : [bold]{msg_limit}/day[/bold]")

    if not confirm("\n  Start sending?"):
        return

    sent = failed = skipped = 0
    log_path = Path("logs") / "messages.log"
    log_path.parent.mkdir(exist_ok=True)

    acc_idx   = 0
    acc_count = 0

    for i, rec in enumerate(recipients, 1):
        if is_emergency():
            print_warn("Emergency mode — stopping.")
            break

        # Rotate accounts
        if acc_count >= msg_limit:
            acc_idx   = (acc_idx + 1) % len(accounts)
            acc_count = 0
            wait = random.randint(300, 600)
            console.print(f"  [cyan]Switching account — waiting {wait}s...[/cyan]")
            await asyncio.sleep(wait)

        acc     = accounts[acc_idx]
        session = str(config.SESSIONS_DIR / acc["phone"])

        username   = rec.get("username") or rec.get("user_id","")
        first_name = rec.get("first_name","Friend")
        last_name  = rec.get("last_name","")

        personalized = text.replace("{first_name}", first_name)\
                           .replace("{last_name}",  last_name)\
                           .replace("{username}",   str(username))

        progress = f"[{i}/{len(recipients)}]"
        try:
            from telethon import TelegramClient
            client = TelegramClient(session, int(api_id), api_hash)
            await client.connect()
            if not await client.is_user_authorized():
                skipped += 1
                await client.disconnect()
                continue

            if media_path and Path(media_path).exists():
                await client.send_file(username, media_path, caption=personalized)
            else:
                await client.send_message(username, personalized)

            await client.disconnect()
            sent += 1
            acc_count += 1
            increment_stat("messages","sent")
            console.print(f"  {progress}  [green]✅[/green] @{username}")
            with open(log_path, "a", encoding="utf-8") as lf:
                lf.write(f"{now_str()} SUCCESS @{username} via {acc['phone']}\n")

        except Exception as e:
            failed += 1
            err = str(e)[:40]
            console.print(f"  {progress}  [red]❌[/red] @{username} — {err}")
            increment_stat("messages","failed")
            with open(log_path, "a", encoding="utf-8") as lf:
                lf.write(f"{now_str()} FAILED @{username} — {err}\n")

        if i < len(recipients):
            delay = random.randint(delay_min, delay_max)
            console.print(f"  [dim]Waiting {delay}s...[/dim]")
            await asyncio.sleep(delay)

    console.print(f"\n  ─── Summary ─────────────────────────")
    console.print(f"  ✅ Sent    : [green]{sent}[/green]")
    console.print(f"  ❌ Failed  : [red]{failed}[/red]")
    console.print(f"  ⏭️  Skipped : [yellow]{skipped}[/yellow]")
    input("\n  Press ENTER...")


def _load_recipients_file(path: str) -> list:
    import csv
    recipients = []
    try:
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                recipients.append({
                    "user_id":    row.get("user_id",""),
                    "username":   row.get("username",""),
                    "first_name": row.get("first_name",""),
                    "last_name":  row.get("last_name",""),
                })
    except Exception as e:
        print_error(f"Could not read file: {e}")
    return recipients


# ─── 2. Select Recipients ─────────────────────────────────────────────────────

def select_recipients():
    print_header("📋  Select Recipients")
    exports = sorted(Path("exports").glob("*.csv")) if Path("exports").exists() else []
    if not exports:
        print_info("No exported CSV files found. Scrape members first.")
        input("\n  Press ENTER...")
        return
    for i, f in enumerate(exports, 1):
        size = f.stat().st_size // 1024
        console.print(f"  [{i}] {f.name}  [dim]{size} KB[/dim]")
    ch = prompt("\n  Select file #")
    if ch.isdigit() and 1 <= int(ch) <= len(exports):
        path = str(exports[int(ch)-1])
        console.print(f"  [green]Selected: {path}[/green]")
        console.print("  Now go to option 1 (Compose & Send) and enter this path.")
    input("\n  Press ENTER...")


# ─── 3. Import Recipients ─────────────────────────────────────────────────────

def import_recipients():
    print_header("📂  Import Recipients from File")
    console.print("  Supported formats: CSV (with headers), TXT (one username per line)\n")
    path = prompt("  File path")
    if not path or not Path(path).exists():
        print_error("File not found.")
        input("\n  Press ENTER...")
        return
    if path.endswith(".csv"):
        recs = _load_recipients_file(path)
    else:
        recs = [{"username": l.strip().strip("@")} for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    print_success(f"Loaded {len(recs)} recipients from {Path(path).name}")
    console.print("  Use option 1 (Compose & Send) and enter this file path.")
    input("\n  Press ENTER...")


# ─── 4. Schedule Message ──────────────────────────────────────────────────────

def schedule_message():
    print_header("⏰  Schedule Message")
    console.print("  This creates a scheduled task — use the Scheduler (menu 12) to manage it.\n")
    text = prompt("  Message text")
    path = prompt("  Recipients CSV file")
    date = prompt("  Date (YYYY-MM-DD)", __import__("datetime").datetime.now().strftime("%Y-%m-%d"))
    time_str = prompt("  Time (HH:MM)", "09:00")
    if text and path:
        from modules.database import add_schedule
        task_id = add_schedule({
            "name":      f"Bulk message — {date} {time_str}",
            "operation": "bulk_message",
            "schedule":  f"{date} {time_str}",
            "stype":     "1",
            "params":    {"text": text, "source_file": path},
            "notify":    True,
        })
        print_success(f"Scheduled as Task #{task_id}")
    input("\n  Press ENTER...")


# ─── 5. Message History ───────────────────────────────────────────────────────

def message_history():
    print_header("📊  Message History")
    log_path = Path("logs") / "messages.log"
    if not log_path.exists():
        print_info("No message log found.")
        input("\n  Press ENTER...")
        return
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    recent = lines[-40:]
    for line in recent:
        if "SUCCESS" in line:
            console.print(f"  [green]{line}[/green]")
        elif "FAILED" in line:
            console.print(f"  [red]{line}[/red]")
        else:
            console.print(f"  [dim]{line}[/dim]")
    console.print(f"\n  [dim]Showing last {len(recent)} of {len(lines)} lines[/dim]")
    input("\n  Press ENTER...")


# ─── 6. Send with Media ───────────────────────────────────────────────────────

async def send_with_media():
    print_header("📎  Send with Media")
    console.print("  Supported: JPG, PNG, MP4, PDF, any file\n")
    media_path = prompt("  Media file path")
    if not media_path or not Path(media_path).exists():
        print_error("File not found.")
        input("\n  Press ENTER...")
        return
    caption = prompt("  Caption text (optional, use {first_name} etc.)")
    src     = prompt("  Recipients CSV file")
    recipients = _load_recipients_file(src) if src and Path(src).exists() else []
    if not recipients:
        print_error("No recipients.")
        input("\n  Press ENTER...")
        return
    await compose_and_send(recipients=recipients, text=caption or "", media_path=media_path)


# ─── 7. Templates ─────────────────────────────────────────────────────────────

def templates_menu():
    while True:
        templates = load_templates()
        print_header("🔄  Message Templates", f"{len(templates)} saved")
        choice = menu_choice([
            ("1", "➕  Create Template"),
            ("2", "📋  View Templates"),
            ("3", "📋  Use Template"),
            ("4", "❌  Delete Template"),
        ])
        if choice == "1":
            name = prompt("  Template name")
            text = prompt("  Template text (use {first_name} etc.)")
            cat  = prompt("  Category (optional)", "general")
            if name and text:
                add_template(name, text, cat)
                print_success("Template saved.")
            input("\n  Press ENTER...")
        elif choice == "2":
            print_header("📋  Templates")
            if not templates:
                print_info("No templates.")
            for t in templates:
                console.print(f"  [dim]#{t['id']}[/dim]  [bold cyan]{t['name']:<25}[/bold cyan]  [white]{t['text'][:50]}[/white]")
            input("\n  Press ENTER...")
        elif choice == "3":
            if not templates:
                print_info("No templates saved.")
                input("\n  Press ENTER...")
                continue
            for t in templates:
                console.print(f"  [{t['id']}] {t['name']}")
            tid = prompt("  Template #")
            if tid.isdigit():
                tmpl = next((t for t in templates if t["id"] == int(tid)), None)
                if tmpl:
                    console.print(f"\n  Text: [cyan]{tmpl['text']}[/cyan]\n")
                    templates_list = load_templates()
                    for i, t in enumerate(templates_list):
                        if t["id"] == int(tid):
                            templates_list[i]["used_count"] = t.get("used_count",0)+1
                    save_templates(templates_list)
                    asyncio.run(compose_and_send(text=tmpl["text"]))
                    return
            input("\n  Press ENTER...")
        elif choice == "4":
            for t in templates:
                console.print(f"  [{t['id']}] {t['name']}")
            tid = prompt("  Template # to delete")
            if tid.isdigit():
                delete_template(int(tid))
                print_success("Deleted.")
            input("\n  Press ENTER...")
        elif choice == "0":
            break


# ─── 8. Spin / Rotate Variants ────────────────────────────────────────────────

def spin_message_menu():
    print_header("🎲  Message Spinning / Rotation")
    console.print("  Enter {word1|word2|word3} to create variants.\n")
    console.print("  Example: Hello {friend|buddy|mate}, check this {link|URL|page}!")
    console.print("  Each recipient will get a different variant.\n")
    text = prompt("  Message with spin syntax")
    if not text:
        return
    count = int(prompt("  Preview how many variants?", "3") or 3)
    console.print(f"\n  ─── {count} Sample Variants ───────────────")
    for i in range(count):
        spun = _spin(text)
        console.print(f"  [{i+1}] {spun}")
    console.print()
    if confirm("  Use this for sending?"):
        asyncio.run(compose_and_send(text=text))


def _spin(text: str) -> str:
    import re
    def replacer(m):
        options = m.group(1).split("|")
        return random.choice(options)
    return re.sub(r"\{([^}]+)\}", replacer, text)


# ─── 9. Read Rate ─────────────────────────────────────────────────────────────

def read_rate_menu():
    print_header("📈  Read Rate Tracker")
    print_info("Telegram doesn't expose read receipts for most accounts.")
    console.print("  However, we can track [bold]reply rate[/bold] from recipients.\n")
    log_path = Path("logs") / "messages.log"
    if not log_path.exists():
        print_info("No message log found yet.")
        input("\n  Press ENTER...")
        return
    lines = log_path.read_text(encoding="utf-8").splitlines()
    success = sum(1 for l in lines if "SUCCESS" in l)
    failed  = sum(1 for l in lines if "FAILED"  in l)
    total   = success + failed
    rate    = f"{success/total*100:.1f}%" if total else "0%"
    console.print(f"  Total Sent   : [bold]{total}[/bold]")
    console.print(f"  Delivered    : [green]{success}[/green]")
    console.print(f"  Failed       : [red]{failed}[/red]")
    console.print(f"  Delivery Rate: [bold cyan]{rate}[/bold cyan]")
    input("\n  Press ENTER...")
