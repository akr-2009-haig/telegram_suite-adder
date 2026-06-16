from modules.utils import (
    console, print_header, print_success, print_error, print_info, print_warn,
    prompt, menu_choice, confirm,
)
import config


def settings_menu():
    while True:
        print_header("⚙️  Settings", "System Configuration")
        cfg = config.load_settings()
        api_id   = cfg.get("api_id","Not set")
        api_hash = cfg.get("api_hash","Not set")
        night    = "[green]ON[/green]" if cfg.get("night_mode") else "[dim]OFF[/dim]"
        notif    = "[green]ON[/green]" if cfg.get("notif_bot_token") else "[dim]OFF[/dim]"
        passwd   = "[green]SET[/green]" if cfg.get("tool_password") else "[dim]NOT SET[/dim]"
        autoback = cfg.get("auto_backup_freq","disabled")

        console.print(f"  API ID:        [cyan]{api_id}[/cyan]")
        console.print(f"  API Hash:      [cyan]{str(api_hash)[:8]}...[/cyan]" if api_hash != "Not set" else f"  API Hash:      [dim]Not set[/dim]")
        console.print()

        choice = menu_choice([
            ("1",  f"🔑  API ID / API Hash"),
            ("2",  f"📤  Daily Add Limit per Account       [{cfg.get('add_limit',20)}]"),
            ("3",  f"📥  Daily Scrape Limit per Account    [{cfg.get('scrape_limit',500)}]"),
            ("4",  f"💬  Daily Messages Limit per Account  [{cfg.get('msg_limit',30)}]"),
            ("5",  f"⏱️  Default Delay (seconds)           [{cfg.get('delay_min',60)}–{cfg.get('delay_max',120)}]"),
            ("6",  f"📁  Sessions / Export / Logs paths"),
            ("7",  f"🔔  Notifications                     [{notif}]"),
            ("8",  f"📊  Verbose Logging                   [{'ON' if cfg.get('verbose_log') else 'OFF'}]"),
            ("9",  f"🌙  Night Mode (12am–7am)              [{night}]"),
            ("10", f"🤖  Telegram Bot Alerts               [{notif}]"),
            ("11", f"🔐  Tool Password                     [{passwd}]"),
            ("12", f"📦  Auto-Backup                       [{autoback}]"),
            ("13", f"🧹  Auto Log Cleanup"),
            ("14", "🔄  Reset to Defaults"),
        ])

        if choice == "1":   set_api_keys()
        elif choice == "2": set_limit("add_limit",     "Daily Add Limit",     "20")
        elif choice == "3": set_limit("scrape_limit",  "Daily Scrape Limit",  "500")
        elif choice == "4": set_limit("msg_limit",     "Daily Msg Limit",     "30")
        elif choice == "5": set_delay()
        elif choice == "6": set_paths()
        elif choice == "7": toggle_setting("notifications_enabled", "Notifications")
        elif choice == "8": toggle_setting("verbose_log", "Verbose Logging")
        elif choice == "9": set_night_mode()
        elif choice == "10": set_bot_alerts()
        elif choice == "11": set_tool_password()
        elif choice == "12": set_auto_backup()
        elif choice == "13": set_log_cleanup()
        elif choice == "14": reset_defaults()
        elif choice == "0": break


def set_api_keys():
    print_header("🔑  API Credentials")
    cfg  = config.load_settings()
    console.print("  Get your credentials from https://my.telegram.org\n")
    api_id   = prompt("  API ID",   cfg.get("api_id",""))
    api_hash = prompt("  API Hash", cfg.get("api_hash",""))
    if api_id:   cfg["api_id"]   = api_id
    if api_hash: cfg["api_hash"] = api_hash
    config.save_settings(cfg)
    print_success("API credentials saved.")
    input("\n  Press ENTER...")


def set_limit(key: str, label: str, default: str):
    print_header(f"  {label}")
    cfg = config.load_settings()
    val = prompt(f"  {label}", str(cfg.get(key, default)))
    if val.isdigit():
        cfg[key] = int(val)
        config.save_settings(cfg)
        print_success(f"{label} set to {val}.")
    else:
        print_error("Invalid number.")
    input("\n  Press ENTER...")


def set_delay():
    print_header("⏱️  Default Delay")
    cfg     = config.load_settings()
    dmin    = prompt("  Min delay (seconds)", str(cfg.get("delay_min",60)))
    dmax    = prompt("  Max delay (seconds)", str(cfg.get("delay_max",120)))
    if dmin.isdigit() and dmax.isdigit():
        cfg["delay_min"] = int(dmin)
        cfg["delay_max"] = int(dmax)
        config.save_settings(cfg)
        print_success(f"Delay set to {dmin}–{dmax} seconds.")
    else:
        print_error("Invalid numbers.")
    input("\n  Press ENTER...")


def set_paths():
    print_header("📁  Storage Paths")
    import config as cfg_mod
    console.print(f"  Sessions : [cyan]{cfg_mod.SESSIONS_DIR}[/cyan]")
    console.print(f"  Data     : [cyan]{cfg_mod.DATA_DIR}[/cyan]")
    console.print(f"  Exports  : [cyan]exports/[/cyan]")
    console.print(f"  Logs     : [cyan]logs/[/cyan]")
    console.print("\n  [dim]Paths are defined in config.py[/dim]")
    input("\n  Press ENTER...")


def toggle_setting(key: str, label: str):
    cfg = config.load_settings()
    cfg[key] = not cfg.get(key, False)
    config.save_settings(cfg)
    status = "[green]ON[/green]" if cfg[key] else "[red]OFF[/red]"
    console.print(f"\n  {label}: {status}")
    input("\n  Press ENTER...")


def set_night_mode():
    print_header("🌙  Night Mode")
    console.print("  When enabled, all operations stop from 12:00 AM to 7:00 AM.\n")
    cfg = config.load_settings()
    cfg["night_mode"] = confirm("  Enable Night Mode?", default=cfg.get("night_mode",False))
    config.save_settings(cfg)
    print_success("Night mode " + ("enabled." if cfg["night_mode"] else "disabled."))
    input("\n  Press ENTER...")


def set_bot_alerts():
    print_header("🤖  Telegram Bot Alerts")
    console.print("  Create a bot via @BotFather, get chat ID from @userinfobot\n")
    cfg   = config.load_settings()
    token = prompt("  Bot Token (ENTER keep)", cfg.get("notif_bot_token",""))
    cid   = prompt("  Chat ID   (ENTER keep)", cfg.get("notif_chat_id",""))
    cfg["notif_bot_token"] = token or cfg.get("notif_bot_token","")
    cfg["notif_chat_id"]   = cid   or cfg.get("notif_chat_id","")
    config.save_settings(cfg)
    print_success("Bot alerts configured.")
    input("\n  Press ENTER...")


def set_tool_password():
    print_header("🔐  Tool Password")
    cfg = config.load_settings()
    if cfg.get("tool_password"):
        console.print("  [yellow]A password is currently set.[/yellow]")
        if not confirm("  Change / remove the password?"):
            input("\n  Press ENTER...")
            return
    pw  = prompt("  New password (ENTER to disable)", password=True)
    pw2 = prompt("  Confirm password", password=True) if pw else ""
    if pw and pw == pw2:
        import hashlib
        cfg["tool_password"] = hashlib.sha256(pw.encode()).hexdigest()
        print_success("Password set.")
    elif pw:
        print_error("Passwords do not match. No changes made.")
    else:
        cfg.pop("tool_password", None)
        print_success("Password disabled.")
    config.save_settings(cfg)
    input("\n  Press ENTER...")


def set_auto_backup():
    print_header("📦  Auto-Backup Schedule")
    cfg      = config.load_settings()
    freq_map = {"1":"daily","2":"weekly","3":"monthly","4":"disabled"}
    cur      = cfg.get("auto_backup_freq","disabled")
    console.print(f"  Current: [cyan]{cur}[/cyan]\n")
    console.print("  [1] Daily  [2] Weekly  [3] Monthly  [4] Disabled")
    ch = prompt("  Select","1")
    cfg["auto_backup_freq"] = freq_map.get(ch, "daily")
    config.save_settings(cfg)
    print_success(f"Auto-backup set to: {cfg['auto_backup_freq']}.")
    input("\n  Press ENTER...")


def set_log_cleanup():
    print_header("🧹  Auto Log Cleanup")
    cfg     = config.load_settings()
    cur     = cfg.get("log_cleanup","weekly")
    freq_map = {"1":"daily","2":"weekly","3":"monthly","4":"disabled"}
    console.print(f"  Current: [cyan]{cur}[/cyan]\n")
    console.print("  [1] Daily  [2] Weekly  [3] Monthly  [4] Disabled")
    ch = prompt("  Select","2")
    cfg["log_cleanup"] = freq_map.get(ch, "weekly")
    config.save_settings(cfg)
    print_success(f"Log cleanup set to: {cfg['log_cleanup']}.")
    input("\n  Press ENTER...")


def reset_defaults():
    print_header("🔄  Reset to Defaults")
    print_warn("This will reset ALL settings to defaults (keeps API keys).")
    if not confirm("  Are you sure?"):
        return
    cfg = config.load_settings()
    api_id   = cfg.get("api_id")
    api_hash = cfg.get("api_hash")
    defaults = config.DEFAULT_SETTINGS.copy()
    if api_id:   defaults["api_id"]   = api_id
    if api_hash: defaults["api_hash"] = api_hash
    config.save_settings(defaults)
    print_success("Settings reset to defaults.")
    input("\n  Press ENTER...")
