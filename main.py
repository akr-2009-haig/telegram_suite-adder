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

import config
from modules.utils import (
    console, print_banner, print_header, print_success, print_error,
    print_info, print_warn, prompt, menu_choice, confirm, now_str,
)
from modules.database import load_accounts, load_proxies, get_today_stats


# ─── First-Run Setup ─────────────────────────────────────────────────────────

def first_run_setup():
    api_id, api_hash = config.get_api_credentials()
    if api_id and api_hash:
        return

    print_banner()
    console.print()
    console.print("  [bold yellow]⚙️  First-Time Setup Required[/bold yellow]")
    console.print()
    console.print("  ┌────────────────────────────────────────────────────────┐")
    console.print("  │  You need a Telegram API ID and Hash to continue.      │")
    console.print("  │                                                        │")
    console.print("  │  Get them FREE at: https://my.telegram.org/apps        │")
    console.print("  │                                                        │")
    console.print("  │  Steps:                                                │")
    console.print("  │  1. Log in with your Telegram account                  │")
    console.print("  │  2. Click 'Create Application'                         │")
    console.print("  │  3. Copy your API ID and API Hash                      │")
    console.print("  └────────────────────────────────────────────────────────┘")
    console.print()

    api_id   = prompt("  🔑 Enter API ID")
    api_hash = prompt("  🔑 Enter API Hash")

    if not api_id or not api_hash:
        print_error("API credentials are required. Exiting.")
        sys.exit(1)

    config.save_api_credentials(api_id.strip(), api_hash.strip())
    print_success("Credentials saved to .env — you won't be asked again.")
    console.print()
    input("  Press ENTER to continue...")


# ─── Status Bar ──────────────────────────────────────────────────────────────

def print_status_bar():
    accounts = load_accounts()
    proxies  = load_proxies()
    stats    = get_today_stats()

    total   = len(accounts)
    active  = sum(1 for a in accounts if a.get("status") == "active")
    banned  = sum(1 for a in accounts if a.get("status") in ("banned", "restricted"))
    prx_active = sum(1 for p in proxies if p.get("status") == "alive")

    imp_today = stats.get("import",     {}).get("successful", 0)
    col_today = stats.get("collection", {}).get("total_collected", 0)
    msg_today = stats.get("message",    {}).get("sent", 0)

    console.print()
    console.print("  ┌──────────────────────────────────────────────────────────┐")
    console.print(f"  │  Connected Accounts : [bold green]{active}[/bold green] / {total}   "
                  f"  Banned: [bold red]{banned}[/bold red]   "
                  f"  Proxies: [bold cyan]{prx_active}[/bold cyan]        │")
    console.print(f"  │  Today — Collected: [cyan]{col_today}[/cyan]   "
                  f"Imported: [green]{imp_today}[/green]   "
                  f"Messages: [yellow]{msg_today}[/yellow]              │")
    console.print("  └──────────────────────────────────────────────────────────┘")
    console.print()


# ─── Main Menu ───────────────────────────────────────────────────────────────

def main_menu():
    while True:
        print_banner()
        print_status_bar()

        console.print("  ┌─── Main Menu ────────────────────────────────────────────┐")
        console.print("  │                                                          │")
        console.print("  │  [bold cyan][ 1][/bold cyan]  👤  Account Manager                                   │")
        console.print("  │  [bold cyan][ 2][/bold cyan]  📥  Member Scraper                                    │")
        console.print("  │  [bold cyan][ 3][/bold cyan]  📤  Member Adder                                      │")
        console.print("  │  [bold cyan][ 4][/bold cyan]  🔄  Rotation System                                   │")
        console.print("  │  [bold cyan][ 5][/bold cyan]  🌐  Proxy Manager                                     │")
        console.print("  │  [bold cyan][ 6][/bold cyan]  ⚙️   Settings                                          │")
        console.print("  │  [bold cyan][ 7][/bold cyan]  📊  Reports & Logs                                    │")
        console.print("  │  [bold cyan][ 8][/bold cyan]  🛡️   Security Tools                                    │")
        console.print("  │  [bold cyan][ 9][/bold cyan]  💬  Bulk Messaging                                    │")
        console.print("  │  [bold cyan][10][/bold cyan]  📢  Outreach Campaigns                                │")
        console.print("  │                                                          │")
        console.print("  │  [dim][ 0]  🚪  Exit[/dim]                                            │")
        console.print("  ├──────────────────────────────────────────────────────────┤")
        console.print("  │  [dim]By: Akram Haig  |  +967772009303[/dim]                        │")
        console.print("  └──────────────────────────────────────────────────────────┘")
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
        elif choice == "0":
            console.print("\n  [bold]Goodbye! 👋[/bold]\n")
            sys.exit(0)
        else:
            print_error("Invalid option. Enter a number from the menu.")


# ─── Entry Point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        first_run_setup()
        main_menu()
    except KeyboardInterrupt:
        console.print("\n\n  [dim]Interrupted by user. Goodbye![/dim]\n")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n  [bold red]Fatal error:[/bold red] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
