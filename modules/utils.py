import os
import sys
import time
import json
import asyncio
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn
from rich.text import Text
from rich import box
from rich.align import Align

console = Console()

BANNER = """
╔══════════════════════════════════════════════════════════════╗
║          Telegram Automation Suite  v1.0                     ║
║                  Termux Edition — CLI                        ║
╚══════════════════════════════════════════════════════════════╝"""

COLORS = {
    "success": "bold green",
    "error":   "bold red",
    "warn":    "bold yellow",
    "info":    "bold cyan",
    "dim":     "dim white",
    "title":   "bold white",
    "accent":  "bold blue",
}


def clear():
    os.system("clear" if os.name != "nt" else "cls")


def print_banner():
    clear()
    console.print(BANNER, style="bold cyan")


def print_header(title: str, subtitle: str = ""):
    console.print()
    console.print(Panel(
        f"[bold white]{title}[/bold white]" + (f"\n[dim]{subtitle}[/dim]" if subtitle else ""),
        border_style="cyan",
        expand=False,
        padding=(0, 2),
    ))
    console.print()


def print_success(msg: str):
    console.print(f"  [bold green]✅ {msg}[/bold green]")


def print_error(msg: str):
    console.print(f"  [bold red]❌ {msg}[/bold red]")


def print_warn(msg: str):
    console.print(f"  [bold yellow]⚠️  {msg}[/bold yellow]")


def print_info(msg: str):
    console.print(f"  [bold cyan]ℹ  {msg}[/bold cyan]")


def prompt(label: str, default: str = "") -> str:
    placeholder = f" [{default}]" if default else ""
    try:
        val = console.input(f"  [bold white]{label}{placeholder}:[/bold white] ").strip()
        return val if val else default
    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]  Cancelled.[/dim]")
        return ""


def prompt_secret(label: str) -> str:
    import getpass
    try:
        val = getpass.getpass(f"  {label}: ")
        return val.strip()
    except (KeyboardInterrupt, EOFError):
        return ""


def menu_choice(options: list[tuple[str, str]], back: bool = True) -> str:
    console.print()
    for key, label in options:
        console.print(f"  [bold cyan][{key}][/bold cyan] {label}")
    if back:
        console.print(f"  [dim][0][/dim] [dim]🔙 Back[/dim]")
    console.print()
    return prompt("Select").strip()


def confirm(question: str) -> bool:
    ans = prompt(f"{question} [Y/N]").upper()
    return ans in ("Y", "YES", "1")


def progress_bar(total: int, description: str = "Processing"):
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(bar_width=30, style="cyan", complete_style="green"),
        TextColumn("[bold white]{task.percentage:>5.1f}%"),
        TextColumn("[dim]{task.completed}/{task.total}[/dim]"),
        TimeRemainingColumn(),
        console=console,
        transient=False,
    )


def fmt_time(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def date_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def log_event(log_file: Path, level: str, message: str):
    entry = f"[{now_str()}] [{level.upper()}] {message}\n"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(entry)


def status_icon(status: str) -> str:
    icons = {
        "active":      "✅ Active",
        "banned":      "⛔ Banned",
        "restricted":  "⚠️  Restricted",
        "verifying":   "⏳ Verifying",
        "idle":        "💤 Idle",
        "running":     "🔄 Running",
        "ready":       "🟢 Ready",
        "waiting":     "⏳ Waiting",
        "limit":       "💤 Limit Reached",
        "error":       "❌ Error",
    }
    return icons.get(status.lower(), status)


def wait_countdown(seconds: int, label: str = "Waiting"):
    for remaining in range(seconds, 0, -1):
        console.print(f"\r  ⏱  {label}: [bold yellow]{remaining}s[/bold yellow]  ", end="")
        time.sleep(1)
    console.print()


def read_json(path: Path, default=None):
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default if default is not None else {}
    return default if default is not None else {}


def write_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def paginate(items: list, page_size: int = 10) -> list[list]:
    return [items[i:i+page_size] for i in range(0, len(items), page_size)]
