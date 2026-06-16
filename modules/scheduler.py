import asyncio
import os
import sys
import signal
import subprocess
from datetime import datetime
from pathlib import Path
from modules.utils import (
    console, print_header, print_success, print_error, print_info, print_warn,
    prompt, menu_choice, confirm, now_str,
)
from modules.database import (
    load_schedules, save_schedules, add_schedule,
    remove_schedule, update_schedule,
)

_PID_FILE = Path(__file__).parent.parent / "data" / "scheduler.pid"
_LOG_FILE = Path(__file__).parent.parent / "logs"  / "scheduler.log"


# ─── Menu ─────────────────────────────────────────────────────────────────────

def scheduler_menu():
    while True:
        tasks   = load_schedules()
        pending = sum(1 for t in tasks if t.get("status") == "pending")
        done    = sum(1 for t in tasks if t.get("status") == "completed")
        running = _is_daemon_running()

        daemon_status = "[bold green]Running ✅[/bold green]" if running else "[dim]Stopped[/dim]"
        print_header("📅  Task Scheduler",
                     f"Pending: {pending}  |  Completed: {done}  |  Daemon: {daemon_status}")

        choice = menu_choice([
            ("1", "➕  Add Scheduled Task"),
            ("2", "📋  View All Tasks"),
            ("3", "✏️  Edit Task"),
            ("4", "❌  Delete Task"),
            ("5", "▶️   Run Task Now"),
            ("6", "📊  Execution History"),
            ("7", "🚀  Start Background Daemon" if not running else "⏹️  Stop Background Daemon"),
            ("8", "📄  View Daemon Log"),
        ])

        if choice == "1":   add_task()
        elif choice == "2": view_tasks()
        elif choice == "3": edit_task()
        elif choice == "4": delete_task()
        elif choice == "5": run_task_now()
        elif choice == "6": view_history()
        elif choice == "7":
            if running: stop_daemon()
            else:       start_daemon()
        elif choice == "8": view_daemon_log()
        elif choice == "0": break


# ─── 1. Add Task ──────────────────────────────────────────────────────────────

def add_task():
    print_header("➕  Add Scheduled Task")
    ops = {
        "1": "scrape",
        "2": "add_members",
        "3": "bulk_message",
        "4": "warmup",
        "5": "validate",
        "6": "reset_counters",
        "7": "backup",
    }
    console.print("  Operation Type:")
    for k, v in ops.items():
        console.print(f"  [{k}] {v}")
    op   = ops.get(prompt("  Select", "1"), "validate")
    name = prompt("  Task Name", f"{op} task")

    console.print("\n  Repeat:")
    console.print("  [1] One-time  [2] Daily  [3] Weekly")
    stype    = prompt("  Select", "2")
    run_time = prompt("  Time (HH:MM)", "09:00")

    if stype == "1":
        run_date = prompt("  Date (YYYY-MM-DD)", datetime.now().strftime("%Y-%m-%d"))
        schedule = f"{run_date} {run_time}"
    else:
        schedule = run_time

    params = {}
    if op in ("scrape", "add_members"):
        params["target"] = prompt("  Target group (optional)")

    notify = confirm("  Send notification on completion?")

    task_id = add_schedule({
        "name": name, "operation": op,
        "schedule": schedule, "stype": stype,
        "params": params, "notify": notify,
    })
    print_success(f"Task #{task_id} '{name}' scheduled.")
    if not _is_daemon_running():
        if confirm("  Start background daemon now?"):
            start_daemon()
    input("\n  Press ENTER...")


# ─── 2. View Tasks ────────────────────────────────────────────────────────────

def view_tasks():
    print_header("📋  Scheduled Tasks")
    tasks = load_schedules()
    if not tasks:
        print_info("No scheduled tasks.")
        input("\n  Press ENTER...")
        return
    stype_map = {"1":"Once","2":"Daily","3":"Weekly"}
    for t in tasks:
        st  = t.get("status","pending")
        sc  = "green" if st=="running" else ("dim" if st=="completed" else "yellow")
        console.print(
            f"  [dim]#{t['id']}[/dim]  [{sc}]{st.upper():<10}[/{sc}]  "
            f"[bold]{t['name']:<25}[/bold]  "
            f"[cyan]{t['operation']:<15}[/cyan]  "
            f"[dim]{stype_map.get(t.get('stype','2'),'?')} @ "
            f"{t.get('schedule','?')}  runs:{t.get('run_count',0)}[/dim]"
        )
    input("\n  Press ENTER...")


# ─── 3. Edit Task ─────────────────────────────────────────────────────────────

def edit_task():
    print_header("✏️  Edit Scheduled Task")
    tasks = load_schedules()
    if not tasks:
        print_info("No tasks.")
        input("\n  Press ENTER...")
        return
    for t in tasks:
        console.print(f"  [{t['id']}] {t['name']} — {t['operation']} @ {t.get('schedule','?')}")
    tid = prompt("  Task # to edit")
    if not tid.isdigit():
        return
    task = next((t for t in tasks if t["id"] == int(tid)), None)
    if not task:
        print_error("Not found.")
        input("\n  Press ENTER...")
        return
    new_name  = prompt("  New name (ENTER = keep)", task["name"])
    new_sched = prompt("  New schedule HH:MM or YYYY-MM-DD HH:MM (ENTER = keep)",
                       task.get("schedule",""))
    update_schedule(int(tid), {
        "name":     new_name  or task["name"],
        "schedule": new_sched or task.get("schedule",""),
    })
    print_success("Task updated.")
    input("\n  Press ENTER...")


# ─── 4. Delete Task ───────────────────────────────────────────────────────────

def delete_task():
    print_header("❌  Delete Scheduled Task")
    tasks = load_schedules()
    if not tasks:
        print_info("No tasks.")
        input("\n  Press ENTER...")
        return
    for t in tasks:
        console.print(f"  [{t['id']}] {t['name']}")
    tid = prompt("  Task # to delete")
    if not tid.isdigit():
        return
    if confirm(f"  Delete task #{tid}?"):
        remove_schedule(int(tid))
        print_success("Deleted.")
    input("\n  Press ENTER...")


# ─── 5. Run Now ───────────────────────────────────────────────────────────────

def run_task_now():
    print_header("▶️   Run Task Now")
    tasks = [t for t in load_schedules() if t.get("status") != "running"]
    if not tasks:
        print_info("No tasks available.")
        input("\n  Press ENTER...")
        return
    for t in tasks:
        console.print(f"  [{t['id']}] {t['name']} — {t['operation']}")
    tid = prompt("  Task #")
    if not tid.isdigit():
        return
    task = next((t for t in tasks if t["id"] == int(tid)), None)
    if not task:
        print_error("Not found.")
        input("\n  Press ENTER...")
        return
    print_info(f"Executing: {task['name']} ({task['operation']})...")
    _execute_task(task)
    update_schedule(task["id"], {
        "last_run": now_str(),
        "run_count": task.get("run_count",0)+1,
    })
    if task.get("notify"):
        try:
            from modules.notifications import send_alert
            send_alert("scheduler", f"Task '{task['name']}' completed.", "success")
        except Exception:
            pass
    print_success("Task executed.")
    input("\n  Press ENTER...")


# ─── 6. History ───────────────────────────────────────────────────────────────

def view_history():
    print_header("📊  Execution History")
    tasks = sorted(
        [t for t in load_schedules() if t.get("last_run")],
        key=lambda t: t.get("last_run",""), reverse=True,
    )
    if not tasks:
        print_info("No executed tasks yet.")
        input("\n  Press ENTER...")
        return
    for t in tasks:
        console.print(
            f"  [cyan]{str(t.get('last_run',''))[:16]}[/cyan]  "
            f"[bold]{t['name']:<25}[/bold]  "
            f"[dim]{t['operation']}  runs:{t.get('run_count',0)}[/dim]"
        )
    input("\n  Press ENTER...")


# ─── 7. Daemon management ─────────────────────────────────────────────────────

def _is_daemon_running() -> bool:
    if not _PID_FILE.exists():
        return False
    try:
        pid = int(_PID_FILE.read_text().strip())
        os.kill(pid, 0)   # signal 0 = just check existence
        return True
    except (ProcessLookupError, ValueError, PermissionError):
        _PID_FILE.unlink(missing_ok=True)
        return False


def start_daemon():
    print_header("🚀  Start Background Daemon")
    if _is_daemon_running():
        pid = _PID_FILE.read_text().strip()
        print_warn(f"Daemon already running (PID {pid}).")
        input("\n  Press ENTER...")
        return

    _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Build inline Python that imports and runs the daemon loop
    daemon_script = (
        "import sys, os; "
        f"sys.path.insert(0, {str(Path(__file__).parent.parent)!r}); "
        "from modules.scheduler import _daemon_loop; "
        "import asyncio; asyncio.run(_daemon_loop())"
    )

    log_fd  = open(_LOG_FILE, "a")
    proc    = subprocess.Popen(
        [sys.executable, "-c", daemon_script],
        stdout=log_fd, stderr=log_fd,
        stdin=subprocess.DEVNULL,
        start_new_session=True,       # detach from terminal
    )
    _PID_FILE.write_text(str(proc.pid))
    print_success(f"Daemon started in background (PID {proc.pid}).")
    print_info(f"Log: {_LOG_FILE}")
    input("\n  Press ENTER...")


def stop_daemon():
    print_header("⏹️  Stop Background Daemon")
    if not _is_daemon_running():
        print_warn("Daemon is not running.")
        _PID_FILE.unlink(missing_ok=True)
        input("\n  Press ENTER...")
        return
    try:
        pid = int(_PID_FILE.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        _PID_FILE.unlink(missing_ok=True)
        print_success(f"Daemon stopped (PID {pid}).")
    except Exception as e:
        print_error(f"Could not stop daemon: {e}")
    input("\n  Press ENTER...")


def view_daemon_log():
    print_header("📄  Daemon Log (last 30 lines)")
    if not _LOG_FILE.exists():
        print_info("No log yet.")
        input("\n  Press ENTER...")
        return
    lines = _LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines[-30:]:
        console.print(f"  [dim]{line}[/dim]")
    input("\n  Press ENTER...")


# ─── Task Executor ────────────────────────────────────────────────────────────

def _execute_task(task: dict):
    op = task.get("operation","")
    try:
        if op == "validate":
            from modules.account_manager import validate_accounts
            asyncio.run(validate_accounts())

        elif op == "reset_counters":
            from modules.database import reset_daily_counters
            reset_daily_counters()
            print_success("Daily counters reset.")

        elif op == "warmup":
            from modules.account_manager import account_warmup
            asyncio.run(account_warmup())

        elif op == "backup":
            from modules.backup import _do_backup
            _do_backup()

        elif op in ("scrape", "add_members", "bulk_message"):
            # These need interactive terminal — log a note when running headless
            _daemon_log(f"Task '{task['name']}' ({op}) requires interactive mode. Skipped in daemon.")

        else:
            _daemon_log(f"Unknown operation: {op}")

    except Exception as e:
        _daemon_log(f"Task '{task.get('name','?')}' error: {e}")
        raise


def _daemon_log(msg: str):
    _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")


# ─── Daemon Loop (runs in subprocess) ────────────────────────────────────────

async def _daemon_loop():
    _daemon_log("Scheduler daemon started.")
    try:
        while True:
            tasks = load_schedules()
            now   = datetime.now()
            for task in tasks:
                if task.get("status") == "running":
                    continue
                stype    = task.get("stype","2")
                schedule = task.get("schedule","")
                should_run = False
                try:
                    if stype == "1":
                        run_dt = datetime.strptime(schedule, "%Y-%m-%d %H:%M")
                        if now >= run_dt and task.get("run_count",0) == 0:
                            should_run = True
                    elif stype in ("2","3"):
                        run_time = datetime.strptime(schedule, "%H:%M").time()
                        if now.hour == run_time.hour and now.minute == run_time.minute:
                            last = task.get("last_run")
                            if not last:
                                should_run = True
                            else:
                                last_dt = datetime.strptime(str(last)[:16], "%Y-%m-%d %H:%M")
                                diff    = now - last_dt
                                if stype == "2" and diff.total_seconds() > 3600:
                                    should_run = True
                                elif stype == "3" and diff.days >= 7:
                                    should_run = True
                except ValueError:
                    pass

                if should_run:
                    _daemon_log(f"Running: {task['name']} ({task['operation']})")
                    update_schedule(task["id"], {"status":"running","last_run":now_str()})
                    try:
                        _execute_task(task)
                        update_schedule(task["id"], {
                            "status":    "pending" if stype in ("2","3") else "completed",
                            "run_count": task.get("run_count",0)+1,
                        })
                        _daemon_log(f"Done: {task['name']}")
                        if task.get("notify"):
                            try:
                                from modules.notifications import send_alert
                                send_alert("scheduler", f"Task '{task['name']}' completed.", "success")
                            except Exception:
                                pass
                    except Exception as e:
                        update_schedule(task["id"], {"status":"pending"})
                        _daemon_log(f"Failed: {task['name']} — {e}")

            await asyncio.sleep(30)
    except Exception as e:
        _daemon_log(f"Daemon crashed: {e}")
