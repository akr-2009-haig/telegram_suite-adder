import urllib.request
import urllib.parse
import json as _json
from modules.utils import (
    console, print_header, print_success, print_error, print_info, print_warn,
    prompt, menu_choice, confirm, now_str,
)
from modules.database import (
    load_notif_log, mark_notifications_read, get_unread_notifications, add_notification,
)
import config


# ─── Menu ─────────────────────────────────────────────────────────────────────

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
            ("7", "❓  How to Get Bot Token & Chat ID"),
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
        elif choice == "7": show_bot_help()
        elif choice == "0": break


# ─── 1. View Notifications ────────────────────────────────────────────────────

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
        col = level_color.get(n.get("level","info"),"white")
        dot = " [bold]●[/bold]" if not n.get("read") else ""
        console.print(
            f"  [dim]{str(n.get('time',''))[:16]}[/dim]{dot}  "
            f"[{col}]{n.get('type','INFO')[:12].upper():<12}[/{col}]  "
            f"[white]{n.get('message','')}[/white]"
        )
    input("\n  Press ENTER...")


# ─── 4. Notification Settings ─────────────────────────────────────────────────

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
        ("scheduler",          "Scheduler task completed"),
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


# ─── 5. Configure Bot ─────────────────────────────────────────────────────────

def configure_bot():
    print_header("🤖  Telegram Bot Alerts")
    cfg       = config.load_settings()
    cur_token = cfg.get("notif_bot_token","")
    cur_cid   = cfg.get("notif_chat_id","")

    if cur_token:
        console.print(f"  Current token  : [dim]{cur_token[:10]}...[/dim]")
        console.print(f"  Current chat ID: [dim]{cur_cid or 'Not set'}[/dim]\n")
    else:
        console.print("  [dim]No bot configured yet.[/dim]\n")
        console.print("  Type [7] in the menu to see setup instructions.\n")

    token = prompt("  Bot Token (ENTER = keep)", cur_token)
    cid   = prompt("  Chat ID   (ENTER = keep)", cur_cid)

    token = token or cur_token
    cid   = cid   or cur_cid

    # Auto-detect chat ID if token given but no chat ID
    if token and not cid:
        console.print("  [dim]Trying to auto-detect chat ID from recent messages...[/dim]")
        cid = _get_chat_id_from_updates(token) or ""
        if cid:
            console.print(f"  [green]✅ Chat ID detected: {cid}[/green]")
        else:
            console.print("  [yellow]Could not auto-detect. Send any message to the bot first, then try again.[/yellow]")

    cfg["notif_bot_token"] = token
    cfg["notif_chat_id"]   = cid
    config.save_settings(cfg)
    print_success("Bot configuration saved.")

    if token and cid and confirm("  Send a test message now?"):
        ok = _send_tg_sync(token, cid,
                           "✅ <b>Telegram Suite</b> — bot alerts configured!\n"
                           "<i>By: Akram Haig | +967772009303</i>")
        if ok:
            print_success("Test message sent successfully!")
        else:
            print_error("Failed to send. Check token / chat ID.")

    input("\n  Press ENTER...")


# ─── 6. Test Notification ─────────────────────────────────────────────────────

def test_notification():
    print_header("🧪  Test Notification")
    add_notification("test", "Test notification from the system.", "success")
    print_success("Added to notification log.")

    cfg   = config.load_settings()
    token = cfg.get("notif_bot_token","")
    cid   = cfg.get("notif_chat_id","")

    if token and cid:
        if confirm("  Also send via Telegram bot?"):
            ok = _send_tg_sync(token, cid,
                               "🧪 <b>Test Notification</b>\n"
                               "This is a test from Telegram Suite.\n"
                               f"<i>{now_str()}</i>")
            if ok:
                print_success("Telegram message sent!")
            else:
                print_error("Failed. Check bot token and chat ID in settings.")
    else:
        print_warn("No bot configured — message only added to local log.")
        print_info("Go to option [5] to configure the bot.")
    input("\n  Press ENTER...")


# ─── 7. Help ──────────────────────────────────────────────────────────────────

def show_bot_help():
    print_header("❓  How to Set Up Bot Alerts")
    console.print("""
  ── Step 1: Create a Bot ──────────────────────────────────────
  1. Open Telegram and search for @BotFather
  2. Send: /newbot
  3. Follow instructions — choose a name and username
  4. Copy the token that looks like:  123456789:ABC-DEF...

  ── Step 2: Get Your Chat ID ──────────────────────────────────
  Method A (automatic):
    • Send any message to your new bot
    • Then go to menu option [5] — it will auto-detect your ID

  Method B (manual):
    • Search for @userinfobot on Telegram
    • Send /start — it shows your chat ID

  ── Step 3: Configure ─────────────────────────────────────────
  • Go to menu option [5] Configure Telegram Bot Alerts
  • Paste your token and chat ID
  • Click test — you should receive a message immediately
""")
    input("  Press ENTER...")


# ─── Core Sender (no external dependencies) ──────────────────────────────────

def _send_tg_sync(token: str, chat_id: str, text: str) -> bool:
    """Send a Telegram message using only stdlib urllib — no aiohttp needed."""
    if not token or not chat_id:
        return False
    url  = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id":    str(chat_id),
        "text":       text,
        "parse_mode": "HTML",
    }).encode()
    try:
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            r = _json.loads(resp.read())
            return r.get("ok", False)
    except Exception:
        return False


def _get_chat_id_from_updates(token: str) -> str:
    """Auto-detect chat ID from the latest message sent to the bot."""
    url = f"https://api.telegram.org/bot{token}/getUpdates?limit=1&offset=-1"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            r = _json.loads(resp.read())
            results = r.get("result", [])
            if results:
                msg = results[-1].get("message") or results[-1].get("channel_post") or {}
                chat = msg.get("chat", {})
                cid  = chat.get("id")
                if cid:
                    return str(cid)
    except Exception:
        pass
    return ""


# ─── Public API: send_alert() ─────────────────────────────────────────────────

def send_alert(event_type: str, message: str, level: str = "info"):
    """
    Log a notification and optionally push via Telegram bot.
    Safe to call from anywhere — fully synchronous, no asyncio needed.
    """
    add_notification(event_type, message, level)

    cfg   = config.load_settings()
    notif = cfg.get("notifications", {})
    if not notif.get(event_type, True):
        return          # user disabled this event type

    token = cfg.get("notif_bot_token","")
    cid   = cfg.get("notif_chat_id","")
    if not (token and cid):
        return          # bot not configured — silent

    icons = {"info":"ℹ️","warn":"⚠️","error":"🚨","success":"✅"}
    full  = (
        f"{icons.get(level,'ℹ️')} <b>{event_type.upper().replace('_',' ')}</b>\n"
        f"{message}\n"
        f"<i>{now_str()}</i>"
    )
    _send_tg_sync(token, cid, full)
