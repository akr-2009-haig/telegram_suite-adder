from modules.utils import (
    console, print_header, print_success, print_info, prompt, menu_choice,
)
from modules.database import get_today_stats, get_week_stats, load_accounts
from datetime import datetime
from pathlib import Path


def reports_menu():
    while True:
        print_header("📊  Reports & Logs", "Statistics and Activity History")

        choice = menu_choice([
            ("1", "📊  Today's Report"),
            ("2", "📈  Weekly Report"),
            ("3", "📋  Scraping Log"),
            ("4", "📋  Adding Log"),
            ("5", "❌  Error Log"),
            ("6", "📤  Export Report (TXT / CSV)"),
            ("7", "📉  Account Performance Report"),
            ("8", "🔔  Notification Log"),
            ("9", "📊  Daily Performance Comparison"),
        ])

        if choice == "1":   today_report()
        elif choice == "2": weekly_report()
        elif choice == "3": show_log("scrape")
        elif choice == "4": show_log("add")
        elif choice == "5": show_log("error")
        elif choice == "6": export_report()
        elif choice == "7": account_performance()
        elif choice == "8": notification_log()
        elif choice == "9": daily_comparison()
        elif choice == "0": break


def today_report():
    print_header("📊  Today's Report")
    today  = datetime.now().strftime("%Y-%m-%d")
    stats  = get_today_stats()
    scrape = stats.get("scrape",  {})
    add    = stats.get("add",     {})
    msg    = stats.get("messages",{})
    errors = stats.get("errors",  {})

    console.print(f"  📅  Date: [bold]{today}[/bold]\n")

    console.print("  ─── 📥 Scraping ─────────────────────")
    console.print(f"  Total Scraped  : [cyan]{scrape.get('total',0):,}[/cyan]")
    console.print(f"  After Filters  : [cyan]{scrape.get('filtered',0):,}[/cyan]")
    console.print(f"  Sessions Run   : [white]{scrape.get('sessions',0)}[/white]")
    console.print(f"  Best Source    : [dim]{scrape.get('best_source','—')}[/dim]")
    console.print()

    console.print("  ─── 📤 Adding ───────────────────────")
    total_added  = add.get("success",0)
    total_failed = add.get("failed",0)
    total_skip   = add.get("skipped",0)
    total_all    = total_added + total_failed + total_skip
    pct          = f"{total_added/total_all*100:.1f}%" if total_all else "0%"
    console.print(f"  Total Added    : [green]{total_added:,}[/green]  ({pct} success)")
    console.print(f"  Failed         : [red]{total_failed}[/red]")
    console.print(f"  Skipped        : [yellow]{total_skip}[/yellow]")
    console.print(f"  Flood Waits    : [yellow]{add.get('flood_waits',0)}[/yellow]")
    console.print()

    console.print("  ─── 💬 Messages ─────────────────────")
    console.print(f"  Sent           : [cyan]{msg.get('sent',0)}[/cyan]")
    console.print(f"  Failed         : [red]{msg.get('failed',0)}[/red]")
    console.print()

    console.print("  ─── 🛡️ Protection ──────────────────")
    console.print(f"  Banned today   : [red]{errors.get('banned',0)}[/red]")
    console.print(f"  Restricted     : [yellow]{errors.get('restricted',0)}[/yellow]")
    console.print(f"  Auto-switches  : [dim]{errors.get('switches',0)}[/dim]")

    input("\n  Press ENTER...")


def weekly_report():
    print_header("📈  Weekly Report")
    week_stats = get_week_stats()
    total_scraped = 0
    total_added   = 0
    total_msgs    = 0
    console.print("  Day          Scraped    Added    Messages")
    console.print("  " + "─" * 48)
    for day in sorted(week_stats.keys(), reverse=True):
        ds = week_stats[day]
        sc = ds.get("scrape",{}).get("total",0)
        ad = ds.get("add",{}).get("success",0)
        ms = ds.get("messages",{}).get("sent",0)
        total_scraped += sc
        total_added   += ad
        total_msgs    += ms
        console.print(f"  [dim]{day}[/dim]  {sc:>8,}  {ad:>7,}  {ms:>8,}")
    console.print("  " + "─" * 48)
    console.print(f"  [bold]TOTAL[/bold]        {total_scraped:>8,}  {total_added:>7,}  {total_msgs:>8,}")
    input("\n  Press ENTER...")


def show_log(log_type: str):
    titles = {"scrape":"📋 Scraping Log","add":"📋 Adding Log","error":"❌ Error Log"}
    print_header(titles.get(log_type, "📋 Log"))
    log_file = Path("logs") / f"{log_type}.log"
    if not log_file.exists():
        print_info("No log file found.")
        input("\n  Press ENTER...")
        return
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    recent = lines[-50:]
    for line in recent:
        if "ERROR" in line or "BANNED" in line:
            console.print(f"  [red]{line}[/red]")
        elif "WARN" in line or "FLOOD" in line:
            console.print(f"  [yellow]{line}[/yellow]")
        elif "SUCCESS" in line or "OK" in line:
            console.print(f"  [green]{line}[/green]")
        else:
            console.print(f"  [dim]{line}[/dim]")
    console.print(f"\n  [dim]Showing last {len(recent)} of {len(lines)} lines — {log_file}[/dim]")
    input("\n  Press ENTER...")


def export_report():
    print_header("📤  Export Report")
    console.print("  Format:")
    console.print("  [1] TXT  [2] CSV")
    fmt_map  = {"1":"txt","2":"csv"}
    fmt      = fmt_map.get(prompt("  Select","1"),"txt")
    today    = datetime.now().strftime("%Y%m%d")
    out_dir  = Path("exports")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"report_{today}.{fmt}"
    stats    = get_today_stats()
    if fmt == "txt":
        lines = [
            f"Telegram Suite — Report — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "By: Akram Haig | +967772009303", "",
            f"Scraped : {stats.get('scrape',{}).get('total',0)}",
            f"Added   : {stats.get('add',{}).get('success',0)}",
            f"Messages: {stats.get('messages',{}).get('sent',0)}",
            f"Banned  : {stats.get('errors',{}).get('banned',0)}",
        ]
        out_path.write_text("\n".join(lines), encoding="utf-8")
    else:
        import csv
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Category","Metric","Value"])
            sc = stats.get("scrape",{})
            ad = stats.get("add",{})
            for k,v in sc.items():
                w.writerow(["Scrape", k, v])
            for k,v in ad.items():
                w.writerow(["Add", k, v])
    print_success(f"Exported: {out_path}")
    input("\n  Press ENTER...")


def account_performance():
    print_header("📉  Account Performance Report")
    accounts = load_accounts()
    if not accounts:
        print_info("No accounts found.")
        input("\n  Press ENTER...")
        return
    console.print("  Phone              Status      Added   Scraped  Messages  Age")
    console.print("  " + "─" * 72)
    for a in accounts:
        phone   = a.get("phone","?")[-12:]
        st      = a.get("status","?")
        col     = "green" if st=="active" else ("red" if st=="banned" else "yellow")
        added   = a.get("total_added",0)
        scraped = a.get("total_scraped",0)
        msgs    = a.get("total_messages",0)
        added_d = str(a.get("added_date",""))[:10]
        try:
            from datetime import date
            age_days = (date.today() - datetime.strptime(added_d, "%Y-%m-%d").date()).days
            age = f"{age_days}d"
        except Exception:
            age = "—"
        console.print(
            f"  [white]{phone:<18}[/white] [{col}]{st:<10}[/{col}] "
            f"{added:>7} {scraped:>8} {msgs:>9}  [dim]{age}[/dim]"
        )
    input("\n  Press ENTER...")


def notification_log():
    print_header("🔔  Notification Log")
    from modules.database import load_notif_log
    log = list(reversed(load_notif_log()))[:40]
    if not log:
        print_info("No notifications logged.")
        input("\n  Press ENTER...")
        return
    level_color = {"info":"cyan","warn":"yellow","error":"red","success":"green"}
    for n in log:
        col = level_color.get(n.get("level","info"),"white")
        dot = "" if n.get("read") else " ●"
        console.print(
            f"  [dim]{str(n.get('time',''))[:16]}[/dim]{dot}  "
            f"[{col}]{n.get('type',''):12}[/{col}]  "
            f"[white]{n.get('message','')}[/white]"
        )
    input("\n  Press ENTER...")


def daily_comparison():
    print_header("📊  Daily Performance Comparison")
    week_stats = get_week_stats()
    days = sorted(week_stats.keys(), reverse=True)
    if len(days) < 2:
        print_info("Need at least 2 days of data.")
        input("\n  Press ENTER...")
        return
    today_s = week_stats[days[0]] if days else {}
    yest_s  = week_stats[days[1]] if len(days) > 1 else {}

    def _get(stats, cat, key):
        return stats.get(cat,{}).get(key,0)

    def _diff(a, b):
        if b == 0: return "[dim]—[/dim]"
        pct = (a - b) / b * 100
        if pct > 0: return f"[green]+{pct:.0f}%[/green]"
        return f"[red]{pct:.0f}%[/red]"

    console.print(f"  {'Metric':<20}  {'Today':>10}  {'Yesterday':>10}  {'Change':>10}")
    console.print("  " + "─" * 56)
    metrics = [
        ("Scraped",  "scrape",  "total"),
        ("Added",    "add",     "success"),
        ("Failed",   "add",     "failed"),
        ("Messages", "messages","sent"),
        ("Banned",   "errors",  "banned"),
    ]
    for label, cat, key in metrics:
        t = _get(today_s, cat, key)
        y = _get(yest_s,  cat, key)
        console.print(f"  {label:<20}  {t:>10,}  {y:>10,}  {_diff(t,y):>10}")

    input("\n  Press ENTER...")
