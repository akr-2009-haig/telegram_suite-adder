import asyncio
import time
import random
from pathlib import Path
from modules.utils import (
    console, print_header, print_success, print_error, print_info, print_warn,
    prompt, menu_choice, confirm, now_str,
)
from modules.database import (
    load_proxies, save_proxies, add_proxy, remove_proxy,
    update_proxy, load_accounts, save_accounts, get_unassigned_proxies,
)


def proxy_manager_menu():
    while True:
        proxies = load_proxies()
        alive   = sum(1 for p in proxies if p.get("status") == "alive")
        print_header("🌐  Proxy Manager", f"Total: {len(proxies)}  |  Alive: {alive}")

        choice = menu_choice([
            ("1",  "➕  Add New Proxy"),
            ("2",  "📂  Import Proxy List (from file)"),
            ("3",  "📋  View All Proxies"),
            ("4",  "✅  Test / Validate Proxies"),
            ("5",  "🔗  Assign Proxy to Account"),
            ("6",  "🔗  Auto-Assign Proxies"),
            ("7",  "❌  Remove Dead Proxies"),
            ("8",  "🔄  Auto-Rotate Proxies"),
            ("9",  "📊  Proxy Speed Statistics"),
            ("10", "🌍  Free Proxy Sources"),
        ])

        if choice == "1":   add_proxy_menu()
        elif choice == "2": import_proxies()
        elif choice == "3": view_proxies()
        elif choice == "4": asyncio.run(test_all_proxies())
        elif choice == "5": assign_proxy_to_account()
        elif choice == "6": auto_assign_proxies()
        elif choice == "7": remove_dead_proxies()
        elif choice == "8": auto_rotate_settings()
        elif choice == "9": proxy_speed_stats()
        elif choice == "10": free_proxy_sources()
        elif choice == "0": break


def add_proxy_menu():
    print_header("➕  Add New Proxy")
    console.print("  Type:")
    console.print("  [1] SOCKS5  [2] SOCKS4  [3] HTTP/HTTPS  [4] MTProto")
    type_map = {"1":"socks5","2":"socks4","3":"http","4":"mtproto"}
    ptype = type_map.get(prompt("  Select","1"),"socks5")

    console.print("\n  You can enter manually OR use shorthand IP:PORT[:USER:PASS]\n")
    shorthand = prompt("  Shorthand (or ENTER for manual)")
    if shorthand and ":" in shorthand:
        parts = shorthand.split(":")
        host  = parts[0]
        port  = int(parts[1]) if len(parts) > 1 else 1080
        user  = parts[2] if len(parts) > 2 else ""
        pwd   = parts[3] if len(parts) > 3 else ""
    else:
        host  = prompt("  Host / IP")
        port  = int(prompt("  Port", "1080") or 1080)
        user  = prompt("  Username (optional)", "")
        pwd   = prompt("  Password (optional)", "")

    proxy = {
        "type":     ptype,
        "host":     host,
        "port":     port,
        "username": user,
        "password": pwd,
    }
    add_proxy(proxy)
    proxy_id = load_proxies()[-1]["id"]
    print_success(f"Proxy added (ID #{proxy_id}).")

    if confirm("  Test connection now?"):
        asyncio.run(_test_single_proxy(proxy_id))
    input("\n  Press ENTER...")


def import_proxies():
    print_header("📂  Import Proxy List")
    console.print("  Format per line: HOST:PORT or HOST:PORT:USER:PASS\n")
    fpath = prompt("  File path (.txt)")
    if not fpath or not Path(fpath).exists():
        print_error("File not found.")
        input("\n  Press ENTER...")
        return
    lines  = Path(fpath).read_text(encoding="utf-8").strip().splitlines()
    console.print("\n  Proxy type for all:")
    console.print("  [1] SOCKS5  [2] SOCKS4  [3] HTTP")
    type_map = {"1":"socks5","2":"socks4","3":"http"}
    ptype = type_map.get(prompt("  Select","1"),"socks5")

    imported = 0
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(":")
        if len(parts) < 2:
            continue
        try:
            proxy = {
                "type":     ptype,
                "host":     parts[0],
                "port":     int(parts[1]),
                "username": parts[2] if len(parts) > 2 else "",
                "password": parts[3] if len(parts) > 3 else "",
            }
            add_proxy(proxy)
            imported += 1
        except Exception:
            pass
    print_success(f"Imported {imported} proxies.")

    if imported > 0 and confirm("  Test all imported proxies?"):
        asyncio.run(test_all_proxies())
    input("\n  Press ENTER...")


def view_proxies():
    print_header("📋  All Proxies")
    proxies = load_proxies()
    if not proxies:
        print_info("No proxies configured.")
        input("\n  Press ENTER...")
        return
    console.print(f"  {'#':<4} {'Type':<8} {'Host':<22} {'Port':<6} {'Status':<10} {'Ping':<8} {'Auth'}")
    console.print("  " + "─" * 72)
    for p in proxies:
        st  = p.get("status","unknown")
        col = "green" if st=="alive" else ("red" if st=="dead" else "dim")
        ping = p.get("ping_ms","—")
        auth = "✓" if p.get("username") else "—"
        console.print(
            f"  {str(p['id']):<4} {p.get('type','?'):<8} {p.get('host','?'):<22} "
            f"{str(p.get('port','?')):<6} [{col}]{st:<10}[/{col}] {str(ping):<8} {auth}"
        )
    console.print(f"\n  Total: [bold]{len(proxies)}[/bold]  |  "
                  f"Alive: [green]{sum(1 for p in proxies if p.get('status')=='alive')}[/green]  |  "
                  f"Dead: [red]{sum(1 for p in proxies if p.get('status')=='dead')}[/red]")
    input("\n  Press ENTER...")


async def test_all_proxies():
    print_header("✅  Testing All Proxies")
    proxies = load_proxies()
    if not proxies:
        print_info("No proxies to test.")
        input("\n  Press ENTER...")
        return
    for p in proxies:
        await _test_single_proxy(p["id"])
    alive = sum(1 for p in load_proxies() if p.get("status")=="alive")
    console.print(f"\n  Results: [green]{alive}[/green] alive / [red]{len(proxies)-alive}[/red] dead")
    input("\n  Press ENTER...")


async def _test_single_proxy(proxy_id: int):
    proxies = load_proxies()
    p = next((x for x in proxies if x["id"] == proxy_id), None)
    if not p:
        return
    console.print(f"  Testing {p['host']}:{p['port']}...", end=" ")
    try:
        import socket
        start = time.time()
        sock = socket.create_connection((p["host"], p["port"]), timeout=8)
        sock.close()
        ping_ms = int((time.time() - start) * 1000)
        update_proxy(proxy_id, {"status":"alive","ping_ms":ping_ms,"last_checked":now_str()})
        console.print(f"[green]✅ alive ({ping_ms}ms)[/green]")
    except Exception as e:
        update_proxy(proxy_id, {"status":"dead","last_checked":now_str()})
        console.print(f"[red]❌ dead — {str(e)[:30]}[/red]")


def assign_proxy_to_account():
    print_header("🔗  Assign Proxy to Account")
    accounts = load_accounts()
    proxies  = [p for p in load_proxies() if p.get("status") == "alive"]
    if not accounts:
        print_error("No accounts.")
        input("\n  Press ENTER...")
        return
    if not proxies:
        print_error("No alive proxies.")
        input("\n  Press ENTER...")
        return
    for i, a in enumerate(accounts, 1):
        pid = a.get("proxy_id","—")
        console.print(f"  [{i}] {a['phone']}  proxy: {pid}")
    ach = prompt("  Account #")
    if not ach.isdigit():
        return
    acc = accounts[int(ach)-1]
    for p in proxies:
        console.print(f"  [{p['id']}] {p['type']} {p['host']}:{p['port']}  ({p.get('ping_ms','?')}ms)")
    pch = prompt("  Proxy ID")
    if pch.isdigit():
        from modules.database import update_account
        update_account(acc["phone"], {"proxy_id": int(pch)})
        print_success(f"Proxy #{pch} assigned to {acc['phone']}.")
    input("\n  Press ENTER...")


def auto_assign_proxies():
    print_header("🔗  Auto-Assign Proxies")
    accounts_no_proxy = [a for a in load_accounts() if not a.get("proxy_id")]
    proxies_available = get_unassigned_proxies()
    console.print(f"  Accounts without proxy : [bold]{len(accounts_no_proxy)}[/bold]")
    console.print(f"  Available proxies      : [bold]{len(proxies_available)}[/bold]\n")
    if not accounts_no_proxy or not proxies_available:
        print_info("Nothing to assign.")
        input("\n  Press ENTER...")
        return
    console.print("  Ratio mode:")
    console.print("  [1] 1:1 (one proxy per account)")
    console.print("  [2] 1:3")
    console.print("  [3] 1:5")
    ratio_map = {"1":1,"2":3,"3":5}
    ratio = ratio_map.get(prompt("  Select","1"),1)

    from modules.database import update_account
    assigned = 0
    for i, acc in enumerate(accounts_no_proxy):
        p = proxies_available[i // ratio % len(proxies_available)]
        update_account(acc["phone"], {"proxy_id": p["id"]})
        assigned += 1
    print_success(f"Assigned proxies to {assigned} account(s).")
    input("\n  Press ENTER...")


def remove_dead_proxies():
    print_header("❌  Remove Dead Proxies")
    proxies = load_proxies()
    dead = [p for p in proxies if p.get("status") == "dead"]
    if not dead:
        print_info("No dead proxies found.")
        input("\n  Press ENTER...")
        return
    console.print(f"  Dead proxies to remove: [red]{len(dead)}[/red]")
    for p in dead:
        console.print(f"  [red]✗[/red] {p['host']}:{p['port']}")
    if confirm(f"\n  Remove {len(dead)} dead proxy/proxies?"):
        save_proxies([p for p in proxies if p.get("status") != "dead"])
        print_success(f"Removed {len(dead)} dead proxy/proxies.")
    input("\n  Press ENTER...")


def auto_rotate_settings():
    print_header("🔄  Auto-Rotate Proxies")
    cfg = config.load_settings() if hasattr(__import__("config"), "load_settings") else {}
    import config as _cfg
    cfg = _cfg.load_settings()
    console.print("  When auto-rotate is enabled, proxies are cycled periodically\n")
    cfg["proxy_auto_rotate"]    = confirm("  Enable auto-rotate?", default=cfg.get("proxy_auto_rotate",False))
    cfg["proxy_rotate_on_fail"] = confirm("  Rotate immediately on proxy failure?", default=True)
    cfg["proxy_notify_fail"]    = confirm("  Send notification when proxy fails?", default=True)
    _cfg.save_settings(cfg)
    print_success("Settings saved.")
    input("\n  Press ENTER...")


def proxy_speed_stats():
    print_header("📊  Proxy Speed Statistics")
    proxies = [p for p in load_proxies() if p.get("ping_ms") and p.get("status") == "alive"]
    if not proxies:
        print_info("No tested proxies. Run 'Test / Validate Proxies' first.")
        input("\n  Press ENTER...")
        return
    proxies_sorted = sorted(proxies, key=lambda p: p.get("ping_ms", 9999))
    console.print(f"  {'#':<4} {'Host':<22} {'Port':<6} {'Type':<8} {'Ping':>8}")
    console.print("  " + "─" * 54)
    for p in proxies_sorted:
        ping = p.get("ping_ms",0)
        col  = "green" if ping < 200 else ("yellow" if ping < 500 else "red")
        console.print(f"  {str(p['id']):<4} {p['host']:<22} {str(p['port']):<6} {p.get('type','?'):<8} [{col}]{ping:>6}ms[/{col}]")
    avg = sum(p.get("ping_ms",0) for p in proxies_sorted) // len(proxies_sorted)
    console.print(f"\n  Average ping: [bold cyan]{avg}ms[/bold cyan]  |  Fastest: [green]{proxies_sorted[0].get('ping_ms')}ms[/green]")
    input("\n  Press ENTER...")


def free_proxy_sources():
    print_header("🌍  Free Proxy Sources")
    console.print("  Some public proxy list websites:\n")
    sources = [
        "https://www.proxy-list.download/api/v1/get?type=socks5",
        "https://api.proxyscrape.com/?request=getproxies&proxytype=socks5",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt",
        "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
    ]
    for i, s in enumerate(sources, 1):
        console.print(f"  [{i}] [dim]{s}[/dim]")
    console.print("\n  You can download any of these and import via option 2 (Import Proxy List)")
    input("\n  Press ENTER...")
