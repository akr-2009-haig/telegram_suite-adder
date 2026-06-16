#!/data/data/com.termux/files/usr/bin/bash

echo ""
echo "=============================================="
echo "  Telegram Automation Suite — Termux Setup"
echo "  By: Akram Haig  |  +967772009303"
echo "=============================================="
echo ""

echo "[1/5] Updating packages..."
pkg update -y && pkg upgrade -y

echo ""
echo "[2/5] Installing required system packages..."
pkg install python python-pip libxml2 libxslt openssl-tool -y

echo ""
echo "[3/5] Installing Python dependencies..."
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

echo ""
echo "[4/5] Creating required directories..."
mkdir -p sessions exports logs data backups

echo ""
echo "[5/5] Setting up config..."
if [ ! -f ".env" ]; then
    echo ""
    echo "┌─────────────────────────────────────────────────────┐"
    echo "│            Telegram API Credentials Setup           │"
    echo "│                                                     │"
    echo "│  Get your API_ID and API_HASH from:                 │"
    echo "│  https://my.telegram.org/apps                       │"
    echo "└─────────────────────────────────────────────────────┘"
    echo ""
    read -p "  Enter your API_ID   : " api_id
    read -p "  Enter your API_HASH : " api_hash
    echo "API_ID=$api_id" > .env
    echo "API_HASH=$api_hash" >> .env
    echo ""
    echo "  ✅ Credentials saved to .env"
else
    echo "  ✅ .env already exists — skipping."
fi

echo ""
echo "=============================================="
echo "  Setup Complete!"
echo "  Run: python main.py"
echo "  Note: First run will ask for activation password."
echo "=============================================="
echo ""
