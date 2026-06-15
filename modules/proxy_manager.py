import asyncio
import socket
from rich.table import Table
from rich import box

from modules.utils import (
    console, print_header, print_success, print_error, print_info, print_warn,
    prompt, menu_choice, confirm, now_str, progress_bar,
)
from modules.database import (
    load_proxies, save_proxies, add_proxy, remove_proxy, update_proxy,
    load_accounts, save_accounts, get_unassigned_proxies,
)


def proxy_manager_menu():
    while True:
        print_header("🌐  Proxy Manager", "Configure and manage proxy connections")
        proxies = load_proxies()
        alive   = sum(1 for p in proxies if p.get("status") == "alive")
        console.print(f"  Total: [bold]{len(proxies)}[/bold]  |  Alive: [bold green]{alive}[/bold green]  |  Dead: [bold red]{len(proxies)-alive}[/bold red]")
        console.print()

        choice = menu_choice([
            ("1", "➕  Add New Proxy"),
            ("2", "📂  Import Proxy List (.txt)"),
            ("3", "📋  View All Proxies"),
            ("4", "✅  Validate Proxies"),
            ("5", "🔗  Assign Proxy to Account"),
            ("6", "🔗  Automatic Proxy Assignment"),
            ("7", "❌  Remove Dead Proxies"),
        ])
        if choice == "1":
            add_proxy_menu()
        elif choice == "2":
            import_proxies()
        elif choice == "3":
            view_proxies()
        elif choice == "4":
            asyncio.run(validate_proxies())
        elif choice == "5":
            assign_proxy_to_account()
        elif choice == "6":
            auto_assign_proxies()
        elif choice == "7":
            remove_dead_proxies()
        elif choice == "0":
            break


# ─── Add Proxy ────────────────────────────────────────────────────────────────

def add_proxy_menu():
    print_header("➕  Add New Proxy")
    console.print("  Proxy Type:")
    console.print("  [1] SOCKS5  [2] SOCKS4  [3] HTTP/HTTPS  [4] MTProto")
    ptype_choice = prompt("  Select", "1")
    ptype = {"1": "socks5", "2": "socks4", "3": "http", "4": "mtproto"}.get(ptype_choice, "socks5")

    console.print("\n  Enter manually or paste as IP:PORT:USER:PASS format")
    raw = prompt("  Proxy (or press ENTER for manual entry)")

    if raw and ":" in raw:
        parts = raw.strip().split(":")
        host = parts[0]
        port = parts[1]
        username = parts[2] if len(parts) > 2 else ""
        password = parts[3] if len(parts) > 3 else ""
    else:
        host     = prompt("  IP Address / Host")
        port     = prompt("  Port")
        username = prompt("  Username (optional)")
        password = prompt("  Password (optional)")

    if not host or not port:
        print_error("Host and port are required.")
        input("\n  Press ENTER...")
        return

    proxy_data = {
        "type":     ptype,
        "host":     host,
        "port":     int(port),
        "username": username,
        "password": password,
    }
    add_proxy(proxy_data)
    print_success(f"Proxy {host}:{port} ({ptype}) added.")
    input("\n  Press ENTER...")


# ─── Import from File ────────────────────────────────────────────────────────

def import_proxies():
    print_header("📂  Import Proxy List")
    filepath = prompt("  Path to .txt file", "proxies.txt")
    try:
        with open(filepath, "r") as f:
            lines = [l.strip() for l in f if l.strip()]
    except FileNotFoundError:
        print_error(f"File not found: {filepath}")
        input("\n  Press ENTER...")
        return

    console.print(f"\n  [bold]{len(lines)}[/bold] lines found.")
    console.print("  Default proxy type: [1] SOCKS5  [2] SOCKS4  [3] HTTP")
    ptype = {"1": "socks5", "2": "socks4", "3": "http"}.get(prompt("  Type", "1"), "socks5")

    imported = 0
    for line in lines:
        parts = line.split(":")
        if len(parts) < 2:
            continue
        proxy_data = {
            "type":     ptype,
            "host":     parts[0],
            "port":     int(parts[1]) if parts[1].isdigit() else 0,
            "username": parts[2] if len(parts) > 2 else "",
            "password": parts[3] if len(parts) > 3 else "",
        }
        if proxy_data["port"]:
            add_proxy(proxy_data)
            imported += 1

    print_success(f"Imported {imported} proxies.")
    input("\n  Press ENTER...")


# ─── View Proxies ─────────────────────────────────────────────────────────────

def view_proxies():
    print_header("📋  All Proxies")
    proxies = load_proxies()
    if not proxies:
        print_info("No proxies configured.")
        input("\n  Press ENTER...")
        return

    table = Table(box=box.SIMPLE_HEAVY, border_style="cyan")
    table.add_column("#",       width=4, justify="right")
    table.add_column("Type",    width=8)
    table.add_column("Host",    width=20, style="bold white")
    table.add_column("Port",    width=7, justify="right")
    table.add_column("Auth",    width=8)
    table.add_column("Status",  width=12)
    table.add_column("Account", width=17)

    accounts = load_accounts()
    proxy_to_account = {}
    for a in accounts:
        if a.get("proxy_id"):
            proxy_to_account[a["proxy_id"]] = a["phone"]

    for p in proxies:
        st = p.get("status", "unknown")
        sc = "green" if st == "alive" else ("red" if st == "dead" else "dim")
        icon = "✅" if st == "alive" else ("❌" if st == "dead" else "❓")
        assigned = proxy_to_account.get(p["id"], "—")
        auth = "✅" if p.get("username") else "—"
        table.add_row(
            str(p["id"]),
            p.get("type", "?").upper(),
            p["host"],
            str(p["port"]),
            auth,
            f"[{sc}]{icon} {st.title()}[/{sc}]",
            assigned,
        )

    console.print(table)
    input("\n  Press ENTER...")


# ─── Validate Proxies ────────────────────────────────────────────────────────

async def validate_proxies():
    print_header("✅  Validate Proxies")
    proxies = load_proxies()
    if not proxies:
        print_info("No proxies to validate.")
        input("\n  Press ENTER...")
        return

    console.print(f"  Testing [bold]{len(proxies)}[/bold] proxies...\n")
    alive = dead = 0

    for p in proxies:
        host = p["host"]
        port = p["port"]
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _tcp_test, host, port)
            update_proxy(p["id"], {"status": "alive", "checked_at": now_str()})
            console.print(f"  ✅ [green]{host}:{port}[/green]  (ALIVE)")
            alive += 1
        except Exception:
            update_proxy(p["id"], {"status": "dead", "checked_at": now_str()})
            console.print(f"  ❌ [red]{host}:{port}[/red]  (DEAD)")
            dead += 1

    console.print(f"\n  Alive: [green]{alive}[/green]  Dead: [red]{dead}[/red]")
    input("\n  Press ENTER...")


def _tcp_test(host: str, port: int, timeout: float = 5.0):
    s = socket.create_connection((host, port), timeout=timeout)
    s.close()


# ─── Assign Proxy to Account ──────────────────────────────────────────────────

def assign_proxy_to_account(target_phone: str = ""):
    print_header("🔗  Assign Proxy to Account")
    proxies = [p for p in load_proxies() if p.get("status") != "dead"]
    accounts = load_accounts()

    if not proxies:
        print_error("No available proxies. Add proxies first.")
        input("\n  Press ENTER...")
        return

    if not target_phone:
        for i, a in enumerate(accounts, 1):
            cur = a.get("proxy_id")
            console.print(f"  [{i}] {a['phone']}  {'(proxy: #'+str(cur)+')' if cur else '(no proxy)'}")
        sel = prompt("  Select Account #")
        if not sel or not sel.isdigit():
            return
        idx = int(sel) - 1
        if not (0 <= idx < len(accounts)):
            return
        target_phone = accounts[idx]["phone"]

    console.print(f"\n  Available Proxies:")
    for i, p in enumerate(proxies, 1):
        console.print(f"  [{i}] {p['type'].upper()}  {p['host']}:{p['port']}")

    psel = prompt("  Select Proxy #", "1")
    if not psel.isdigit():
        return
    pidx = int(psel) - 1
    if not (0 <= pidx < len(proxies)):
        return

    selected_proxy = proxies[pidx]
    for acc in accounts:
        if acc["phone"] == target_phone:
            acc["proxy_id"] = selected_proxy["id"]
    save_accounts(accounts)
    print_success(f"Proxy #{selected_proxy['id']} ({selected_proxy['host']}:{selected_proxy['port']}) assigned to {target_phone}")
    input("\n  Press ENTER...")


# ─── Auto Assign ─────────────────────────────────────────────────────────────

def auto_assign_proxies():
    print_header("🔗  Automatic Proxy Assignment")

    console.print("  Assignment Method:")
    console.print("  [1] One Proxy Per Account (1:1)")
    console.print("  [2] One Proxy per 3 Accounts (1:3)")
    console.print("  [3] One Proxy per 5 Accounts (1:5)")
    console.print("  [4] Custom")
    mode = prompt("  Select", "1")
    ratio = {"1": 1, "2": 3, "3": 5}.get(mode)
    if not ratio:
        ratio = int(prompt("  Accounts per proxy", "2") or "2")

    accounts = load_accounts()
    proxies  = [p for p in load_proxies() if p.get("status") != "dead"]
    unproxied = [a for a in accounts if not a.get("proxy_id")]

    console.print(f"\n  Accounts without proxy : [bold]{len(unproxied)}[/bold]")
    console.print(f"  Available proxies      : [bold]{len(proxies)}[/bold]")

    if not proxies:
        print_error("No available proxies.")
        input("\n  Press ENTER...")
        return

    if len(proxies) * ratio < len(unproxied):
        print_warn(f"Not enough proxies to cover all accounts at 1:{ratio} ratio.")

    if not confirm("  Start automatic assignment?"):
        return

    assigned = 0
    for i, acc in enumerate(unproxied):
        proxy_idx = i // ratio
        if proxy_idx >= len(proxies):
            break
        proxy = proxies[proxy_idx]
        for a in accounts:
            if a["phone"] == acc["phone"]:
                a["proxy_id"] = proxy["id"]
        assigned += 1

    save_accounts(accounts)
    print_success(f"Assigned proxies to {assigned} accounts.")
    input("\n  Press ENTER...")


# ─── Remove Dead ─────────────────────────────────────────────────────────────

def remove_dead_proxies():
    proxies = load_proxies()
    dead = [p for p in proxies if p.get("status") == "dead"]
    console.print(f"\n  Dead proxies found: [red]{len(dead)}[/red]")
    if not dead:
        print_info("No dead proxies to remove.")
        input("\n  Press ENTER...")
        return
    if confirm(f"  Remove all {len(dead)} dead proxies?"):
        for p in dead:
            remove_proxy(p["id"])
        print_success(f"Removed {len(dead)} dead proxies.")
    input("\n  Press ENTER...")
