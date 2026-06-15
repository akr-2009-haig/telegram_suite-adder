import asyncio
import random
import csv
from pathlib import Path
from datetime import datetime
from telethon import TelegramClient
from telethon.errors import FloodWaitError, PeerFloodError, UserPrivacyRestrictedError

import config
from modules.utils import (
    console, print_header, print_success, print_error, print_warn,
    print_info, prompt, menu_choice, confirm, now_str, date_str, wait_countdown,
)
from modules.database import (
    get_active_accounts, load_campaigns, save_campaigns,
    add_campaign, increment_stat, is_blacklisted, load_proxies,
)

EXPORTS_DIR = config.EXPORTS_DIR


def campaigns_menu():
    while True:
        print_header("📢  Outreach Campaigns", "Launch large-scale messaging campaigns")
        campaigns = load_campaigns()
        active_c  = sum(1 for c in campaigns if c.get("status") == "running")
        console.print(f"  Total Campaigns: [bold]{len(campaigns)}[/bold]  |  Running: [bold green]{active_c}[/bold green]")
        console.print()

        choice = menu_choice([
            ("1", "➕  Create New Campaign"),
            ("2", "▶️   Launch Campaign"),
            ("3", "📋  View All Campaigns"),
            ("4", "📊  Campaign Statistics"),
            ("5", "⏹️   Stop Campaign"),
            ("6", "🗑️  Delete Campaign"),
        ])
        if choice == "1":
            create_campaign()
        elif choice == "2":
            asyncio.run(launch_campaign())
        elif choice == "3":
            view_campaigns()
        elif choice == "4":
            campaign_stats()
        elif choice == "5":
            stop_campaign()
        elif choice == "6":
            delete_campaign()
        elif choice == "0":
            break


def _build_client(account: dict) -> TelegramClient:
    api_id, api_hash = config.get_api_credentials()
    session = str(config.SESSIONS_DIR / account["phone"])
    proxy = None
    if account.get("proxy_id"):
        for p in load_proxies():
            if p["id"] == account["proxy_id"]:
                try:
                    import socks
                    ptype = p.get("type", "socks5").lower()
                    pt = socks.SOCKS5 if "socks5" in ptype else socks.HTTP
                    proxy = (pt, p["host"], int(p["port"]), True,
                             p.get("username") or None, p.get("password") or None)
                except Exception:
                    pass
                break
    return TelegramClient(session, int(api_id), api_hash, proxy=proxy)


# ─── Create Campaign ─────────────────────────────────────────────────────────

def create_campaign():
    print_header("➕  Create New Campaign")

    name = prompt("  Campaign Name")
    if not name:
        return

    console.print("\n  Target Source:")
    console.print("  [1] CSV File (members list)")
    console.print("  [2] Group @username")
    console.print("  [3] Manual usernames list")
    source_type = prompt("  Select", "1")

    targets = []
    source_label = ""

    if source_type == "1":
        files = list(EXPORTS_DIR.glob("*.csv"))
        for i, f in enumerate(files, 1):
            console.print(f"  [{i}] {f.name}")
        sel = prompt("  File #", "1")
        try:
            filepath = files[int(sel) - 1]
            with open(filepath, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    u = row.get("username") or row.get("user_id") or ""
                    if u:
                        targets.append(str(u))
            source_label = filepath.name
        except Exception as e:
            print_error(str(e))
            input("\n  Press ENTER...")
            return

    elif source_type == "2":
        source_label = prompt("  Group @username or link")
        targets = [f"FROM_GROUP:{source_label}"]

    else:
        console.print("  Enter @usernames (type 'done' to finish):")
        i = 1
        while True:
            u = prompt(f"  {i}")
            if u.lower() in ("done", ""):
                break
            targets.append(u.strip().strip("@"))
            i += 1
        source_label = "manual"

    console.print("\n  ─── Message Content ──────────────────────")
    console.print("  [1] Single message for all")
    console.print("  [2] Random rotation (anti-spam)")
    msg_type = prompt("  Select", "1")

    messages = []
    if msg_type == "1":
        m = prompt("  Enter message")
        if m:
            messages = [m]
    else:
        console.print("  Enter messages (type 'done' to finish):")
        i = 1
        while True:
            m = prompt(f"  Msg {i}")
            if m.lower() in ("done", ""):
                break
            messages.append(m)
            i += 1

    if not messages:
        print_error("No message provided.")
        input("\n  Press ENTER...")
        return

    console.print("\n  ─── Delivery Settings ────────────────────")
    delay_min   = int(prompt("  Min delay (seconds)", "60") or "60")
    delay_max   = int(prompt("  Max delay (seconds)", "120") or "120")
    daily_limit = int(prompt("  Max messages per account per day", "30") or "30")
    switch_after= int(prompt("  Switch account after N messages", "10") or "10")

    campaign = {
        "name":         name,
        "source":       source_label,
        "targets":      targets,
        "messages":     messages,
        "delay_min":    delay_min,
        "delay_max":    delay_max,
        "daily_limit":  daily_limit,
        "switch_after": switch_after,
        "sent":         0,
        "failed":       0,
        "skipped":      0,
    }

    camp_id = add_campaign(campaign)
    print_success(f"Campaign '{name}' created with ID #{camp_id}")
    print_success(f"Targets: {len(targets)}  |  Messages: {len(messages)}")
    input("\n  Press ENTER...")


# ─── Launch Campaign ─────────────────────────────────────────────────────────

async def launch_campaign():
    print_header("▶️   Launch Campaign")
    campaigns = [c for c in load_campaigns() if c.get("status") in ("pending", "paused")]
    if not campaigns:
        print_info("No pending campaigns. Create one first.")
        input("\n  Press ENTER...")
        return

    for i, c in enumerate(campaigns, 1):
        console.print(f"  [{i}] #{c['id']}  {c['name']}  ({len(c.get('targets',[]))} targets)")
    sel = prompt("  Select campaign #", "1")
    try:
        camp = campaigns[int(sel) - 1]
    except Exception:
        print_error("Invalid selection.")
        input("\n  Press ENTER...")
        return

    accounts = get_active_accounts()
    if not accounts:
        print_error("No active accounts.")
        input("\n  Press ENTER...")
        return

    console.print(f"\n  🚀 Launching campaign: [bold]{camp['name']}[/bold]")
    console.print(f"  Targets  : [cyan]{len(camp.get('targets',[]))}[/cyan]")
    console.print(f"  Accounts : [cyan]{len(accounts)}[/cyan]")
    console.print()

    if not confirm("  Start campaign?"):
        return

    # update status
    all_camps = load_campaigns()
    for c in all_camps:
        if c["id"] == camp["id"]:
            c["status"] = "running"
            c["started_at"] = now_str()
    save_campaigns(all_camps)

    targets   = camp.get("targets", [])
    messages  = camp.get("messages", ["Hello!"])
    delay     = (camp.get("delay_min", 60), camp.get("delay_max", 120))
    daily_lim = camp.get("daily_limit", 30)
    sw_after  = camp.get("switch_after", 10)

    acc_idx  = 0
    acc_ops  = 0
    sent     = camp.get("sent", 0)
    failed_c = camp.get("failed", 0)
    skipped  = camp.get("skipped", 0)

    client = _build_client(accounts[acc_idx])
    await client.connect()

    try:
        for target in targets[sent:]:
            target = str(target).strip().strip("@")
            if not target or is_blacklisted(target):
                skipped += 1
                continue

            current = accounts[acc_idx]
            if current.get("today_messages", 0) >= daily_lim:
                acc_idx = (acc_idx + 1) % len(accounts)
                if acc_idx == 0:
                    print_warn("All accounts hit daily limit.")
                    break
                await client.disconnect()
                client = _build_client(accounts[acc_idx])
                await client.connect()
                acc_ops = 0

            if acc_ops >= sw_after and len(accounts) > 1:
                acc_idx = (acc_idx + 1) % len(accounts)
                await client.disconnect()
                client = _build_client(accounts[acc_idx])
                await client.connect()
                acc_ops = 0
                print_info(f"Rotated to {accounts[acc_idx]['phone']}")

            msg = random.choice(messages)

            try:
                entity = await client.get_entity(f"@{target}" if not target.startswith("+") else target)
                await client.send_message(entity, msg)
                console.print(f"  [dim]{now_str()[:19]}[/dim]  ✅ [green]{target}[/green]")
                sent   += 1
                acc_ops += 1
                increment_stat("campaign", "sent")
            except UserPrivacyRestrictedError:
                console.print(f"  [dim]{target} — Privacy restricted[/dim]")
                skipped += 1
            except PeerFloodError:
                print_warn("PeerFlood — switching account")
                acc_idx = (acc_idx + 1) % len(accounts)
                await client.disconnect()
                client = _build_client(accounts[acc_idx])
                await client.connect()
                acc_ops = 0
            except FloodWaitError as e:
                print_warn(f"FloodWait {e.seconds}s")
                wait_countdown(min(e.seconds, 120), "FloodWait")
            except Exception as e:
                console.print(f"  ❌ [red]{target}[/red]")
                failed_c += 1

            # save progress every 10 sends
            if sent % 10 == 0:
                all_camps = load_campaigns()
                for c in all_camps:
                    if c["id"] == camp["id"]:
                        c.update({"sent": sent, "failed": failed_c, "skipped": skipped})
                save_campaigns(all_camps)

            await asyncio.sleep(random.randint(*delay))

    except KeyboardInterrupt:
        print_warn("Campaign paused by user.")

    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

    all_camps = load_campaigns()
    for c in all_camps:
        if c["id"] == camp["id"]:
            c.update({
                "sent":    sent,
                "failed":  failed_c,
                "skipped": skipped,
                "status":  "completed" if (sent + failed_c + skipped) >= len(targets) else "paused",
            })
    save_campaigns(all_camps)

    console.print(f"\n  ─── Campaign Results ────────────────────")
    console.print(f"  ✅ Sent    : [green]{sent}[/green]")
    console.print(f"  ⚠️  Skipped : [yellow]{skipped}[/yellow]")
    console.print(f"  ❌ Failed  : [red]{failed_c}[/red]")
    input("\n  Press ENTER...")


# ─── View / Stats / Stop / Delete ────────────────────────────────────────────

def view_campaigns():
    print_header("📋  All Campaigns")
    campaigns = load_campaigns()
    if not campaigns:
        print_info("No campaigns yet.")
        input("\n  Press ENTER...")
        return

    from rich.table import Table
    from rich import box
    table = Table(box=box.SIMPLE_HEAVY, border_style="cyan")
    table.add_column("#",       width=4, justify="right")
    table.add_column("Name",    width=20, style="bold white")
    table.add_column("Targets", width=9, justify="right")
    table.add_column("Sent",    width=7, justify="right", style="green")
    table.add_column("Failed",  width=7, justify="right", style="red")
    table.add_column("Status",  width=12)
    table.add_column("Created", width=12)

    for c in campaigns:
        st = c.get("status", "pending")
        sc = "green" if st == "running" else ("dim" if st == "completed" else "yellow")
        table.add_row(
            str(c["id"]),
            c["name"][:19],
            str(len(c.get("targets", []))),
            str(c.get("sent", 0)),
            str(c.get("failed", 0)),
            f"[{sc}]{st.title()}[/{sc}]",
            c.get("created_at", "")[:10],
        )
    console.print(table)
    input("\n  Press ENTER...")


def campaign_stats():
    print_header("📊  Campaign Statistics")
    campaigns = load_campaigns()
    if not campaigns:
        print_info("No campaigns found.")
        input("\n  Press ENTER...")
        return

    total_sent    = sum(c.get("sent", 0) for c in campaigns)
    total_failed  = sum(c.get("failed", 0) for c in campaigns)
    total_skipped = sum(c.get("skipped", 0) for c in campaigns)
    total_targets = sum(len(c.get("targets", [])) for c in campaigns)

    console.print(f"  Total Campaigns : [bold]{len(campaigns)}[/bold]")
    console.print(f"  Total Targets   : [cyan]{total_targets}[/cyan]")
    console.print(f"  Total Sent      : [green]{total_sent}[/green]")
    console.print(f"  Total Failed    : [red]{total_failed}[/red]")
    console.print(f"  Total Skipped   : [yellow]{total_skipped}[/yellow]")
    if total_targets:
        pct = total_sent / total_targets * 100
        console.print(f"  Success Rate    : [bold]{pct:.1f}%[/bold]")
    input("\n  Press ENTER...")


def stop_campaign():
    campaigns = [c for c in load_campaigns() if c.get("status") == "running"]
    if not campaigns:
        print_info("No running campaigns.")
        input("\n  Press ENTER...")
        return
    for i, c in enumerate(campaigns, 1):
        console.print(f"  [{i}] #{c['id']} {c['name']}")
    sel = prompt("  Select #", "1")
    try:
        camp = campaigns[int(sel) - 1]
        all_c = load_campaigns()
        for c in all_c:
            if c["id"] == camp["id"]:
                c["status"] = "paused"
        save_campaigns(all_c)
        print_success(f"Campaign '{camp['name']}' paused.")
    except Exception:
        print_error("Invalid selection.")
    input("\n  Press ENTER...")


def delete_campaign():
    campaigns = load_campaigns()
    for i, c in enumerate(campaigns, 1):
        console.print(f"  [{i}] #{c['id']} {c['name']}  ({c.get('status','?')})")
    sel = prompt("  Select # to delete")
    try:
        camp = campaigns[int(sel) - 1]
        if confirm(f"  Delete campaign '{camp['name']}'?"):
            remaining = [c for c in campaigns if c["id"] != camp["id"]]
            save_campaigns(remaining)
            print_success("Campaign deleted.")
    except Exception:
        print_error("Invalid selection.")
    input("\n  Press ENTER...")
