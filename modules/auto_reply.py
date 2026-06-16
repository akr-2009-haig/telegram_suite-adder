import asyncio
import re
from modules.utils import (
    console, print_header, print_success, print_error, print_info, print_warn,
    prompt, menu_choice, confirm, now_str,
)
from modules.database import (
    load_auto_replies, save_auto_replies, add_auto_reply,
    remove_auto_reply, toggle_auto_reply, get_active_accounts,
)
import config


def auto_reply_menu():
    while True:
        rules = load_auto_replies()
        enabled = sum(1 for r in rules if r.get("enabled"))
        print_header("🤖  Auto-Reply System", f"Active Rules: {enabled} / {len(rules)}")

        choice = menu_choice([
            ("1", "➕  Create New Rule"),
            ("2", "📋  View All Rules"),
            ("3", "✏️  Edit Rule"),
            ("4", "🔛  Enable / Disable Rule"),
            ("5", "❌  Delete Rule"),
            ("6", "📊  Reply Statistics"),
            ("7", "▶️   Start Listener"),
        ])

        if choice == "1":   create_rule()
        elif choice == "2": view_rules()
        elif choice == "3": edit_rule()
        elif choice == "4": toggle_rule()
        elif choice == "5": delete_rule()
        elif choice == "6": reply_stats()
        elif choice == "7": asyncio.run(start_listener())
        elif choice == "0": break


def create_rule():
    print_header("➕  Create Auto-Reply Rule")
    console.print("  Trigger Type:")
    console.print("  [1] Exact keyword match")
    console.print("  [2] Contains keyword")
    console.print("  [3] Regex pattern")
    console.print("  [4] Any message (reply to all)")
    ttype = prompt("  Select", "2")

    keyword = ""
    if ttype in ("1", "2", "3"):
        keyword = prompt("  Keyword / Pattern")
        if not keyword:
            return

    reply_text = prompt("  Reply text (use {name} for sender's first name)")
    if not reply_text:
        print_error("Reply text is required.")
        input("\n  Press ENTER...")
        return

    delay_min = int(prompt("  Min delay before reply (sec)", "5") or 5)
    delay_max = int(prompt("  Max delay before reply (sec)", "15") or 15)

    rule = {
        "trigger_type": ttype, "keyword": keyword,
        "reply_text": reply_text,
        "delay_min": delay_min, "delay_max": delay_max,
    }
    add_auto_reply(rule)
    print_success("Auto-reply rule created.")
    input("\n  Press ENTER...")


def view_rules():
    print_header("📋  Auto-Reply Rules")
    rules = load_auto_replies()
    if not rules:
        print_info("No rules configured.")
        input("\n  Press ENTER...")
        return
    ttype_map = {"1": "Exact", "2": "Contains", "3": "Regex", "4": "Any"}
    for r in rules:
        st  = "[bold green]ON [/bold green]" if r.get("enabled") else "[bold red]OFF[/bold red]"
        kw  = r.get("keyword","—")[:25] or "(any)"
        rep = r.get("reply_text","")[:35]
        cnt = r.get("trigger_count", 0)
        tt  = ttype_map.get(r.get("trigger_type","2"), "?")
        console.print(f"  [dim]#{r['id']}[/dim]  {st}  [{tt}] [cyan]{kw}[/cyan] → [white]{rep}[/white]  [dim]fired:{cnt}[/dim]")
    input("\n  Press ENTER...")


def edit_rule():
    print_header("✏️  Edit Rule")
    rules = load_auto_replies()
    if not rules:
        print_info("No rules to edit.")
        input("\n  Press ENTER...")
        return
    for r in rules:
        console.print(f"  [{r['id']}] {r.get('keyword','(any)')} → {r.get('reply_text','')[:30]}")
    rid = prompt("  Rule # to edit")
    if not rid.isdigit():
        return
    rule = next((r for r in rules if r["id"] == int(rid)), None)
    if not rule:
        print_error("Not found.")
        input("\n  Press ENTER...")
        return
    new_kw  = prompt("  Keyword (ENTER keep)", rule.get("keyword",""))
    new_rep = prompt("  Reply (ENTER keep)", rule.get("reply_text",""))
    new_dmin = prompt("  Min delay sec (ENTER keep)", str(rule.get("delay_min",5)))
    new_dmax = prompt("  Max delay sec (ENTER keep)", str(rule.get("delay_max",15)))
    for i, r in enumerate(rules):
        if r["id"] == int(rid):
            rules[i].update({
                "keyword":    new_kw   or rule.get("keyword",""),
                "reply_text": new_rep  or rule.get("reply_text",""),
                "delay_min":  int(new_dmin) if new_dmin.isdigit() else rule.get("delay_min",5),
                "delay_max":  int(new_dmax) if new_dmax.isdigit() else rule.get("delay_max",15),
            })
    save_auto_replies(rules)
    print_success("Rule updated.")
    input("\n  Press ENTER...")


def toggle_rule():
    print_header("🔛  Enable / Disable Rule")
    rules = load_auto_replies()
    if not rules:
        print_info("No rules.")
        input("\n  Press ENTER...")
        return
    for r in rules:
        st = "ON" if r.get("enabled") else "OFF"
        console.print(f"  [{r['id']}] [{st}] {r.get('keyword','(any)')}")
    rid = prompt("  Rule # to toggle")
    if not rid.isdigit():
        return
    result = toggle_auto_reply(int(rid))
    if result is None:
        print_error("Not found.")
    else:
        print_success("Rule " + ("enabled." if result else "disabled."))
    input("\n  Press ENTER...")


def delete_rule():
    print_header("❌  Delete Rule")
    rules = load_auto_replies()
    if not rules:
        print_info("No rules.")
        input("\n  Press ENTER...")
        return
    for r in rules:
        console.print(f"  [{r['id']}] {r.get('keyword','(any)')}")
    rid = prompt("  Rule # to delete")
    if not rid.isdigit():
        return
    if confirm(f"  Delete rule #{rid}?"):
        remove_auto_reply(int(rid))
        print_success("Deleted.")
    input("\n  Press ENTER...")


def reply_stats():
    print_header("📊  Auto-Reply Statistics")
    rules = load_auto_replies()
    if not rules:
        print_info("No rules.")
        input("\n  Press ENTER...")
        return
    total = sum(r.get("trigger_count",0) for r in rules)
    enabled = sum(1 for r in rules if r.get("enabled"))
    console.print(f"  Total Rules   : [bold]{len(rules)}[/bold]")
    console.print(f"  Active Rules  : [bold green]{enabled}[/bold green]")
    console.print(f"  Total Fired   : [bold cyan]{total}[/bold cyan]\n")
    top = sorted(rules, key=lambda r: r.get("trigger_count",0), reverse=True)[:5]
    console.print("  ── Top Rules ──────────────")
    for r in top:
        console.print(f"  #{r['id']} [cyan]{r.get('keyword','any')}[/cyan] fired: [bold]{r.get('trigger_count',0)}[/bold]")
    input("\n  Press ENTER...")


async def start_listener():
    print_header("▶️   Auto-Reply Listener")
    rules = [r for r in load_auto_replies() if r.get("enabled")]
    if not rules:
        print_error("No enabled rules.")
        input("\n  Press ENTER...")
        return
    accounts = get_active_accounts()
    if not accounts:
        print_error("No active accounts.")
        input("\n  Press ENTER...")
        return

    api_id, api_hash = config.get_api_credentials()
    console.print(f"  Listening on [bold]{len(accounts[:3])}[/bold] account(s) — [bold]{len(rules)}[/bold] rule(s)")
    console.print("  Press Ctrl+C to stop\n")

    import random
    clients = []
    for acc in accounts[:3]:
        session = str(config.SESSIONS_DIR / acc["phone"])
        try:
            from telethon import TelegramClient, events
            client = TelegramClient(session, int(api_id), api_hash)
            await client.connect()
            if not await client.is_user_authorized():
                continue

            @client.on(events.NewMessage(incoming=True))
            async def handler(event, _rules=rules):
                text = event.raw_text or ""
                sender = await event.get_sender()
                name   = getattr(sender, "first_name", "") or "there"
                for rule in _rules:
                    matched = False
                    ttype = rule.get("trigger_type","2")
                    kw    = rule.get("keyword","")
                    if ttype == "4": matched = True
                    elif ttype == "1": matched = text.strip().lower() == kw.strip().lower()
                    elif ttype == "2": matched = kw.lower() in text.lower()
                    elif ttype == "3":
                        try: matched = bool(re.search(kw, text, re.IGNORECASE))
                        except re.error: pass
                    if matched:
                        await asyncio.sleep(random.randint(rule.get("delay_min",5), rule.get("delay_max",15)))
                        await event.reply(rule["reply_text"].replace("{name}", name))
                        all_rules = load_auto_replies()
                        for i, r in enumerate(all_rules):
                            if r["id"] == rule["id"]:
                                all_rules[i]["trigger_count"] = r.get("trigger_count",0)+1
                        save_auto_replies(all_rules)
                        console.print(f"  [dim]{now_str()[:19]}[/dim]  ✅ Replied to [cyan]{name}[/cyan] — Rule #{rule['id']}")
                        break

            clients.append(client)
            print_success(f"Listening: {acc['phone']}")
        except Exception as e:
            print_warn(f"  {acc['phone']}: {e}")

    if not clients:
        print_error("No clients connected.")
        input("\n  Press ENTER...")
        return
    try:
        await asyncio.gather(*[c.run_until_disconnected() for c in clients])
    except KeyboardInterrupt:
        print_warn("Listener stopped.")
    finally:
        for c in clients:
            try: await c.disconnect()
            except: pass
    input("\n  Press ENTER...")
