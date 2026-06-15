# Telegram Automation Suite v1.0 — Termux CLI

A fully-featured Telegram automation tool designed for Termux on Android. All operations run locally in your terminal — no web interface, no browser.

---

## File Structure

```
telegram_suite/
│
├── main.py                   ← Entry point — run this
├── config.py                 ← Credentials + settings loader
├── requirements.txt          ← Python dependencies
├── setup.sh                  ← One-shot Termux installer
├── .env                      ← API credentials (auto-created on first run)
├── .env.example              ← Template for .env
│
├── modules/
│   ├── utils.py              ← Shared CLI utilities (colors, prompts, progress bars)
│   ├── database.py           ← Local JSON data store (accounts, proxies, stats)
│   ├── account_manager.py    ← Add, import, validate, warm-up accounts
│   ├── member_scraper.py     ← Scrape members from public/private groups
│   ├── member_adder.py       ← Add members to target groups with rotation
│   ├── rotation.py           ← Smart account rotation system
│   ├── proxy_manager.py      ← Add, validate, and assign proxies
│   ├── settings_menu.py      ← API credentials + global settings UI
│   ├── reports.py            ← Daily/weekly reports and log viewer
│   ├── security.py           ← Blacklist, smart limits, backup, ban monitor
│   ├── bulk_messaging.py     ← Send messages to multiple users
│   └── campaigns.py          ← Large-scale outreach campaign management
│
├── sessions/                 ← Saved .session files (one per account)
├── exports/                  ← Scraped member CSV files
├── logs/                     ← Operation logs (import, message, error)
├── data/                     ← JSON data (accounts.json, proxies.json, etc.)
└── backups/                  ← Backup archives (.zip)
```

---

## Installation (Termux)

```bash
# 1. Install Termux from F-Droid (not Google Play)
# 2. Open Termux and run:

pkg install git python -y
git clone <your-repo-url>
cd telegram_suite
bash setup.sh
```

Or manually:
```bash
pkg update && pkg upgrade -y
pkg install python python-pip -y
pip install -r requirements.txt
python main.py
```

---

## First Run

On first launch, the tool asks for your **API ID** and **API Hash** once.
Get them at: https://my.telegram.org/apps

After that, credentials are saved in `.env` and never asked again.

---

## Features

| Module              | What It Does |
|---------------------|--------------|
| Account Manager     | Add accounts via phone, import .session files, validate, warm-up |
| Member Scraper      | Scrape public groups, private links, by messages, or bulk |
| Member Adder        | Add/invite members with rotation, delays, and flood protection |
| Rotation System     | Sequential, random, weighted, or smart account rotation |
| Proxy Manager       | SOCKS5/4, HTTP, MTProto — validate and auto-assign |
| Settings            | API credentials, limits, delays, logging |
| Reports & Logs      | Daily/weekly stats, log viewer, CSV/TXT export |
| Security Tools      | Blacklist, smart limits, health check, cleanup, backup |
| Bulk Messaging      | Send messages to user lists with rotation |
| Campaigns           | Create, launch, and track large-scale outreach campaigns |

---

## Safety Notes

- Use slow delays (60–120s) to avoid FloodWait bans
- Enable Smart Limits for automatic protection
- Warm up new accounts before heavy use
- Use proxies for each account when possible
- Do not exceed 20 adds/day per account on new accounts

---

## Data Files

| File                     | Contents |
|--------------------------|----------|
| `data/accounts.json`     | All connected Telegram accounts |
| `data/proxies.json`      | Configured proxy list |
| `data/settings.json`     | Global settings |
| `data/blacklist.json`    | Blacklisted user IDs |
| `data/stats.json`        | Daily usage statistics |
| `data/campaigns.json`    | Outreach campaign data |
| `data/rotation_cfg.json` | Rotation system config |
| `data/import_progress.json` | Resume checkpoint for imports |
