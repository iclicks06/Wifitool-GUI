#!/bin/bash

echo "🚀 Installing CachyOS WiFi Tool..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "⚠ Please run as root (sudo ./install.sh)"
    exit 1
fi

# Install system dependencies
echo "📦 Installing system dependencies..."
pacman -S --noconfirm python-gobject gtk3 networkmanager libappindicator-gtk3 speedtest-cli

# Create installation directory
echo "📁 Creating installation directory..."
mkdir -p /opt/cachyos-wifi-tool

# Copy files
echo "📋 Copying files..."
cp -r . /opt/cachyos-wifi-tool/

# Create virtual environment
echo "🐍 Creating virtual environment..."
cd /opt/cachyos-wifi-tool
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install desktop entry
echo "🖥️ Installing desktop entry..."
cp cachyos-wifi-tool.desktop /usr/share/applications/

# Make main.py executable
chmod +x main.py

echo "✅ Installation complete!"
echo "   - Launch from application menu or run: python /opt/cachyos-wifi-tool/main.py"
echo "   - Tray icon will appear in Waybar automatically"
