import asyncio
from modules.utils import (
    console, print_header, print_success, print_error, print_info, print_warn,
    prompt, menu_choice, confirm, now_str,
)
from modules.database import (
    load_notif_log, mark_notifications_read, get_unread_notifications, add_notification,
)
import config


def notifications_menu():
    while True:
        unread = len(get_unread_notifications())
        print_header("🔔  Notification Center", f"Unread: {unread}")

        choice = menu_choice([
            ("1", "📋  View All Notifications"),
            ("2", "🔔  View Unread Only"),
            ("3", "✅  Mark All as Read"),
            ("4", "⚙️  Notification Settings"),
            ("5", "🤖  Configure Telegram Bot Alerts"),
            ("6", "🧪  Send Test Notification"),
        ])

        if choice == "1":   view_notifications(unread_only=False)
        elif choice == "2": view_notifications(unread_only=True)
        elif choice == "3":
            mark_notifications_read()
            print_success("All marked as read.")
            input("\n  Press ENTER...")
        elif choice == "4": notification_settings()
        elif choice == "5": configure_bot()
        elif choice == "6": test_notification()
        elif choice == "0": break


def view_notifications(unread_only: bool = False):
    title = "Notifications (Unread)" if unread_only else "All Notifications"
    print_header(f"📋  {title}")
    log = load_notif_log()
    if unread_only:
        log = [n for n in log if not n.get("read")]
    log = list(reversed(log))[:50]
    if not log:
        print_info("No notifications.")
        input("\n  Press ENTER...")
        return
    level_color = {"info":"cyan","warn":"yellow","error":"red","success":"green"}
    for n in log:
        col    = level_color.get(n.get("level","info"),"white")
        dot    = "" if n.get("read") else " [bold]●[/bold]"
        console.print(
            f"  [dim]{str(n.get('time',''))[:16]}[/dim]{dot}  "
            f"[{col}]{n.get('type','INFO')[:12].upper():<12}[/{col}]  "
            f"[white]{n.get('message','')}[/white]"
        )
    input("\n  Press ENTER...")


def notification_settings():
    print_header("⚙️  Notification Settings")
    cfg   = config.load_settings()
    notif = cfg.get("notifications", {})
    events = [
        ("account_banned",     "Account banned"),
        ("account_restricted", "Account restricted"),
        ("scrape_done",        "Scraping completed"),
        ("add_done",           "Adding completed"),
        ("proxy_failed",       "Proxy failed"),
        ("limit_reached",      "Daily limit reached"),
        ("flood_wait",         "FloodWait triggered"),
        ("daily_report",       "Daily summary report"),
        ("emergency",          "Emergency mode"),
    ]
    console.print("  Toggle notifications (y = on, n = off):\n")
    updated = {}
    for key, label in events:
        current = notif.get(key, True)
        mark    = "[green]ON [/green]" if current else "[red]OFF[/red]"
        val = prompt(f"  [{mark}] {label}", "y" if current else "n")
        updated[key] = val.lower().startswith("y")
    cfg["notifications"] = updated
    config.save_settings(cfg)
    print_success("Settings saved.")
    input("\n  Press ENTER...")


def configure_bot():
    print_header("🤖  Telegram Bot Alerts")
    console.print("  You need:")
    console.print("  1. A bot token — create via @BotFather on Telegram")
    console.print("  2. Your chat ID — get from @userinfobot\n")
    cfg = config.load_settings()
    cur_token = cfg.get("notif_bot_token","")
    cur_cid   = cfg.get("notif_chat_id","")
    if cur_token:
        console.print(f"  Current token  : [dim]{cur_token[:10]}...[/dim]")
        console.print(f"  Current chat ID: [dim]{cur_cid}[/dim]\n")
    token = prompt("  Bot Token (ENTER keep)", cur_token)
    cid   = prompt("  Chat ID   (ENTER keep)", cur_cid)
    cfg["notif_bot_token"] = token or cur_token
    cfg["notif_chat_id"]   = cid   or cur_cid
    config.save_settings(cfg)
    if confirm("  Send a test message now?"):
        asyncio.run(_send_tg(token or cur_token, cid or cur_cid,
                             "✅ Telegram Suite — bot alerts configured!\nBy: Akram Haig | +967772009303"))
    print_success("Bot configuration saved.")
    input("\n  Press ENTER...")


def test_notification():
    print_header("🧪  Test Notification")
    add_notification("test", "Test notification from the system.", "success")
    print_success("Added to notification log.")
    cfg   = config.load_settings()
    token = cfg.get("notif_bot_token","")
    cid   = cfg.get("notif_chat_id","")
    if token and cid and confirm("  Also send via Telegram bot?"):
        asyncio.run(_send_tg(token, cid, "🧪 Test from Telegram Suite."))
    input("\n  Press ENTER...")


async def _send_tg(token: str, chat_id: str, text: str):
    if not token or not chat_id:
        print_warn("Bot token or chat ID not set.")
        return
    try:
        import aiohttp
        async with aiohttp.ClientSession() as s:
            async with s.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                r = await resp.json()
                if r.get("ok"):
                    print_success("Telegram message sent.")
                else:
                    print_error(f"Bot error: {r.get('description','unknown')}")
    except ImportError:
        print_warn("aiohttp not installed. Run: pip install aiohttp")
    except Exception as e:
        print_error(f"Send failed: {e}")


def send_alert(event_type: str, message: str, level: str = "info"):
    """Utility — log + optionally push a Telegram notification."""
    add_notification(event_type, message, level)
    cfg   = config.load_settings()
    notif = cfg.get("notifications", {})
    if not notif.get(event_type, True):
        return
    token = cfg.get("notif_bot_token","")
    cid   = cfg.get("notif_chat_id","")
    if not (token and cid):
        return
    icons = {"info":"ℹ️","warn":"⚠️","error":"🚨","success":"✅"}
    full  = f"{icons.get(level,'ℹ️')} <b>{event_type.upper()}</b>\n{message}\n<i>{now_str()}</i>"
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_send_tg(token, cid, full))
        else:
            loop.run_until_complete(_send_tg(token, cid, full))
    except Exception:
        pass
