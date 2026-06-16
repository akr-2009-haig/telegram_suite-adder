import zipfile
from pathlib import Path
from datetime import datetime
from modules.utils import (
    console, print_header, print_success, print_error, print_info, print_warn,
    prompt, menu_choice, confirm, now_str,
)
import config

BACKUP_DIR = Path("backups")


def backup_menu():
    while True:
        BACKUP_DIR.mkdir(exist_ok=True)
        backups = sorted(BACKUP_DIR.glob("backup_*.zip"), reverse=True)
        print_header("📦  Cloud Backup & Restore", f"Available Backups: {len(backups)}")
        if backups:
            console.print(f"  Latest: [dim]{backups[0].name}[/dim]\n")

        choice = menu_choice([
            ("1", "📤  Create Backup Now"),
            ("2", "📥  Restore from Backup"),
            ("3", "📋  View Available Backups"),
            ("4", "☁️   Upload to Telegram (Saved Messages)"),
            ("5", "⬇️   Download from Telegram"),
            ("6", "⚙️  Auto-Backup Settings"),
            ("7", "🗑️  Delete Old Backups"),
        ])

        if choice == "1":   create_backup()
        elif choice == "2": restore_backup()
        elif choice == "3": list_backups()
        elif choice == "4": upload_to_telegram()
        elif choice == "5": download_from_telegram()
        elif choice == "6": auto_backup_settings()
        elif choice == "7": delete_old_backups()
        elif choice == "0": break


def create_backup(silent: bool = False) -> Path | None:
    if not silent:
        print_header("📤  Create Backup")
    BACKUP_DIR.mkdir(exist_ok=True)
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = BACKUP_DIR / f"backup_{ts}.zip"
    cfg      = config.load_settings()
    bcfg     = cfg.get("backup_include", {"sessions":True,"data":True,"exports":False,"logs":False})
    if not silent:
        console.print("  Select what to include:\n")
        bcfg["sessions"] = confirm("  ✅ Session files?",       default=bcfg.get("sessions",True))
        bcfg["data"]     = confirm("  ✅ Data & settings JSON?", default=bcfg.get("data",True))
        bcfg["exports"]  = confirm("  ✅ Exported member lists?",default=bcfg.get("exports",False))
        bcfg["logs"]     = confirm("  ✅ Log files?",            default=bcfg.get("logs",False))
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            if bcfg.get("sessions") and config.SESSIONS_DIR.exists():
                for f in config.SESSIONS_DIR.glob("*.session"):
                    zf.write(f, f"sessions/{f.name}")
            if bcfg.get("data") and config.DATA_DIR.exists():
                for f in config.DATA_DIR.glob("*.json"):
                    zf.write(f, f"data/{f.name}")
            if bcfg.get("exports"):
                exp = Path("exports")
                if exp.exists():
                    for f in exp.iterdir():
                        if f.is_file(): zf.write(f, f"exports/{f.name}")
            if bcfg.get("logs"):
                logs = Path("logs")
                if logs.exists():
                    for f in logs.glob("*.log"): zf.write(f, f"logs/{f.name}")
        size_kb = zip_path.stat().st_size // 1024
        if not silent:
            print_success(f"Backup: {zip_path.name}  ({size_kb} KB)")
            input("\n  Press ENTER...")
        return zip_path
    except Exception as e:
        print_error(f"Backup failed: {e}")
        if not silent: input("\n  Press ENTER...")
        return None


def restore_backup():
    print_header("📥  Restore from Backup")
    BACKUP_DIR.mkdir(exist_ok=True)
    backups = sorted(BACKUP_DIR.glob("backup_*.zip"), reverse=True)
    if not backups:
        print_error("No backups found.")
        input("\n  Press ENTER...")
        return
    for i, b in enumerate(backups, 1):
        size_kb = b.stat().st_size // 1024
        ts = b.stem.replace("backup_","").replace("_"," ")
        console.print(f"  [{i}] {b.name}  ({size_kb} KB)  [dim]{ts}[/dim]")
    ch = prompt("\n  Select backup #")
    if not ch.isdigit():
        return
    idx = int(ch) - 1
    if idx < 0 or idx >= len(backups):
        print_error("Invalid selection.")
        input("\n  Press ENTER...")
        return
    zip_path = backups[idx]
    print_warn(f"This overwrites current sessions/data with {zip_path.name}")
    if not confirm("  Continue?"):
        return
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            namelist = zf.namelist()
            for n in namelist:
                if n.startswith("sessions/"):
                    config.SESSIONS_DIR.mkdir(exist_ok=True)
                    zf.extract(n, ".")
            for n in namelist:
                if n.startswith("data/"):
                    config.DATA_DIR.mkdir(exist_ok=True)
                    zf.extract(n, ".")
        print_success(f"Restored from {zip_path.name}")
    except Exception as e:
        print_error(f"Restore failed: {e}")
    input("\n  Press ENTER...")


def list_backups():
    print_header("📋  Available Backups")
    BACKUP_DIR.mkdir(exist_ok=True)
    backups = sorted(BACKUP_DIR.glob("backup_*.zip"), reverse=True)
    if not backups:
        print_info("No backups found.")
        input("\n  Press ENTER...")
        return
    total = 0
    for i, b in enumerate(backups, 1):
        size_kb = b.stat().st_size // 1024
        total += size_kb
        ts = b.stem.replace("backup_","").replace("_"," ")
        console.print(f"  [{i}]  {b.name:<40}  [cyan]{size_kb:>6} KB[/cyan]  [dim]{ts}[/dim]")
    console.print(f"\n  Total: [bold]{len(backups)}[/bold] backups  |  [cyan]{total} KB[/cyan]")
    input("\n  Press ENTER...")


def upload_to_telegram():
    import asyncio
    print_header("☁️   Upload Backup to Telegram")
    BACKUP_DIR.mkdir(exist_ok=True)
    backups = sorted(BACKUP_DIR.glob("backup_*.zip"), reverse=True)
    if not backups:
        print_warn("No backup found — creating one first...")
        zip_path = create_backup(silent=True)
        if not zip_path:
            return
    else:
        zip_path = backups[0]
        console.print(f"  Using: [bold]{zip_path.name}[/bold]")
    asyncio.run(_upload_file(zip_path))


async def _upload_file(zip_path: Path):
    from modules.database import get_active_accounts
    accounts = get_active_accounts()
    if not accounts:
        print_error("No active accounts for upload.")
        input("\n  Press ENTER...")
        return
    api_id, api_hash = config.get_api_credentials()
    acc     = accounts[0]
    session = str(config.SESSIONS_DIR / acc["phone"])
    try:
        from telethon import TelegramClient
        async with TelegramClient(session, int(api_id), api_hash) as client:
            print_info(f"Uploading via {acc['phone']}...")
            await client.send_file("me", zip_path,
                caption=f"📦 Telegram Suite Backup\n{now_str()}\nBy: Akram Haig | +967772009303")
            print_success(f"Uploaded to Saved Messages: {zip_path.name}")
    except Exception as e:
        print_error(f"Upload failed: {e}")
    input("\n  Press ENTER...")


def download_from_telegram():
    import asyncio
    print_header("⬇️   Download Backup from Telegram")
    asyncio.run(_download_backup())


async def _download_backup():
    from modules.database import get_active_accounts
    accounts = get_active_accounts()
    if not accounts:
        print_error("No active accounts.")
        input("\n  Press ENTER...")
        return
    api_id, api_hash = config.get_api_credentials()
    acc     = accounts[0]
    session = str(config.SESSIONS_DIR / acc["phone"])
    try:
        from telethon import TelegramClient
        async with TelegramClient(session, int(api_id), api_hash) as client:
            found = []
            async for msg in client.iter_messages("me", limit=50):
                if msg.document:
                    fname = ""
                    for attr in (msg.document.attributes or []):
                        fname = getattr(attr, "file_name", "") or ""
                        if fname: break
                    if fname.startswith("backup_") and fname.endswith(".zip"):
                        found.append((msg, fname))
            if not found:
                print_warn("No backup files found in Saved Messages.")
                input("\n  Press ENTER...")
                return
            for i, (_, fname) in enumerate(found, 1):
                console.print(f"  [{i}] {fname}")
            ch = prompt("\n  Select backup #")
            if not ch.isdigit():
                return
            idx = int(ch) - 1
            if idx < 0 or idx >= len(found):
                print_error("Invalid.")
                input("\n  Press ENTER...")
                return
            msg, fname = found[idx]
            BACKUP_DIR.mkdir(exist_ok=True)
            out = BACKUP_DIR / fname
            print_info(f"Downloading {fname}...")
            await client.download_media(msg, file=out)
            print_success(f"Saved to {out}")
    except Exception as e:
        print_error(f"Download failed: {e}")
    input("\n  Press ENTER...")


def auto_backup_settings():
    print_header("⚙️  Auto-Backup Settings")
    cfg = config.load_settings()
    console.print("  Backup frequency:")
    console.print("  [1] Daily  [2] Weekly  [3] Monthly  [4] Disabled")
    freq_map = {"1":"daily","2":"weekly","3":"monthly","4":"disabled"}
    cfg["auto_backup_freq"]   = freq_map.get(prompt("  Select","1"),"daily")
    cfg["auto_backup_upload"] = confirm("  Auto-upload to Telegram Saved Messages?")
    config.save_settings(cfg)
    print_success("Settings saved.")
    input("\n  Press ENTER...")


def delete_old_backups():
    print_header("🗑️  Delete Old Backups")
    BACKUP_DIR.mkdir(exist_ok=True)
    backups = sorted(BACKUP_DIR.glob("backup_*.zip"), reverse=True)
    if len(backups) <= 1:
        print_info("Only 1 backup or less — nothing to delete.")
        input("\n  Press ENTER...")
        return
    keep = int(prompt("  Keep last N backups","3") or 3)
    to_del = backups[keep:]
    if not to_del:
        print_info("Nothing to delete.")
        input("\n  Press ENTER...")
        return
    for b in to_del:
        console.print(f"  [red]✗[/red] {b.name}")
    if confirm(f"\n  Delete {len(to_del)} backup(s)?"):
        for b in to_del:
            b.unlink()
        print_success(f"Deleted {len(to_del)} backup(s).")
    input("\n  Press ENTER...")


def run_auto_backup():
    """Called from scheduler / startup for automated backups."""
    cfg  = config.load_settings()
    freq = cfg.get("auto_backup_freq","disabled")
    if freq == "disabled":
        return
    zip_path = create_backup(silent=True)
    if zip_path and cfg.get("auto_backup_upload"):
        import asyncio
        try:
            asyncio.run(_upload_file(zip_path))
        except Exception:
            pass
