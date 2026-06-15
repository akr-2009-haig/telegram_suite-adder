import csv
import json
from datetime import datetime, timedelta
from pathlib import Path
from rich.table import Table
from rich import box

import config
from modules.utils import (
    console, print_header, print_success, print_error, print_info,
    prompt, menu_choice, now_str, date_str,
)
from modules.database import (
    get_today_stats, load_stats, load_accounts, load_proxies,
)


def reports_menu():
    while True:
        print_header("📊  Reports & Logs", "View statistics, reports, and activity logs")
        choice = menu_choice([
            ("1", "📊  Today's Report"),
            ("2", "📈  Weekly Report"),
            ("3", "📋  Collection Log"),
            ("4", "📋  Import Log"),
            ("5", "❌  Error Log"),
            ("6", "📤  Export Report (TXT / CSV)"),
        ])
        if choice == "1":
            todays_report()
        elif choice == "2":
            weekly_report()
        elif choice == "3":
            view_log("collection")
        elif choice == "4":
            view_log("import")
        elif choice == "5":
            view_log("error")
        elif choice == "6":
            export_report()
        elif choice == "0":
            break


# ─── Today's Report ──────────────────────────────────────────────────────────

def todays_report():
    print_header("📊  Today's Report", date_str())
    stats  = get_today_stats()
    accounts = load_accounts()

    col_stats = stats.get("collection", {})
    imp_stats = stats.get("import", {})
    prot_stats = stats.get("protection", {})

    console.print("  ─── 📥 Collection ───────────────────────")
    console.print(f"  Operations      : [cyan]{col_stats.get('operations', 0)}[/cyan]")
    console.print(f"  Total Extracted : [bold]{col_stats.get('total_collected', 0)}[/bold]")
    console.print(f"  After Filtering : [green]{col_stats.get('after_filter', 0)}[/green]")

    console.print("\n  ─── 📤 Imports ──────────────────────────")
    total_imp = imp_stats.get("successful", 0) + imp_stats.get("failed", 0) + imp_stats.get("skipped", 0)
    success   = imp_stats.get("successful", 0)
    failed    = imp_stats.get("failed", 0)
    skipped   = imp_stats.get("skipped", 0)
    pct       = f"{(success/total_imp*100):.1f}%" if total_imp else "0%"
    console.print(f"  Total Attempted : [bold]{total_imp}[/bold]")
    console.print(f"  Successful      : [green]{success}[/green]  ({pct})")
    console.print(f"  Failed          : [red]{failed}[/red]")
    console.print(f"  Skipped         : [yellow]{skipped}[/yellow]")

    console.print("\n  ─── 🛡️ Protection ───────────────────────")
    banned_accs = [a for a in accounts if a.get("status") == "banned"]
    restricted  = [a for a in accounts if a.get("status") == "restricted"]
    console.print(f"  FloodWait Warnings   : [yellow]{prot_stats.get('floodwait', 0)}[/yellow]")
    console.print(f"  Banned Accounts      : [red]{len(banned_accs)}[/red]")
    console.print(f"  Restricted Accounts  : [yellow]{len(restricted)}[/yellow]")
    console.print(f"  Auto Switches        : [cyan]{prot_stats.get('switches', 0)}[/cyan]")

    console.print("\n  ─── 👥 Account Summary ──────────────────")
    active = sum(1 for a in accounts if a.get("status") == "active")
    total  = len(accounts)
    used_today = sum(1 for a in accounts if a.get("today_imports", 0) > 0 or a.get("today_collections", 0) > 0)
    console.print(f"  Active / Total : [green]{active}[/green] / {total}")
    console.print(f"  Used Today     : [cyan]{used_today}[/cyan]")

    input("\n  Press ENTER...")


# ─── Weekly Report ───────────────────────────────────────────────────────────

def weekly_report():
    print_header("📈  Weekly Report")
    stats = load_stats()

    table = Table(box=box.SIMPLE_HEAVY, border_style="cyan")
    table.add_column("Date",       width=12, style="bold white")
    table.add_column("Collected",  width=12, justify="right", style="cyan")
    table.add_column("Imported",   width=12, justify="right", style="green")
    table.add_column("Messages",   width=12, justify="right", style="yellow")
    table.add_column("Errors",     width=10, justify="right", style="red")

    today = datetime.now()
    totals = {"collected": 0, "imported": 0, "messages": 0, "errors": 0}
    for i in range(6, -1, -1):
        day = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        day_stats = stats.get(day, {})
        c = day_stats.get("collection", {}).get("total_collected", 0)
        m = day_stats.get("import", {}).get("successful", 0)
        msg = day_stats.get("message", {}).get("sent", 0)
        e = day_stats.get("import", {}).get("failed", 0)
        totals["collected"] += c
        totals["imported"]  += m
        totals["messages"]  += msg
        totals["errors"]    += e

        label = "Today" if i == 0 else ("Yesterday" if i == 1 else day)
        table.add_row(label, str(c), str(m), str(msg), str(e))

    console.print(table)
    console.print(f"\n  7-Day Totals:")
    console.print(f"  Collected: [cyan]{totals['collected']}[/cyan]  Imported: [green]{totals['imported']}[/green]  Messages: [yellow]{totals['messages']}[/yellow]  Errors: [red]{totals['errors']}[/red]")

    input("\n  Press ENTER...")


# ─── View Logs ───────────────────────────────────────────────────────────────

def view_log(log_type: str):
    logs_dir = config.LOGS_DIR
    pattern  = f"{log_type}_*.log"
    files    = sorted(logs_dir.glob(pattern), reverse=True)

    title_map = {"collection": "📋  Collection Log", "import": "📋  Import Log", "error": "❌  Error Log"}
    print_header(title_map.get(log_type, "📋  Log"))

    if not files:
        print_info(f"No {log_type} logs found yet.")
        input("\n  Press ENTER...")
        return

    for i, f in enumerate(files[:10], 1):
        console.print(f"  [{i}] {f.name}")
    console.print()
    sel = prompt("  Select log #", "1")
    try:
        idx = int(sel) - 1
        if 0 <= idx < len(files):
            content = files[idx].read_text(encoding="utf-8")
            lines = content.strip().split("\n")
            display = lines[-50:] if len(lines) > 50 else lines
            console.print()
            for line in display:
                if "✅" in line or "OK" in line.upper():
                    console.print(f"  [green]{line}[/green]")
                elif "❌" in line or "ERROR" in line.upper() or "FAIL" in line.upper():
                    console.print(f"  [red]{line}[/red]")
                elif "⚠️" in line or "WARN" in line.upper():
                    console.print(f"  [yellow]{line}[/yellow]")
                else:
                    console.print(f"  [dim]{line}[/dim]")
            if len(lines) > 50:
                console.print(f"\n  [dim]... showing last 50 of {len(lines)} lines[/dim]")
    except (ValueError, IndexError):
        print_error("Invalid selection.")
    input("\n  Press ENTER...")


# ─── Export Report ───────────────────────────────────────────────────────────

def export_report():
    print_header("📤  Export Report")
    console.print("  [1] TXT   [2] CSV")
    fmt = prompt("  Format", "1")

    stats    = get_today_stats()
    accounts = load_accounts()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename  = f"report_{timestamp}.{'txt' if fmt != '2' else 'csv'}"
    out_path  = config.EXPORTS_DIR / filename

    col = stats.get("collection", {})
    imp = stats.get("import", {})

    if fmt == "2":
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Category", "Metric", "Value"])
            writer.writerow(["Collection", "Total Collected", col.get("total_collected", 0)])
            writer.writerow(["Import", "Successful", imp.get("successful", 0)])
            writer.writerow(["Import", "Failed", imp.get("failed", 0)])
            writer.writerow(["Import", "Skipped", imp.get("skipped", 0)])
            writer.writerow(["Accounts", "Active", sum(1 for a in accounts if a.get("status") == "active")])
            writer.writerow(["Accounts", "Total", len(accounts)])
    else:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"Telegram Automation Suite — Report\n")
            f.write(f"Generated: {now_str()}\n")
            f.write("=" * 40 + "\n\n")
            f.write(f"Collection\n")
            f.write(f"  Total Collected : {col.get('total_collected', 0)}\n\n")
            f.write(f"Imports\n")
            f.write(f"  Successful : {imp.get('successful', 0)}\n")
            f.write(f"  Failed     : {imp.get('failed', 0)}\n")
            f.write(f"  Skipped    : {imp.get('skipped', 0)}\n\n")
            active = sum(1 for a in accounts if a.get("status") == "active")
            f.write(f"Accounts\n")
            f.write(f"  Active : {active} / {len(accounts)}\n")

    print_success(f"Report saved: {out_path}")
    input("\n  Press ENTER...")
