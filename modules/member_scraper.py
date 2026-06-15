import asyncio
import csv
import os
import random
from pathlib import Path
from datetime import datetime, timedelta
from telethon import TelegramClient
from telethon.tl.types import (
    ChannelParticipantsSearch, UserStatusOnline, UserStatusRecently,
    UserStatusOffline, InputPeerChannel,
)
from telethon.errors import FloodWaitError, ChatAdminRequiredError
from rich.table import Table
from rich import box

import config
from modules.utils import (
    console, print_header, print_success, print_error, print_warn,
    print_info, prompt, menu_choice, confirm, progress_bar,
    now_str, date_str, wait_countdown,
)
from modules.database import (
    load_accounts, get_active_accounts, increment_account_counter,
    load_proxies, increment_stat,
)

EXPORTS_DIR = config.EXPORTS_DIR


def member_scraper_menu():
    while True:
        print_header("📥  Member Scraper", "Extract members from groups and channels")
        choice = menu_choice([
            ("1", "🌐  Scrape from Public Group / Channel"),
            ("2", "🔗  Scrape from Private Invite Link"),
            ("3", "💬  Scrape Chat Participants (by messages)"),
            ("4", "👁️  Scrape Visible Group Members"),
            ("5", "📊  Bulk Scrape Multiple Groups"),
            ("6", "📂  View Exported Files"),
            ("7", "🔀  Merge Files + Remove Duplicates"),
        ])
        if choice == "1":
            asyncio.run(scrape_public_group())
        elif choice == "2":
            asyncio.run(scrape_private_group())
        elif choice == "3":
            asyncio.run(scrape_by_messages())
        elif choice == "4":
            asyncio.run(scrape_visible_members())
        elif choice == "5":
            asyncio.run(bulk_scrape())
        elif choice == "6":
            view_exported_files()
        elif choice == "7":
            merge_files()
        elif choice == "0":
            break


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _build_client(account: dict) -> TelegramClient:
    api_id, api_hash = config.get_api_credentials()
    session = str(config.SESSIONS_DIR / account["phone"])
    proxy = None
    if account.get("proxy_id"):
        from modules.database import load_proxies
        for p in load_proxies():
            if p["id"] == account["proxy_id"]:
                ptype = p.get("type", "socks5").lower()
                import socks
                pt = socks.SOCKS5 if "socks5" in ptype else (socks.SOCKS4 if "socks4" in ptype else socks.HTTP)
                proxy = (pt, p["host"], int(p["port"]),
                         True, p.get("username") or None, p.get("password") or None)
                break
    return TelegramClient(session, int(api_id), api_hash, proxy=proxy)


def _collection_filters() -> dict:
    console.print("\n  ─── Collection Filters ───────────────────")
    filters = {}
    filters["exclude_bots"]      = confirm("  Exclude bots?")
    filters["exclude_deleted"]   = confirm("  Exclude deleted accounts?")
    filters["exclude_no_username"]= confirm("  Exclude accounts without username?")
    filters["photos_only"]       = confirm("  Only accounts with profile photos?")
    console.print()
    return filters


def _collection_type() -> dict:
    console.print("\n  ─── Collection Type ──────────────────────")
    console.print("  [1] All Members")
    console.print("  [2] Active Members Only (sent messages)")
    console.print("  [3] Currently Online Only")
    console.print("  [4] Active Within a Specific Time Range")
    ct = prompt("  Select", "1")
    params = {"type": ct}
    if ct == "4":
        console.print("  [1] Last 24h  [2] Last 3 Days  [3] Last Week  [4] Last Month  [5] Custom")
        tr = prompt("  Range", "3")
        ranges = {"1": 1, "2": 3, "3": 7, "4": 30}
        params["days"] = ranges.get(tr, 7)
    return params


def _collection_limit() -> int:
    console.print("\n  ─── Collection Limit ─────────────────────")
    console.print("  [1] All Members   [2] First 1000   [3] Custom Amount")
    lc = prompt("  Select", "1")
    if lc == "2":
        return 1000
    elif lc == "3":
        return int(prompt("  Amount", "500") or 500)
    return 0  # 0 = all


def _select_accounts() -> list[dict]:
    console.print("\n  ─── Account Selection ────────────────────")
    console.print("  [1] Single Account (manual)")
    console.print("  [2] Rotate Between Multiple Accounts  ⭐")
    mode = prompt("  Select", "2")
    active = get_active_accounts()
    if not active:
        print_error("No active accounts available.")
        return []
    if mode == "1":
        for i, a in enumerate(active, 1):
            console.print(f"    [{i}] {a['phone']}  ({a.get('name','N/A')})")
        idx = int(prompt("  Choose Account #", "1") or 1) - 1
        return [active[idx]] if 0 <= idx < len(active) else [active[0]]
    return active


def _apply_filters(user, filters: dict) -> bool:
    if filters.get("exclude_bots") and user.bot:
        return False
    if filters.get("exclude_deleted") and user.deleted:
        return False
    if filters.get("exclude_no_username") and not user.username:
        return False
    if filters.get("photos_only") and not user.photo:
        return False
    return True


def _save_members(members: list[dict], filename: str) -> Path:
    out_path = EXPORTS_DIR / filename
    if not members:
        return out_path
    fieldnames = ["user_id", "first_name", "last_name", "username", "phone", "last_seen"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(members)
    return out_path


# ─── Public Group Scraper ────────────────────────────────────────────────────

async def scrape_public_group():
    print_header("🌐  Scrape Public Group / Channel")
    link = prompt("🔗 Enter Group Link or @username")
    if not link:
        return

    accounts = _select_accounts()
    if not accounts:
        input("\n  Press ENTER...")
        return

    ctype   = _collection_type()
    filters = _collection_filters()
    limit   = _collection_limit()

    client = _build_client(accounts[0])
    acc_idx = 0

    try:
        await client.connect()
        entity = await client.get_entity(link.strip())
        name = getattr(entity, "title", link)
        count = getattr(entity, "participants_count", "?")

        console.print(f"\n  📌 [bold]{name}[/bold]  |  Members: [cyan]{count}[/cyan]")

        members_data = []
        skipped = 0
        collected = 0
        acc_ops = 0
        switch_after = 50

        console.print(f"\n  🔄 Starting collection...\n")

        kwargs = {"aggressive": True}
        if limit:
            kwargs["limit"] = limit

        async for user in client.iter_participants(entity, **kwargs):
            if limit and collected >= limit:
                break

            # rotate account
            if acc_ops >= switch_after and len(accounts) > 1:
                await client.disconnect()
                acc_idx = (acc_idx + 1) % len(accounts)
                client = _build_client(accounts[acc_idx])
                await client.connect()
                acc_ops = 0
                print_info(f"Rotated to account {accounts[acc_idx]['phone']}")

            if not _apply_filters(user, filters):
                skipped += 1
                continue

            last_seen = ""
            if hasattr(user, "status") and user.status:
                if isinstance(user.status, UserStatusOnline):
                    last_seen = "Online"
                elif isinstance(user.status, UserStatusRecently):
                    last_seen = "Recently"
                elif isinstance(user.status, UserStatusOffline):
                    last_seen = user.status.was_online.strftime("%Y-%m-%d") if user.status.was_online else ""

            members_data.append({
                "user_id":    user.id,
                "first_name": user.first_name or "",
                "last_name":  user.last_name or "",
                "username":   user.username or "",
                "phone":      user.phone or "",
                "last_seen":  last_seen,
            })
            collected += 1
            acc_ops += 1

            if collected % 100 == 0:
                console.print(f"  📊 Collected: [bold green]{collected}[/bold green]  |  Skipped: [dim]{skipped}[/dim]  |  Account: [cyan]{accounts[acc_idx]['phone']}[/cyan]", end="\r")

            await asyncio.sleep(random.uniform(0.05, 0.2))

        await client.disconnect()

        safe_name = name.replace(" ", "_").replace("/", "_")[:30]
        filename = f"{safe_name}_{date_str()}.csv"
        out_path = _save_members(members_data, filename)

        increment_stat("collection", "total_collected", collected)

        console.print(f"\n\n  🎉 [bold green]Collection Completed![/bold green]")
        console.print(f"  Total Collected : [bold]{collected}[/bold]")
        console.print(f"  Skipped         : [dim]{skipped}[/dim]")
        console.print(f"  Saved to        : [cyan]{out_path}[/cyan]")

        choice = menu_choice([
            ("1", "📂  Open Exports Folder"),
            ("2", "📤  Go to Member Adder"),
            ("3", "🔀  Merge with Another File"),
        ])
        if choice == "2":
            from modules.member_adder import member_adder_menu
            member_adder_menu()

    except FloodWaitError as e:
        print_warn(f"FloodWait detected — wait {e.seconds} seconds.")
    except Exception as e:
        print_error(f"Error: {e}")
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

    input("\n  Press ENTER to continue...")


# ─── Private Group ───────────────────────────────────────────────────────────

async def scrape_private_group():
    print_header("🔗  Scrape from Private Invite Link")
    link = prompt("🔗 Enter Invite Link (https://t.me/+AbCdEf)")
    if not link:
        return

    accounts = _select_accounts()
    if not accounts:
        input("\n  Press ENTER...")
        return

    client = _build_client(accounts[0])
    try:
        await client.connect()
        print_info(f"Joining with {accounts[0]['phone']}...")
        try:
            await client(
                __import__("telethon.tl.functions.messages", fromlist=["ImportChatInviteRequest"]).ImportChatInviteRequest(
                    link.split("+")[-1].split("/")[-1]
                )
            )
            print_success("Joined group successfully.")
        except Exception as e:
            if "already" in str(e).lower():
                print_info("Already a member of this group.")
            else:
                print_warn(f"Join attempt: {e}")

        entity = await client.get_entity(link)
        await client.disconnect()

        print_info("Proceeding to collection options...")
        await asyncio.sleep(1)
        await scrape_public_group()

    except Exception as e:
        print_error(f"Error: {e}")
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass
    input("\n  Press ENTER...")


# ─── Scrape by Messages ──────────────────────────────────────────────────────

async def scrape_by_messages():
    print_header("💬  Scrape Chat Participants (via Messages)")
    link = prompt("🔗 Enter Group Link")
    if not link:
        return

    console.print("\n  Message Scan Range:")
    console.print("  [1] Last 100   [2] Last 500   [3] Last 1000")
    console.print("  [4] Last 5000  [5] All         [6] Date Range")
    sc = prompt("  Select", "3")
    limits_map = {"1": 100, "2": 500, "3": 1000, "4": 5000, "5": 0}
    scan_limit = limits_map.get(sc, 1000)

    accounts = _select_accounts()
    if not accounts:
        input("\n  Press ENTER...")
        return

    client = _build_client(accounts[0])
    try:
        await client.connect()
        entity = await client.get_entity(link.strip())

        seen_ids = set()
        members_data = []

        console.print(f"\n  📥 Scanning messages...\n")
        async for msg in client.iter_messages(entity, limit=scan_limit or None):
            if msg.sender_id and msg.sender_id not in seen_ids:
                seen_ids.add(msg.sender_id)
                try:
                    user = await client.get_entity(msg.sender_id)
                    members_data.append({
                        "user_id":    user.id,
                        "first_name": getattr(user, "first_name", "") or "",
                        "last_name":  getattr(user, "last_name", "") or "",
                        "username":   getattr(user, "username", "") or "",
                        "phone":      getattr(user, "phone", "") or "",
                        "last_seen":  "",
                    })
                except Exception:
                    pass
                if len(members_data) % 50 == 0:
                    console.print(f"  Unique senders found: [bold]{len(members_data)}[/bold]", end="\r")
                await asyncio.sleep(0.1)

        await client.disconnect()

        filename = f"messages_{date_str()}.csv"
        out_path = _save_members(members_data, filename)
        print_success(f"Collected {len(members_data)} unique senders → {out_path}")

    except Exception as e:
        print_error(f"Error: {e}")
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass
    input("\n  Press ENTER...")


# ─── Scrape Visible Members ──────────────────────────────────────────────────

async def scrape_visible_members():
    print_header("👁️  Scrape Visible Group Members")
    link = prompt("🔗 Group Link")
    if not link:
        return
    accounts = _select_accounts()
    if not accounts:
        input("\n  Press ENTER...")
        return
    await _do_scrape(link, accounts)


async def _do_scrape(link: str, accounts: list):
    client = _build_client(accounts[0])
    try:
        await client.connect()
        entity = await client.get_entity(link.strip())
        members_data = []
        async for user in client.iter_participants(entity):
            members_data.append({
                "user_id":    user.id,
                "first_name": user.first_name or "",
                "last_name":  user.last_name or "",
                "username":   user.username or "",
                "phone":      user.phone or "",
                "last_seen":  "",
            })
        await client.disconnect()
        filename = f"visible_{date_str()}.csv"
        out_path = _save_members(members_data, filename)
        print_success(f"Collected {len(members_data)} members → {out_path}")
    except Exception as e:
        print_error(f"Error: {e}")
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass
    input("\n  Press ENTER...")


# ─── Bulk Scrape ─────────────────────────────────────────────────────────────

async def bulk_scrape():
    print_header("📊  Bulk Scrape Multiple Groups")

    console.print("  How to enter groups?")
    console.print("  [1] Manual Entry (type links)")
    console.print("  [2] Import from links.txt")
    mode = prompt("  Select", "1")

    links = []
    if mode == "1":
        console.print("\n  Enter links (one per line, type 'done' to finish):\n")
        i = 1
        while True:
            link = prompt(f"  {i}")
            if link.lower() in ("done", ""):
                break
            links.append(link)
            i += 1
    else:
        txt_path = prompt("  Path to links.txt", "links.txt")
        try:
            with open(txt_path, "r") as f:
                links = [l.strip() for l in f if l.strip()]
        except FileNotFoundError:
            print_error("File not found.")
            input("\n  Press ENTER...")
            return

    if not links:
        print_error("No links entered.")
        input("\n  Press ENTER...")
        return

    console.print(f"\n  [bold]{len(links)}[/bold] groups queued.")
    merge = confirm("  Merge all results into one file?")
    dedup = confirm("  Remove duplicates across groups?")

    accounts = _select_accounts()
    if not accounts:
        input("\n  Press ENTER...")
        return

    all_members: list[dict] = []
    seen_ids: set = set()

    for idx, link in enumerate(links, 1):
        console.print(f"\n  ── Group [{idx}/{len(links)}]: {link} ──")
        client = _build_client(accounts[idx % len(accounts)])
        try:
            await client.connect()
            entity = await client.get_entity(link.strip())
            name = getattr(entity, "title", link)
            group_members = []
            async for user in client.iter_participants(entity, aggressive=True):
                if dedup and user.id in seen_ids:
                    continue
                seen_ids.add(user.id)
                group_members.append({
                    "user_id":    user.id,
                    "first_name": user.first_name or "",
                    "last_name":  user.last_name or "",
                    "username":   user.username or "",
                    "phone":      user.phone or "",
                    "last_seen":  "",
                })
            await client.disconnect()

            if not merge:
                safe = name.replace(" ", "_")[:20]
                _save_members(group_members, f"{safe}_{date_str()}.csv")
                print_success(f"{name}: {len(group_members)} members saved.")
            else:
                all_members.extend(group_members)
                print_success(f"{name}: {len(group_members)} collected. Total: {len(all_members)}")

        except Exception as e:
            print_error(f"{link}: {e}")
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

    if merge and all_members:
        out = _save_members(all_members, f"bulk_merged_{date_str()}.csv")
        print_success(f"Merged file saved: {out}  ({len(all_members)} members)")

    input("\n  Press ENTER to continue...")


# ─── View / Merge Files ──────────────────────────────────────────────────────

def view_exported_files():
    print_header("📂  Exported Files")
    files = list(EXPORTS_DIR.glob("*.csv"))
    if not files:
        print_info("No exported files found.")
        input("\n  Press ENTER...")
        return

    table = Table(box=box.SIMPLE_HEAVY, border_style="cyan")
    table.add_column("#",       style="dim", width=4)
    table.add_column("File",    style="bold white", width=35)
    table.add_column("Members", style="cyan", width=10, justify="right")
    table.add_column("Date",    style="dim",  width=12)

    for i, f in enumerate(files, 1):
        with open(f, "r") as fp:
            lines = sum(1 for _ in fp) - 1
        mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d")
        table.add_row(str(i), f.name, str(lines), mtime)

    console.print(table)
    input("\n  Press ENTER...")


def merge_files():
    print_header("🔀  Merge Files + Remove Duplicates")
    files = list(EXPORTS_DIR.glob("*.csv"))
    if not files:
        print_error("No exported files to merge.")
        input("\n  Press ENTER...")
        return

    for i, f in enumerate(files, 1):
        console.print(f"  [{i}] {f.name}")

    sel = prompt("\n  Enter file numbers to merge (comma-separated, or 'all')", "all")
    if sel.strip().lower() == "all":
        selected = files
    else:
        indices = [int(x.strip()) - 1 for x in sel.split(",") if x.strip().isdigit()]
        selected = [files[i] for i in indices if 0 <= i < len(files)]

    if not selected:
        print_error("No valid files selected.")
        input("\n  Press ENTER...")
        return

    all_rows: list[dict] = []
    seen_ids: set = set()

    for f in selected:
        with open(f, "r", encoding="utf-8") as fp:
            reader = csv.DictReader(fp)
            for row in reader:
                uid = row.get("user_id", "")
                if uid not in seen_ids:
                    seen_ids.add(uid)
                    all_rows.append(row)

    output_name = f"merged_{date_str()}.csv"
    out_path = _save_members(all_rows, output_name)
    print_success(f"Merged {len(all_rows)} unique members → {out_path}")
    input("\n  Press ENTER...")
