import random
from rich.table import Table
from rich import box

from modules.utils import (
    console, print_header, print_success, print_info, print_warn,
    prompt, menu_choice, confirm, now_str, status_icon,
)
from modules.database import (
    load_accounts, save_accounts, reset_daily_counters, get_active_accounts,
)
import config

ROTATION_CFG_FILE = config.DATA_DIR / "rotation_cfg.json"


def rotation_menu():
    while True:
        print_header("🔄  Account Rotation System", "Distribute workload across accounts")
        choice = menu_choice([
            ("1", "⚙️  General Rotation Settings"),
            ("2", "📋  View Current Rotation Schedule"),
            ("3", "✏️  Edit Account Order"),
            ("4", "📊  View Account Limits & Daily Usage"),
            ("5", "🔄  Reset Daily Counters"),
        ])
        if choice == "1":
            rotation_settings()
        elif choice == "2":
            view_schedule()
        elif choice == "3":
            edit_order()
        elif choice == "4":
            view_usage()
        elif choice == "5":
            _reset_counters()
        elif choice == "0":
            break


def _load_cfg() -> dict:
    from modules.utils import read_json
    return read_json(ROTATION_CFG_FILE, _default_cfg())


def _save_cfg(cfg: dict):
    from modules.utils import write_json
    write_json(ROTATION_CFG_FILE, cfg)


def _default_cfg() -> dict:
    return {
        "mode":               "smart",
        "switch_after_ops":   5,
        "switch_after_mins":  10,
        "on_restrict":        "switch_retry",
        "on_all_limit":       "stop_resume",
    }


# ─── Rotation Settings ───────────────────────────────────────────────────────

def rotation_settings():
    print_header("⚙️  Rotation Configuration")
    cfg = _load_cfg()

    console.print("  1️⃣  Rotation Mode")
    console.print("  [1] 🔁 Sequential")
    console.print("  [2] 🎲 Random")
    console.print("  [3] ⚖️  Weighted (Least-Used First)")
    console.print("  [4] 🧠 Smart  ⭐  (Status + Age + Activity)")
    mode_map = {"1": "sequential", "2": "random", "3": "weighted", "4": "smart"}
    m = prompt(f"\n  Select Mode (current: {cfg['mode']})", "4")
    cfg["mode"] = mode_map.get(m, "smart")

    console.print("\n  2️⃣  Switch Condition")
    console.print("  [1] After N Operations")
    console.print("  [2] After N Minutes")
    console.print("  [3] After First Error")
    console.print("  [4] Mixed (Operations + Time, whichever first)")
    sc = prompt("  Select", "4")
    if sc == "1":
        cfg["switch_after_ops"] = int(prompt("  Operations before switch", str(cfg["switch_after_ops"])) or cfg["switch_after_ops"])
    elif sc == "2":
        cfg["switch_after_mins"] = int(prompt("  Minutes before switch", str(cfg["switch_after_mins"])) or cfg["switch_after_mins"])
    elif sc == "4":
        cfg["switch_after_ops"] = int(prompt("  Max operations", str(cfg["switch_after_ops"])) or cfg["switch_after_ops"])
        cfg["switch_after_mins"] = int(prompt("  Max minutes", str(cfg["switch_after_mins"])) or cfg["switch_after_mins"])

    console.print("\n  3️⃣  On Account Restriction")
    console.print("  [1] Immediate Switch + Remove from Rotation")
    console.print("  [2] Switch + Retry After 1 Hour")
    console.print("  [3] Stop All + Notify")
    rc = prompt("  Select", "2")
    cfg["on_restrict"] = {"1": "switch_remove", "2": "switch_retry", "3": "stop_notify"}.get(rc, "switch_retry")

    console.print("\n  4️⃣  When All Accounts Hit Limit")
    console.print("  [1] Stop + Resume Next Day  ⭐")
    console.print("  [2] Stop + Notify Only")
    console.print("  [3] Wait for Next Available Account")
    al = prompt("  Select", "1")
    cfg["on_all_limit"] = {"1": "stop_resume", "2": "stop_notify", "3": "wait"}.get(al, "stop_resume")

    _save_cfg(cfg)
    print_success("Rotation settings saved.")
    input("\n  Press ENTER...")


# ─── View Schedule ───────────────────────────────────────────────────────────

def view_schedule():
    print_header("📋  Current Rotation Schedule")
    accounts = get_active_accounts()
    if not accounts:
        print_info("No active accounts.")
        input("\n  Press ENTER...")
        return

    cfg = _load_cfg()
    mode = cfg["mode"]
    console.print(f"  Rotation Mode: [bold cyan]{mode.upper()}[/bold cyan]")
    console.print()

    if mode == "sequential":
        order = accounts
    elif mode == "random":
        order = accounts[:]
        random.shuffle(order)
    elif mode == "weighted":
        order = sorted(accounts, key=lambda a: a.get("today_imports", 0))
    else:
        order = sorted(accounts, key=lambda a: (
            0 if a.get("status") == "active" else 1,
            a.get("today_imports", 0),
        ))

    for i, a in enumerate(order, 1):
        status = "◀ Next" if i == 1 else ""
        console.print(f"  [{i}] {a['phone']}  ({a.get('name','N/A')})  [dim]{status}[/dim]")

    input("\n  Press ENTER...")


# ─── Edit Order ──────────────────────────────────────────────────────────────

def edit_order():
    print_header("✏️  Edit Account Order")
    accounts = load_accounts()
    for i, a in enumerate(accounts, 1):
        console.print(f"  [{i}] {a['phone']}  ({a.get('name','N/A')})")

    console.print("\n  Enter new order (e.g. 3,1,2,4):")
    new_order = prompt("  Order")
    try:
        indices = [int(x.strip()) - 1 for x in new_order.split(",")]
        reordered = [accounts[i] for i in indices if 0 <= i < len(accounts)]
        remaining = [a for i, a in enumerate(accounts) if i not in indices]
        final = reordered + remaining
        save_accounts(final)
        print_success("Account order updated.")
    except Exception as e:
        print_info(f"Error: {e} — order unchanged.")
    input("\n  Press ENTER...")


# ─── View Usage ──────────────────────────────────────────────────────────────

def view_usage():
    print_header("📊  Account Limits & Daily Usage")
    accounts = load_accounts()
    if not accounts:
        print_info("No accounts found.")
        input("\n  Press ENTER...")
        return

    settings = config.load_settings()
    daily_imp  = settings.get("daily_import_limit", 20)
    daily_col  = settings.get("daily_collection_limit", 500)
    daily_msg  = settings.get("daily_message_limit", 30)

    table = Table(box=box.SIMPLE_HEAVY, border_style="cyan")
    table.add_column("#",          width=4, justify="right")
    table.add_column("Account",    width=17, style="bold white")
    table.add_column("Collection", width=14, justify="right")
    table.add_column("Imports",    width=12, justify="right")
    table.add_column("Messages",   width=12, justify="right")
    table.add_column("Status",     width=20)

    total_col = total_imp = total_msg = 0
    for i, a in enumerate(accounts, 1):
        tc = a.get("today_collections", 0)
        ti = a.get("today_imports", 0)
        tm = a.get("today_messages", 0)
        total_col += tc; total_imp += ti; total_msg += tm

        st = a.get("status", "unknown")
        sc = "green" if st == "active" else ("red" if st == "banned" else "yellow")

        def _fmt(used, limit):
            c = "red" if used >= limit else ("yellow" if used >= limit * 0.8 else "green")
            return f"[{c}]{used}/{limit}[/{c}]" + (" 🔴" if used >= limit else "")

        table.add_row(
            str(i),
            a["phone"][-12:],
            _fmt(tc, daily_col),
            _fmt(ti, daily_imp),
            _fmt(tm, daily_msg),
            f"[{sc}]{status_icon(st)}[/{sc}]",
        )

    console.print(table)
    console.print(f"\n  📊 Today's Totals:")
    console.print(f"  Collection : [cyan]{total_col}[/cyan]  |  Imports : [green]{total_imp}[/green]  |  Messages : [yellow]{total_msg}[/yellow]")

    from modules.utils import now_str
    from datetime import datetime, timedelta
    now = datetime.now()
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    diff = midnight - now
    h, rem = divmod(int(diff.total_seconds()), 3600)
    m = rem // 60
    console.print(f"\n  ⏱  Counter Reset In: [bold]{h}h {m}m[/bold] (midnight)")

    input("\n  Press ENTER...")


# ─── Reset Counters ──────────────────────────────────────────────────────────

def _reset_counters():
    if confirm("  Reset all daily counters for all accounts?"):
        reset_daily_counters()
        print_success("Daily counters reset.")
    input("\n  Press ENTER...")


# ─── Smart Account Picker ─────────────────────────────────────────────────────

def pick_next_account(accounts: list[dict], mode: str = "smart") -> dict | None:
    active = [a for a in accounts if a.get("status") == "active"]
    if not active:
        return None
    if mode == "sequential":
        return active[0]
    elif mode == "random":
        return random.choice(active)
    elif mode == "weighted":
        return min(active, key=lambda a: a.get("today_imports", 0))
    else:  # smart
        return min(active, key=lambda a: (
            a.get("today_imports", 0) + a.get("today_collections", 0),
        ))
