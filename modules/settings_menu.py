from pathlib import Path
from rich.table import Table
from rich import box

import config
from modules.utils import (
    console, print_header, print_success, print_error, print_info,
    prompt, menu_choice, confirm,
)


def settings_menu():
    while True:
        print_header("⚙️  Settings", "Configure global system settings")
        cfg = config.load_settings()
        api_id, api_hash = config.get_api_credentials()

        console.print("  ─── API Credentials ─────────────────────")
        console.print(f"  API ID   : [bold]{'*' * 6 + str(api_id)[-3:] if api_id else '[red]Not Set[/red]'}[/bold]")
        console.print(f"  API Hash : [bold]{'*' * 10 + str(api_hash)[-4:] if api_hash else '[red]Not Set[/red]'}[/bold]")
        console.print()
        console.print("  ─── Default Limits ──────────────────────")
        console.print(f"  [3]  Daily Import Limit   : [cyan]{cfg['daily_import_limit']}[/cyan]")
        console.print(f"  [4]  Daily Collection Limit: [cyan]{cfg['daily_collection_limit']}[/cyan]")
        console.print(f"  [5]  Daily Message Limit   : [cyan]{cfg['daily_message_limit']}[/cyan]")
        console.print(f"  [6]  Default Delay         : [cyan]{cfg['delay_min']}–{cfg['delay_max']}s[/cyan]")
        console.print()
        console.print("  ─── Storage Paths ───────────────────────")
        console.print(f"  [7]  Sessions Dir : [dim]{cfg['sessions_dir']}[/dim]")
        console.print(f"  [8]  Exports Dir  : [dim]{cfg['exports_dir']}[/dim]")
        console.print(f"  [9]  Logs Dir     : [dim]{cfg['logs_dir']}[/dim]")
        console.print()
        console.print("  ─── Other ───────────────────────────────")
        console.print(f"  [10] Notifications      : [{'green' if cfg['notifications'] else 'red'}]{'Enabled' if cfg['notifications'] else 'Disabled'}[/{'green' if cfg['notifications'] else 'red'}]")
        console.print(f"  [11] Detailed Logging   : [{'green' if cfg['detailed_logging'] else 'red'}]{'Enabled' if cfg['detailed_logging'] else 'Disabled'}[/{'green' if cfg['detailed_logging'] else 'red'}]")
        console.print(f"  [12] Security Level     : [cyan]{cfg.get('security_level','balanced').title()}[/cyan]")
        console.print()

        choice = menu_choice([
            ("1",  "🔑  Update API ID"),
            ("2",  "🔑  Update API Hash"),
            ("3",  "📤  Daily Import Limit"),
            ("4",  "📥  Daily Collection Limit"),
            ("5",  "💬  Daily Message Limit"),
            ("6",  "⏱️  Default Delay Range"),
            ("10", "🔔  Toggle Notifications"),
            ("11", "📊  Toggle Detailed Logging"),
            ("12", "🛡️  Security Level"),
            ("13", "🔄  Reset to Defaults"),
        ], back=True)

        if choice == "1":
            new_id = prompt("  Enter new API ID")
            if new_id:
                api_hash_current = api_hash or ""
                config.save_api_credentials(new_id, api_hash_current)
                print_success("API ID updated.")

        elif choice == "2":
            new_hash = prompt("  Enter new API Hash")
            if new_hash:
                api_id_current = api_id or ""
                config.save_api_credentials(api_id_current, new_hash)
                print_success("API Hash updated.")

        elif choice == "3":
            val = prompt(f"  Daily Import Limit (current: {cfg['daily_import_limit']})")
            if val.isdigit():
                cfg["daily_import_limit"] = int(val)
                config.save_settings(cfg)
                print_success("Updated.")

        elif choice == "4":
            val = prompt(f"  Daily Collection Limit (current: {cfg['daily_collection_limit']})")
            if val.isdigit():
                cfg["daily_collection_limit"] = int(val)
                config.save_settings(cfg)
                print_success("Updated.")

        elif choice == "5":
            val = prompt(f"  Daily Message Limit (current: {cfg['daily_message_limit']})")
            if val.isdigit():
                cfg["daily_message_limit"] = int(val)
                config.save_settings(cfg)
                print_success("Updated.")

        elif choice == "6":
            dmin = prompt(f"  Min delay seconds (current: {cfg['delay_min']})")
            dmax = prompt(f"  Max delay seconds (current: {cfg['delay_max']})")
            if dmin.isdigit(): cfg["delay_min"] = int(dmin)
            if dmax.isdigit(): cfg["delay_max"] = int(dmax)
            config.save_settings(cfg)
            print_success("Delay range updated.")

        elif choice == "10":
            cfg["notifications"] = not cfg["notifications"]
            config.save_settings(cfg)
            state = "enabled" if cfg["notifications"] else "disabled"
            print_success(f"Notifications {state}.")

        elif choice == "11":
            cfg["detailed_logging"] = not cfg["detailed_logging"]
            config.save_settings(cfg)
            state = "enabled" if cfg["detailed_logging"] else "disabled"
            print_success(f"Detailed logging {state}.")

        elif choice == "12":
            console.print("  [1] Conservative  [2] Balanced  [3] Aggressive")
            sl = prompt("  Select", "2")
            cfg["security_level"] = {"1": "conservative", "2": "balanced", "3": "aggressive"}.get(sl, "balanced")
            config.save_settings(cfg)
            print_success("Security level updated.")

        elif choice == "13":
            if confirm("  Reset ALL settings to defaults?"):
                config.save_settings(config.default_settings())
                print_success("Settings reset to defaults.")

        elif choice == "0":
            break

        input("\n  Press ENTER...")
