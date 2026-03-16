# Wifitool-GUI
I saw a issue in linux with wifi that its hard to connect idk i am new with linux and i found its kinda hard so i decided to build a tool for it and its waybar ready so yea and you can also cuztomize it with your flavours 


# 📶 CachyOS WiFi Tool

A feature-rich WiFi manager with real-time speed monitoring, designed for Wayland/Waybar desktop environments.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![GTK](https://img.shields.io/badge/GTK-3.0-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## ✨ Features

- 📡 **WiFi Scanning** - Scan and list all available networks
- 🔐 **Connect to Networks** - Support for Open, WPA, WPA2 networks
- 📊 **Real-time Speed Monitor** - Live upload/download speed
- 🚀 **Speed Test** - Built-in internet speed test
- 📱 **System Tray** - Waybar compatible tray icon
- 🎨 **GTK3 UI** - Clean, native Linux desktop appearance
- 🐧 **Wayland Ready** - Works on Sway, Hyprland, GNOME Wayland

## 📋 Requirements

### System Dependencies (Arch/CachyOS)

```bash
sudo pacman -S python-gobject gtk3 networkmanager libappindicator-gtk3
