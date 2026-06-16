#!/usr/bin/env python3
"""
Telegram Automation Suite v1.0
Termux Edition — CLI
By: Akram Haig | +967772009303
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# ─── نظام القفل الذكي — يجب أن يكون أول شيء يُنفَّذ ─────────────────────────
from modules.device_lock import check_device_lock

import config
from modules.utils import (
    console, print_banner, print_header, print_success, print_error,
    print_info, print_warn, prompt, menu_choice, confirm, now_str,
)
from modules.database import load_accounts, load_proxies, get_today_stats, get_unread_notifications


# ─── Night Mode Check ─────────────────────────────────────────────────────────

def is_night_mode_active() -> bool:
    cfg  = config.load_settings()
    if not cfg.get("night_mode"):
        return False
    from datetime import datetime
    h = datetime.now().hour
    return h >= 0 and h < 7


# ─── Status Bar ──────────────────────────────────────────────────────────────

def print_status_bar():
    accounts   = load_accounts()
    proxies    = load_proxies()
    stats      = get_today_stats()
    unread     = len(get_unread_notifications())

    total      = len(accounts)
    active     = sum(1 for a in accounts if a.get("status") == "active")
    banned     = sum(1 for a in accounts if a.get("status") in ("banned","restricted"))
    prx_active = sum(1 for p in proxies if p.get("status") == "alive")

    col_today  = stats.get("scrape",   {}).get("total", 0)
    add_today  = stats.get("add",      {}).get("success", 0)
    msg_today  = stats.get("messages", {}).get("sent", 0)

    night_warn = "  [bold yellow]🌙 Night Mode Active — Operations Paused[/bold yellow]\n" if is_night_mode_active() else ""
    emrg_warn  = "  [bold red]🚨 EMERGENCY MODE ACTIVE — Delete emergency.flag to resume[/bold red]\n" if Path("emergency.flag").exists() else ""
    notif_line = f"  [bold yellow]🔔 {unread} unread notification(s)[/bold yellow]\n" if unread else ""

    console.print()
    if night_warn: console.print(night_warn, end="")
    if emrg_warn:  console.print(emrg_warn,  end="")
    if notif_line: console.print(notif_line, end="")
    console.print("  ┌──────────────────────────────────────────────────────────────┐")
    console.print(f"  │  Accounts: [bold green]{active}[/bold green] active / [dim]{total}[/dim] total   "
                  f"Banned: [bold red]{banned}[/bold red]   "
                  f"Proxies: [bold cyan]{prx_active}[/bold cyan]       │")
    console.print(f"  │  Today — Scraped: [cyan]{col_today:,}[/cyan]   "
                  f"Added: [green]{add_today:,}[/green]   "
                  f"Messages: [yellow]{msg_today:,}[/yellow]            │")
    console.print("  └──────────────────────────────────────────────────────────────┘")
    console.print()


# ─── Main Menu ───────────────────────────────────────────────────────────────

def main_menu():
    while True:
        print_banner()
        print_status_bar()

        console.print("  ┌─── Main Menu ──────────────────────────────────────────────┐")
        console.print("  │                                                            │")
        console.print("  │  [bold cyan][ 1][/bold cyan]  👤  Account Manager                                     │")
        console.print("  │  [bold cyan][ 2][/bold cyan]  📥  Member Scraper                                      │")
        console.print("  │  [bold cyan][ 3][/bold cyan]  📤  Member Adder                                        │")
        console.print("  │  [bold cyan][ 4][/bold cyan]  🔄  Rotation System                                     │")
        console.print("  │  [bold cyan][ 5][/bold cyan]  🌐  Proxy Manager                                       │")
        console.print("  │  [bold cyan][ 6][/bold cyan]  ⚙️   Settings                                            │")
        console.print("  │  [bold cyan][ 7][/bold cyan]  📊  Reports & Logs                                      │")
        console.print("  │  [bold cyan][ 8][/bold cyan]  🛡️   Security Tools                                      │")
        console.print("  │  [bold cyan][ 9][/bold cyan]  💬  Bulk Messaging                                      │")
        console.print("  │  [bold cyan][10][/bold cyan]  📢  Outreach Campaigns                                  │")
        console.print("  │  [bold cyan][11][/bold cyan]  🤖  Auto-Reply System                                   │")
        console.print("  │  [bold cyan][12][/bold cyan]  📅  Task Scheduler                                      │")
        console.print("  │  [bold cyan][13][/bold cyan]  🔔  Notification Center                                 │")
        console.print("  │  [bold cyan][14][/bold cyan]  📦  Backup & Restore                                    │")
        console.print("  │                                                            │")
        console.print("  │  [dim][ 0]  🚪  Exit[/dim]                                              │")
        console.print("  ├────────────────────────────────────────────────────────────┤")
        console.print("  │  [dim]By: Akram Haig  |  +967772009303[/dim]                          │")
        console.print("  └────────────────────────────────────────────────────────────┘")
        console.print()

        choice = prompt("  ❯").strip()

        if choice == "1":
            from modules.account_manager import account_manager_menu
            account_manager_menu()
        elif choice == "2":
            from modules.member_scraper import member_scraper_menu
            member_scraper_menu()
        elif choice == "3":
            from modules.member_adder import member_adder_menu
            member_adder_menu()
        elif choice == "4":
            from modules.rotation import rotation_menu
            rotation_menu()
        elif choice == "5":
            from modules.proxy_manager import proxy_manager_menu
            proxy_manager_menu()
        elif choice == "6":
            from modules.settings_menu import settings_menu
            settings_menu()
        elif choice == "7":
            from modules.reports import reports_menu
            reports_menu()
        elif choice == "8":
            from modules.security import security_menu
            security_menu()
        elif choice == "9":
            from modules.bulk_messaging import bulk_messaging_menu
            bulk_messaging_menu()
        elif choice == "10":
            from modules.campaigns import campaigns_menu
            campaigns_menu()
        elif choice == "11":
            from modules.auto_reply import auto_reply_menu
            auto_reply_menu()
        elif choice == "12":
            from modules.scheduler import scheduler_menu
            scheduler_menu()
        elif choice == "13":
            from modules.notifications import notifications_menu
            notifications_menu()
        elif choice == "14":
            from modules.backup import backup_menu
            backup_menu()
        elif choice == "0":
            console.print("\n  [bold]Goodbye! 👋[/bold]\n")
            sys.exit(0)
        else:
            print_error("Invalid option — enter a number from the menu.")


# ─── Entry Point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        check_device_lock()
        main_menu()
    except KeyboardInterrupt:
        console.print("\n\n  [dim]Interrupted. Goodbye![/dim]\n")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n  [bold red]Fatal error:[/bold red] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
