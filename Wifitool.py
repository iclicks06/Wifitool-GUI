#!/usr/bin/env python3
"""
CachyOS WiFi Tool - GTK3 Version (FIXED)
All API compatibility issues resolved
"""

import gi

# ⚠️ CRITICAL: Import order matters!
gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')
gi.require_version('NM', '1.0')
gi.require_version('Gdk', '3.0')

from gi.repository import Gtk, AppIndicator3, NM, Gio, GLib, Gdk
import os
import time
import subprocess
import sys

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════
CONFIG = {
    'app_id': 'com.cachyos.wifitool',
    'app_name': 'CachyOS WiFi',
    'update_interval_ms': 1000,
    'scan_interval_ms': 30000,
    'show_speed_in_tray': True,
    'window_width': 450,
    'window_height': 600,
}

class WiFiTool(Gtk.Window):
    """Main Application Window"""
    
    def __init__(self):
        super().__init__(title=CONFIG['app_name'])
        self.set_default_size(CONFIG['window_width'], CONFIG['window_height'])
        self.set_border_width(10)
        
        # NetworkManager Client
        self.nm_client = NM.Client.new(None)
        
        # Network statistics
        self.prev_rx_bytes = 0
        self.prev_tx_bytes = 0
        self.prev_time = time.time()
        self.active_interface = None
        
        # UI Components
        self.status_label = None
        self.ssid_label = None
        self.ip_label = None
        self.signal_label = None
        self.speed_label = None
        self.network_list = None
        self.available_networks = []
        
        # Build UI
        self.build_ui()
        
        # Setup system tray (with error handling)
        try:
            self.setup_tray()
        except Exception as e:
            print(f"⚠ Tray setup failed: {e}")
            print("  Continuing without tray...")
        
        # Start monitors
        GLib.timeout_add(CONFIG['update_interval_ms'], self.update_speed)
        GLib.timeout_add(CONFIG['scan_interval_ms'], self.auto_scan)
        
        # Initial scan after delay
        GLib.timeout_add(1000, self.scan_networks)
        
        # Connect to NM signals
        self.nm_client.connect('device-added', self.on_device_changed)
        self.nm_client.connect('device-removed', self.on_device_changed)
        
        # Close window handling
        self.connect('delete-event', self.on_window_close)

    def build_ui(self):
        """Build the GTK3 UI"""
        
        # Main vertical box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(main_box)
        
        # ─── Connection Status Frame ───────────────────────────
        status_frame = Gtk.Frame(label="Connection Status")
        status_frame.set_shadow_type(Gtk.ShadowType.IN)
        main_box.pack_start(status_frame, False, False, 0)
        
        status_grid = Gtk.Grid()
        status_grid.set_row_spacing(5)
        status_grid.set_column_spacing(10)
        status_grid.set_margin_start(10)
        status_grid.set_margin_end(10)
        status_grid.set_margin_top(10)
        status_grid.set_margin_bottom(10)
        status_frame.add(status_grid)
        
        # Status Label
        self.status_label = Gtk.Label(label="⚪ Disconnected")
        self.status_label.set_halign(Gtk.Align.START)
        status_grid.attach(self.status_label, 0, 0, 2, 1)
        
        # SSID Label
        self.ssid_label = Gtk.Label(label="SSID: --")
        self.ssid_label.set_halign(Gtk.Align.START)
        status_grid.attach(self.ssid_label, 0, 1, 2, 1)
        
        # IP Label
        self.ip_label = Gtk.Label(label="IP: --")
        self.ip_label.set_halign(Gtk.Align.START)
        status_grid.attach(self.ip_label, 0, 2, 2, 1)
        
        # Signal Label
        self.signal_label = Gtk.Label(label="Signal: --")
        self.signal_label.set_halign(Gtk.Align.START)
        status_grid.attach(self.signal_label, 0, 3, 2, 1)
        
        # Speed Label
        self.speed_label = Gtk.Label(label="↓ 0 KB/s | ↑ 0 KB/s")
        self.speed_label.set_halign(Gtk.Align.START)
        status_grid.attach(self.speed_label, 0, 4, 2, 1)
        
        # ─── Action Buttons ────────────────────────────────────
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        button_box.set_halign(Gtk.Align.CENTER)
        main_box.pack_start(button_box, False, False, 5)
        
        # Scan Button
        scan_btn = Gtk.Button(label="🔄 Scan")
        scan_btn.connect("clicked", self.on_scan_clicked)
        button_box.pack_start(scan_btn, False, False, 0)
        
        # Refresh Button
        refresh_btn = Gtk.Button(label="🔄 Refresh")
        refresh_btn.connect("clicked", self.on_refresh_clicked)
        button_box.pack_start(refresh_btn, False, False, 0)
        
        # Speed Test Button
        speedtest_btn = Gtk.Button(label="🚀 Speed Test")
        speedtest_btn.connect("clicked", self.on_speedtest_clicked)
        button_box.pack_start(speedtest_btn, False, False, 0)
        
        # ─── Available Networks Frame ──────────────────────────
        networks_frame = Gtk.Frame(label="Available Networks")
        networks_frame.set_shadow_type(Gtk.ShadowType.IN)
        main_box.pack_start(networks_frame, True, True, 0)
        
        # Scrolled Window
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(200)
        networks_frame.add(scrolled)
        
        # ListBox for networks
        self.network_list = Gtk.ListBox()
        self.network_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.network_list.connect("row-activated", self.on_network_selected)
        scrolled.add(self.network_list)
        
        # Show all widgets
        self.show_all()

    def setup_tray(self):
        """Setup system tray icon for Waybar"""
        
        # FIX: Use correct enum value
        self.tray = AppIndicator3.Indicator.new(
            "wifi-tool-tray",
            "network-wireless",
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS  # FIXED: Was COMMUNICATION
        )
        
        self.tray.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.tray.set_title(CONFIG['app_name'])
        self.tray.set_icon("network-wireless")
        
        # Create menu
        menu = Gtk.Menu()
        
        # Show Window
        show_item = Gtk.MenuItem(label="Show Window")
        show_item.connect("activate", self.on_tray_show)
        menu.append(show_item)
        
        # Separator
        menu.append(Gtk.SeparatorMenuItem())
        
        # Scan
        scan_item = Gtk.MenuItem(label="Scan Networks")
        scan_item.connect("activate", lambda x: self.scan_networks())
        menu.append(scan_item)
        
        # Separator
        menu.append(Gtk.SeparatorMenuItem())
        
        # Quit
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self.on_quit)
        menu.append(quit_item)
        
        menu.show_all()
        self.tray.set_menu(menu)
        
        print("✓ System tray initialized (Waybar compatible)")

    def on_tray_show(self, widget):
        """Show window from tray"""
        self.show_all()
        self.present()

    def on_quit(self, widget):
        """Quit application"""
        Gtk.main_quit()

    def on_window_close(self, widget, event):
        """Hide to tray on close"""
        self.hide()
        return True

    def get_wifi_device(self):
        """Get primary WiFi device"""
        devices = self.nm_client.get_devices()
        for device in devices:
            if device.get_device_type() == NM.DeviceType.WIFI:
                return device
        return None

    def get_active_connection(self):
        """Get active WiFi connection"""
        device = self.get_wifi_device()
        if not device:
            return None
        return device.get_active_connection()

    def scan_networks(self):
        """Scan for WiFi networks"""
        device = self.get_wifi_device()
        if not device:
            print("⚠ No WiFi device found")
            return False
        
        print("📡 Scanning...")
        try:
            # FIX: Use nmcli for scanning (more reliable than deprecated API)
            subprocess.run(
                ["nmcli", "device", "wifi", "rescan"],
                capture_output=True,
                timeout=10
            )
            # Wait for scan results
            GLib.timeout_add(3000, self.process_scan_results)
        except Exception as e:
            print(f"Scan error: {e}")
        
        return False

    def process_scan_results(self):
        """Process and display scan results"""
        device = self.get_wifi_device()
        if not device:
            print("⚠ No WiFi device after scan")
            return False
        
        # Clear list
        for row in self.network_list.get_children():
            self.network_list.remove(row)
        
        self.available_networks = []
        access_points = device.get_access_points()
        
        print(f"📡 Found {len(access_points)} access points")
        
        # Sort by signal strength
        access_points.sort(key=lambda ap: ap.get_strength(), reverse=True)
        
        for ap in access_points:
            ssid = ap.get_ssid()
            if ssid:
                try:
                    ssid_str = ssid.get_data().decode('utf-8')
                except:
                    ssid_str = "Hidden Network"
                
                strength = ap.get_strength()
                security = self.get_security_type(ap)
                
                # Skip duplicates
                if ssid_str in [n['ssid'] for n in self.available_networks]:
                    continue
                
                network_info = {
                    'ssid': ssid_str,
                    'strength': strength,
                    'security': security,
                    'ap': ap
                }
                self.available_networks.append(network_info)
                
                row = self.create_network_row(network_info)
                self.network_list.add(row)
        
        self.network_list.show_all()
        print(f"✓ Displaying {len(self.available_networks)} networks")
        return False

    def create_network_row(self, network_info):
        """Create a network list row"""
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(5)
        box.set_margin_bottom(5)
        
        # SSID Label
        ssid_label = Gtk.Label(label=network_info['ssid'])
        ssid_label.set_halign(Gtk.Align.START)
        box.pack_start(ssid_label, True, True, 0)
        
        # Signal & Security
        signal_icon = self.get_signal_icon(network_info['strength'])
        info_label = Gtk.Label(label=f"{signal_icon} {network_info['strength']}% | {network_info['security']}")
        box.pack_start(info_label, False, False, 0)
        
        # Connect Button
        connect_btn = Gtk.Button()
        connect_btn.set_image(Gtk.Image.new_from_icon_name("network-wireless-connected-symbolic", Gtk.IconSize.BUTTON))
        connect_btn.connect("clicked", self.on_connect_network, network_info)
        box.pack_start(connect_btn, False, False, 0)
        
        row.add(box)
        row.network_data = network_info
        return row

    def get_signal_icon(self, strength):
        """Get signal icon"""
        if strength >= 80:
            return "📶"
        elif strength >= 60:
            return "📳"
        elif strength >= 40:
            return "📲"
        else:
            return "📴"

    def get_security_type(self, ap):
        """Get security type - FIXED for API compatibility"""
        try:
            # FIX: Access flags directly from ap object
            flags = ap.get_flags()
            wpa_flags = ap.get_wpa_flags()
            rsn_flags = ap.get_rsn_flags()
            
            # FIX: Compare with 0 instead of NM.AccessPointFlags.NONE
            if wpa_flags != 0 or rsn_flags != 0:
                return "WPA2" if rsn_flags != 0 else "WPA"
            elif flags & 0x00000002:  # PRIVACY flag
                return "WEP"
            else:
                return "Open"
        except Exception as e:
            print(f"Security type error: {e}")
            return "Unknown"

    def on_network_selected(self, listbox, row):
        """Network selected"""
        if hasattr(row, 'network_data'):
            print(f"Selected: {row.network_data['ssid']}")

    def on_connect_network(self, button, network_info):
        """Connect to network"""
        ssid = network_info['ssid']
        
        if network_info['security'] != 'Open' and network_info['security'] != 'Unknown':
            self.show_password_dialog(ssid, network_info)
        else:
            self.connect_to_network(ssid, None)

    def show_password_dialog(self, ssid, network_info):
        """Show password dialog"""
        dialog = Gtk.Dialog(title="WiFi Password", transient_for=self, flags=0)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Connect", Gtk.ResponseType.OK)
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_start(20)
        box.set_margin_end(20)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        
        label = Gtk.Label(label=f"Enter password for {ssid}")
        box.pack_start(label, False, False, 0)
        
        entry = Gtk.Entry()
        entry.set_placeholder_text("Password")
        entry.set_visibility(False)
        box.pack_start(entry, False, False, 0)
        
        dialog.get_content_area().add(box)
        dialog.show_all()
        
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            password = entry.get_text()
            self.connect_to_network(ssid, password)
        
        dialog.destroy()

    def connect_to_network(self, ssid, password):
        """Connect to network using nmcli"""
        device = self.get_wifi_device()
        if not device:
            self.show_message("Error", "No WiFi device found")
            return
        
        if password:
            cmd = f"nmcli device wifi connect '{ssid}' password '{password}'"
        else:
            cmd = f"nmcli device wifi connect '{ssid}'"
        
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                print(f"✓ Connected to {ssid}")
                self.update_connection_info()
                self.show_message("Success", f"Connected to {ssid}")
            else:
                print(f"✗ Failed: {result.stderr}")
                self.show_message("Error", f"Connection failed:\n{result.stderr}")
                
        except Exception as e:
            self.show_message("Error", str(e))

    def show_message(self, title, message):
        """Show message dialog"""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO if title == "Success" else Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=title
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()

    def update_speed(self):
        """Update network speed - FIXED"""
        try:
            device = self.get_wifi_device()
            if not device:
                return True
            
            # FIX: Use get_iface() instead of get_interface()
            self.active_interface = device.get_iface()
            
            if not self.active_interface:
                return True
            
            current_rx, current_tx = self.get_interface_stats(self.active_interface)
            current_time = time.time()
            
            time_delta = current_time - self.prev_time
            if time_delta > 0 and self.prev_rx_bytes > 0:
                rx_speed = (current_rx - self.prev_rx_bytes) / time_delta
                tx_speed = (current_tx - self.prev_tx_bytes) / time_delta
                
                rx_kbs = max(0, rx_speed / 1024)
                tx_kbs = max(0, tx_speed / 1024)
                
                if self.speed_label:
                    self.speed_label.set_label(f"↓ {rx_kbs:.1f} KB/s | ↑ {tx_kbs:.1f} KB/s")
                
                if CONFIG['show_speed_in_tray'] and hasattr(self, 'tray'):
                    self.tray.set_title(f"{CONFIG['app_name']}\n↓ {rx_kbs:.1f} KB/s | ↑ {tx_kbs:.1f} KB/s")
            
            self.prev_rx_bytes = current_rx
            self.prev_tx_bytes = current_tx
            self.prev_time = current_time
            
        except Exception as e:
            # Silently ignore speed errors (don't spam terminal)
            pass
        
        return True

    def get_interface_stats(self, interface):
        """Read /proc/net/dev"""
        try:
            with open('/proc/net/dev', 'r') as f:
                for line in f:
                    if interface + ':' in line:
                        parts = line.split()
                        rx_bytes = int(parts[1])
                        tx_bytes = int(parts[9])
                        return rx_bytes, tx_bytes
        except Exception as e:
            pass
        return 0, 0

    def update_connection_info(self):
        """Update connection status"""
        active = self.get_active_connection()
        
        if active:
            ip_config = active.get_ip4_config()
            device = self.get_wifi_device()
            
            if device and ip_config:
                self.status_label.set_label("🟢 Connected")
                
                ssid = device.get_ssid()
                if ssid:
                    self.ssid_label.set_label(f"SSID: {ssid}")
                
                addresses = ip_config.get_addresses()
                if addresses:
                    ip = addresses[0].get_address()
                    self.ip_label.set_label(f"IP: {ip}")
                
                strength = device.get_percent()
                self.signal_label.set_label(f"Signal: {strength}% {self.get_signal_icon(strength)}")
            else:
                self.set_disconnected_state()
        else:
            self.set_disconnected_state()

    def set_disconnected_state(self):
        """Set disconnected state"""
        self.status_label.set_label("⚪ Disconnected")
        self.ssid_label.set_label("SSID: --")
        self.ip_label.set_label("IP: --")
        self.signal_label.set_label("Signal: --")

    def auto_scan(self):
        """Periodic scan"""
        self.scan_networks()
        self.update_connection_info()
        return True

    def on_scan_clicked(self, button):
        """Manual scan"""
        self.scan_networks()
        self.show_message("Scanning", "Scanning for networks...")

    def on_refresh_clicked(self, button):
        """Refresh info"""
        self.update_connection_info()

    def on_speedtest_clicked(self, button):
        """Run speed test"""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="Speed Test"
        )
        dialog.format_secondary_text("Running speed test...")
        dialog.show_all()
        
        GLib.timeout_add(100, self.run_speedtest, dialog)

    def run_speedtest(self, dialog):
        """Run speedtest"""
        try:
            cmd = "speedtest-cli --simple 2>/dev/null || fast 2>/dev/null || echo 'Install speedtest-cli'"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
            
            dialog.destroy()
            
            result_dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Speed Test Results"
            )
            result_dialog.format_secondary_text(result.stdout if result.stdout else "No results")
            result_dialog.run()
            result_dialog.destroy()
            
        except Exception as e:
            dialog.destroy()
            self.show_message("Error", f"Speed test failed:\n{str(e)}")
        
        return False

    def on_device_changed(self, client, device):
        """Handle device changes"""
        self.update_connection_info()
        self.scan_networks()

# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    window = WiFiTool()
    window.connect('destroy', Gtk.main_quit)
    window.show_all()
    Gtk.main()