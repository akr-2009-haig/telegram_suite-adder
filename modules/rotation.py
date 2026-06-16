from modules.utils import (
    console, print_header, print_success, print_error, print_info, print_warn,
    prompt, menu_choice, confirm, now_str,
)
from modules.database import load_accounts, save_accounts, get_active_accounts, increment_stat
import config


def rotation_menu():
    while True:
        accounts = get_active_accounts()
        print_header("🔄  Rotation System", f"Active accounts: {len(accounts)}")

        choice = menu_choice([
            ("1", "⚙️  Rotation Settings"),
            ("2", "📋  View Current Rotation Schedule"),
            ("3", "✏️  Edit Account Order / Priority"),
            ("4", "📊  Account Usage & Daily Limits"),
            ("5", "🔄  Reset Daily Counters"),
            ("6", "📈  Rotation Performance Stats"),
            ("7", "🧪  Test Rotation (Dry Run)"),
            ("8", "🕐  Time-Based Rotation Schedule"),
        ])

        if choice == "1":   rotation_settings()
        elif choice == "2": view_rotation_schedule()
        elif choice == "3": edit_account_order()
        elif choice == "4": account_usage_panel()
        elif choice == "5": reset_daily_counters_menu()
        elif choice == "6": rotation_performance_stats()
        elif choice == "7": dry_run_test()
        elif choice == "8": time_schedule_settings()
        elif choice == "0": break


# ─── 1. Rotation Settings ─────────────────────────────────────────────────────

def rotation_settings():
    print_header("⚙️  Rotation Settings")
    cfg = config.load_settings()

    console.print("  ─── Switch Mode ────────────────────────────────────")
    console.print("  [1] Sequential   — 1 → 2 → 3 → 4 → ... → 1")
    console.print("  [2] Random       — random order each time")
    console.print("  [3] Load-Based   — least-used account first")
    console.print("  [4] Smart ⭐     — age + activity + status aware")
    console.print("  [5] By Category  — each task uses its tagged accounts")
    mode_map = {"1":"sequential","2":"random","3":"load","4":"smart","5":"category"}
    cur_mode = cfg.get("rotation_mode","smart")
    cur_idx  = {v:k for k,v in mode_map.items()}.get(cur_mode,"4")
    console.print(f"\n  Current: [cyan]{cur_mode}[/cyan]")
    choice = prompt("  Select mode", cur_idx)
    cfg["rotation_mode"] = mode_map.get(choice, cur_mode)

    console.print("\n  ─── Switch Trigger ─────────────────────────────────")
    console.print("  [1] After N operations     [2] After N minutes")
    console.print("  [3] On first error/warning [4] Mixed (ops + time)")
    console.print("  [5] Auto — based on account health")
    trigger_map = {"1":"ops","2":"time","3":"error","4":"mixed","5":"auto"}
    cur_trig = cfg.get("switch_trigger","ops")
    t_idx    = {v:k for k,v in trigger_map.items()}.get(cur_trig,"1")
    tc = prompt("  Select trigger", t_idx)
    cfg["switch_trigger"] = trigger_map.get(tc, cur_trig)

    if cfg["switch_trigger"] in ("ops","mixed"):
        n = prompt("  Switch after how many ops?", str(cfg.get("switch_after_ops",5)))
        if n.isdigit():
            cfg["switch_after_ops"] = int(n)
    if cfg["switch_trigger"] in ("time","mixed"):
        m = prompt("  Switch after how many minutes?", str(cfg.get("switch_after_minutes",10)))
        if m.isdigit():
            cfg["switch_after_minutes"] = int(m)

    console.print("\n  ─── When Account Gets Restricted ────────────────────")
    console.print("  [1] Switch immediately + remove from rotation")
    console.print("  [2] Switch + retry after 1 hour")
    console.print("  [3] Stop all + send alert")
    console.print("  [4] Switch + quarantine account")
    ban_map = {"1":"remove","2":"retry","3":"stop","4":"quarantine"}
    bc = prompt("  Select", "2")
    cfg["on_restriction"] = ban_map.get(bc,"retry")

    console.print("\n  ─── When All Accounts Hit Limits ────────────────────")
    console.print("  [1] Stop + resume tomorrow automatically")
    console.print("  [2] Stop + notify only")
    console.print("  [3] Wait until one frees up")
    console.print("  [4] Stop + send detailed report")
    limit_map = {"1":"auto_resume","2":"notify","3":"wait","4":"report"}
    lc = prompt("  Select","1")
    cfg["on_all_limited"] = limit_map.get(lc,"auto_resume")

    config.save_settings(cfg)
    print_success("Rotation settings saved.")
    input("\n  Press ENTER...")


# ─── 2. View Schedule ─────────────────────────────────────────────────────────

def view_rotation_schedule():
    print_header("📋  Current Rotation Schedule")
    accounts = get_active_accounts()
    if not accounts:
        print_info("No active accounts.")
        input("\n  Press ENTER...")
        return

    cfg   = config.load_settings()
    mode  = cfg.get("rotation_mode","smart")
    trig  = cfg.get("switch_trigger","ops")
    after = cfg.get("switch_after_ops",5)

    console.print(f"  Mode    : [bold cyan]{mode}[/bold cyan]")
    console.print(f"  Trigger : [bold]{trig}[/bold] (every {after} ops)")
    console.print()

    console.print(f"  {'#':<4} {'Phone':<18} {'Status':<14} {'Tag':<15} {'Priority'}")
    console.print("  " + "─" * 64)
    for i, acc in enumerate(accounts, 1):
        st    = acc.get("status","?")
        col   = "green" if st=="active" else "red"
        tag   = acc.get("tag","—")
        prio  = acc.get("priority",0)
        console.print(
            f"  {i:<4} {acc['phone']:<18} [{col}]{st:<14}[/{col}] {tag:<15} {prio}"
        )
    input("\n  Press ENTER...")


# ─── 3. Edit Order ────────────────────────────────────────────────────────────

def edit_account_order():
    print_header("✏️  Edit Account Priority")
    accounts = load_accounts()
    if not accounts:
        print_info("No accounts.")
        input("\n  Press ENTER...")
        return

    for i, a in enumerate(accounts, 1):
        console.print(f"  [{i}] {a['phone']}  priority={a.get('priority',0)}  tag={a.get('tag','—')}")

    console.print("\n  Edit:")
    console.print("  [1] Set priority for an account")
    console.print("  [2] Set tag/category for an account")
    console.print("  [3] Add note to account")
    sub = prompt("  Select", "1")

    phone = prompt("  Account phone number")
    if not phone:
        input("\n  Press ENTER...")
        return

    if sub == "1":
        prio = prompt("  New priority (higher = runs earlier)", "0")
        if prio.lstrip("-").isdigit():
            from modules.database import update_account
            update_account(phone, {"priority": int(prio)})
            print_success(f"Priority set to {prio} for {phone}.")
    elif sub == "2":
        console.print("  Tags: [1] scrape  [2] add  [3] messaging  [4] multi")
        tag_map = {"1":"scrape","2":"add","3":"messaging","4":"multi"}
        tag = tag_map.get(prompt("  Select","4"),"multi")
        from modules.database import update_account
        update_account(phone, {"tag": tag})
        print_success(f"Tag '{tag}' set for {phone}.")
    elif sub == "3":
        note = prompt("  Note")
        from modules.database import update_account
        update_account(phone, {"note": note})
        print_success(f"Note saved for {phone}.")

    input("\n  Press ENTER...")


# ─── 4. Usage Panel ───────────────────────────────────────────────────────────

def account_usage_panel():
    print_header("📊  Account Usage & Daily Limits")
    accounts = load_accounts()
    if not accounts:
        print_info("No accounts.")
        input("\n  Press ENTER...")
        return

    cfg       = config.load_settings()
    add_lim   = cfg.get("add_limit",    20)
    scrp_lim  = cfg.get("scrape_limit", 500)
    msg_lim   = cfg.get("msg_limit",    30)

    console.print(f"  {'Phone':<18} {'Status':<12} {'Added':>8} {'Scraped':>8} {'Msgs':>6} {'Next Reset'}")
    console.print("  " + "─" * 72)

    from datetime import datetime
    now_h   = datetime.now().hour
    now_m   = datetime.now().minute
    hrs_left = 23 - now_h
    mins_left= 60 - now_m

    for a in accounts:
        phone = a.get("phone","?")
        st    = a.get("status","?")
        col   = "green" if st=="active" else ("red" if st=="banned" else "yellow")
        added  = a.get("today_imports",    0)
        scraped= a.get("today_collections",0)
        msgs   = a.get("today_messages",   0)

        add_bar  = f"{added}/{add_lim}"
        scrp_bar = f"{scraped}/{scrp_lim}"
        msg_bar  = f"{msgs}/{msg_lim}"

        add_col  = "red" if added  >= add_lim  else "green"
        scrp_col = "red" if scraped>= scrp_lim else "green"
        msg_col  = "red" if msgs   >= msg_lim  else "green"

        console.print(
            f"  {phone:<18} [{col}]{st:<12}[/{col}] "
            f"[{add_col}]{add_bar:>8}[/{add_col}] "
            f"[{scrp_col}]{scrp_bar:>8}[/{scrp_col}] "
            f"[{msg_col}]{msg_bar:>6}[/{msg_col}]  "
            f"[dim]{hrs_left:02d}:{mins_left:02d}[/dim]"
        )

    console.print(f"\n  Limits per account: Add [bold]{add_lim}[/bold] | Scrape [bold]{scrp_lim}[/bold] | Msg [bold]{msg_lim}[/bold]")
    console.print(f"  Counters reset at  : [bold]12:00 AM[/bold]")
    input("\n  Press ENTER...")


# ─── 5. Reset Counters ────────────────────────────────────────────────────────

def reset_daily_counters_menu():
    print_header("🔄  Reset Daily Counters")
    if confirm("  Reset all daily counters for all accounts?"):
        from modules.database import reset_daily_counters
        reset_daily_counters()
        print_success("Daily counters reset.")
    input("\n  Press ENTER...")


# ─── 6. Performance Stats ─────────────────────────────────────────────────────

def rotation_performance_stats():
    print_header("📈  Rotation Performance Stats")
    accounts = load_accounts()
    if not accounts:
        print_info("No accounts.")
        input("\n  Press ENTER...")
        return

    from modules.database import get_week_stats
    week  = get_week_stats()
    total_adds = sum(
        d.get("add",{}).get("success",0) for d in week.values()
    )
    total_scrape = sum(
        d.get("scrape",{}).get("total",0) for d in week.values()
    )

    active  = sum(1 for a in accounts if a.get("status")=="active")
    banned  = sum(1 for a in accounts if a.get("status")=="banned")
    cfg     = config.load_settings()
    mode    = cfg.get("rotation_mode","smart")
    trigger = cfg.get("switch_trigger","ops")
    after   = cfg.get("switch_after_ops",5)

    console.print(f"  Rotation Mode   : [bold cyan]{mode}[/bold cyan]")
    console.print(f"  Switch Trigger  : [bold]{trigger}[/bold] every {after} ops")
    console.print(f"  Active Accounts : [green]{active}[/green]")
    console.print(f"  Banned Accounts : [red]{banned}[/red]")
    console.print()
    console.print(f"  ─── This Week ─────────────────────────────────────")
    console.print(f"  Total Added   : [bold green]{total_adds:,}[/bold green]")
    console.print(f"  Total Scraped : [bold cyan]{total_scrape:,}[/bold cyan]")
    if active:
        console.print(f"  Avg per acct  : [bold]{total_adds//active:,}[/bold] adds  /  [bold]{total_scrape//active:,}[/bold] scraped")

    input("\n  Press ENTER...")


# ─── 7. Dry Run ───────────────────────────────────────────────────────────────

def dry_run_test():
    print_header("🧪  Rotation Dry Run (Test)")
    console.print("  Simulates which account would be used for each operation.\n")
    accounts = get_active_accounts()
    if not accounts:
        print_info("No active accounts.")
        input("\n  Press ENTER...")
        return

    cfg      = config.load_settings()
    mode     = cfg.get("rotation_mode","smart")
    after    = cfg.get("switch_after_ops",5)
    n_ops    = int(prompt("  Simulate how many operations?","20") or 20)

    import random
    console.print(f"\n  Mode: [cyan]{mode}[/cyan]  |  Switch every [bold]{after}[/bold] ops\n")
    console.print(f"  {'Op #':<6} {'Account':<18} {'Action'}")
    console.print("  " + "─" * 45)

    acc_idx = 0
    for i in range(1, n_ops+1):
        if mode == "random":
            acc = random.choice(accounts)
        else:
            acc = accounts[(acc_idx) % len(accounts)]
        if i % after == 0:
            acc_idx += 1

        op = random.choice(["Add member","Send message","Scrape"])
        console.print(f"  {i:<6} {acc['phone']:<18} {op}")

    console.print(f"\n  [dim]Dry run complete — no actual operations performed.[/dim]")
    input("\n  Press ENTER...")


# ─── 8. Time Schedule ─────────────────────────────────────────────────────────

def time_schedule_settings():
    print_header("🕐  Time-Based Rotation Schedule")
    cfg = config.load_settings()

    console.print("  Define active hours for operations.\n")
    start_h = prompt("  Start hour (24h, 0–23)", str(cfg.get("active_start_hour",8)))
    end_h   = prompt("  End hour   (24h, 0–23)", str(cfg.get("active_end_hour",23)))

    if start_h.isdigit() and end_h.isdigit():
        cfg["active_start_hour"] = int(start_h)
        cfg["active_end_hour"]   = int(end_h)

    cfg["night_mode"] = confirm("  Enforce Night Mode (12am–7am pause)?", default=cfg.get("night_mode",False))

    rest_min = prompt("  Min rest between accounts (minutes)", str(cfg.get("rest_min_minutes",5)))
    rest_max = prompt("  Max rest between accounts (minutes)", str(cfg.get("rest_max_minutes",15)))
    if rest_min.isdigit(): cfg["rest_min_minutes"] = int(rest_min)
    if rest_max.isdigit(): cfg["rest_max_minutes"] = int(rest_max)

    config.save_settings(cfg)
    print_success(
        f"Active hours: {cfg['active_start_hour']}:00 – {cfg['active_end_hour']}:00  |  "
        f"Rest: {cfg.get('rest_min_minutes',5)}–{cfg.get('rest_max_minutes',15)} min"
    )
    input("\n  Press ENTER...")


# ─── Rotation Helpers ─────────────────────────────────────────────────────────

def pick_next_account(accounts: list = None, mode: str = None) -> dict | None:
    """Return the best next account based on current rotation settings."""
    import random
    if accounts is None:
        accounts = get_active_accounts()
    if not accounts:
        return None
    cfg  = config.load_settings()
    mode = mode or cfg.get("rotation_mode","smart")

    if mode == "random":
        return random.choice(accounts)
    elif mode == "load":
        return min(accounts, key=lambda a: a.get("today_imports",0) + a.get("today_messages",0))
    elif mode == "smart":
        from datetime import datetime
        def score(a):
            age_score = 0
            added_date = a.get("added_date","")
            if added_date:
                try:
                    from datetime import date
                    days = (date.today() - datetime.strptime(added_date[:10], "%Y-%m-%d").date()).days
                    age_score = min(days / 30, 10)
                except Exception:
                    pass
            usage_score = -(a.get("today_imports",0) + a.get("today_messages",0))
            prio_score  = a.get("priority", 0)
            return age_score + usage_score + prio_score
        return max(accounts, key=score)
    else:
        return accounts[0]
