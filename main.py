#!/usr/bin/env python3
"""
CachyOS WiFi Tool
A feature-rich WiFi manager with system tray support for Waybar
Compatible with Wayland, GTK4, and Libadwaita
"""

import gi
gi.require_version('AppIndicator3', '0.1')

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('NM', '1.0')


from gi.repository import Gtk, Adw, NM, Gio, GLib, AppIndicator3
import os
import time
import subprocess

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION - TWEAK THESE VALUES
# ═══════════════════════════════════════════════════════════════
CONFIG = {
    'app_id': 'com.cachyos.wifitool',
    'app_name': 'CachyOS WiFi',
    'update_interval_ms': 1000,      # Speed update interval (1 second)
    'scan_interval_ms': 30000,       # Auto-scan interval (30 seconds)
    'show_speed_in_tray': True,      # Show speed in tray tooltip
    'theme_variant': 'default',      # 'default', 'dark', 'light'
    'window_width': 450,
    'window_height': 600,
}

class WiFiTool(Adw.Application):
    """Main Application Class"""
    
    def __init__(self):
        super().__init__(application_id=CONFIG['app_id'])
        
        # NetworkManager Client - handles all WiFi operations
        self.nm_client = NM.Client.new(None)
        
        # Track network statistics
        self.prev_rx_bytes = 0
        self.prev_tx_bytes = 0
        self.prev_time = time.time()
        self.active_interface = None
        
        # UI References (for updates)
        self.window = None
        self.status_label = None
        self.ssid_label = None
        self.ip_label = None
        self.signal_label = None
        self.speed_label = None
        self.network_list = None
        
        # System Tray Indicator
        self.tray = None
        
        # Store available networks
        self.available_networks = []

    # ═══════════════════════════════════════════════════════════
    # APPLICATION LIFECYCLE
    # ═══════════════════════════════════════════════════════════
    
    def do_activate(self):
        """Called when app is launched"""
        
        # Create main window
        self.window = Adw.ApplicationWindow(
            application=self,
            title=CONFIG['app_name'],
            default_width=CONFIG['window_width'],
            default_height=CONFIG['window_height']
        )
        
        # Set theme variant (dark/light)
        if CONFIG['theme_variant'] == 'dark':
            self.window.get_style_context().add_class('dark')
        elif CONFIG['theme_variant'] == 'light':
            self.window.get_style_context().add_class('light')
        
        # Build UI
        self.build_ui()
        
        # Initialize system tray
        self.setup_tray()
        
        # Start background monitors
        GLib.timeout_add(CONFIG['update_interval_ms'], self.update_speed)
        GLib.timeout_add(CONFIG['scan_interval_ms'], self.auto_scan)
        
        # Initial scan
        self.scan_networks()
        
        # Show window
        self.window.present()
        
        # Connect to NetworkManager signals
        self.nm_client.connect('device-added', self.on_device_changed)
        self.nm_client.connect('device-removed', self.on_device_changed)

    def build_ui(self):
        """Build the GTK4/Libadwaita UI"""
        
        # ─── Header Bar ────────────────────────────────────────
        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(True)
        
        # ─── Main Container ────────────────────────────────────
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_top(10)
        main_box.set_margin_bottom(10)
        main_box.set_margin_start(15)
        main_box.set_margin_end(15)
        
        # ─── Connection Status Card ────────────────────────────
        status_card = Adw.PreferencesGroup(title="Connection Status")
        
        # Status Label (Connected/Disconnected)
        self.status_label = Gtk.Label(label="⚪ Disconnected")
        self.status_label.set_halign(Gtk.Align.START)
        self.status_label.add_css_class('status-label')
        status_card.add(self.status_label)
        
        # SSID Label
        self.ssid_label = Gtk.Label(label="SSID: --")
        self.ssid_label.set_halign(Gtk.Align.START)
        status_card.add(self.ssid_label)
        
        # IP Address Label
        self.ip_label = Gtk.Label(label="IP: --")
        self.ip_label.set_halign(Gtk.Align.START)
        status_card.add(self.ip_label)
        
        # Signal Strength Label
        self.signal_label = Gtk.Label(label="Signal: --")
        self.signal_label.set_halign(Gtk.Align.START)
        status_card.add(self.signal_label)
        
        # Internet Speed Label
        self.speed_label = Gtk.Label(label="↓ 0 KB/s | ↑ 0 KB/s")
        self.speed_label.set_halign(Gtk.Align.START)
        self.speed_label.add_css_class('speed-label')
        status_card.add(self.speed_label)
        
        main_box.append(status_card)
        
        # ─── Action Buttons ────────────────────────────────────
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        button_box.set_halign(Gtk.Align.CENTER)
        
        # Scan Button
        scan_btn = Gtk.Button(label="🔄 Scan")
        scan_btn.connect("clicked", self.on_scan_clicked)
        scan_btn.add_css_class('suggested-action')
        button_box.append(scan_btn)
        
        # Refresh Info Button
        refresh_btn = Gtk.Button(label="🔄 Refresh")
        refresh_btn.connect("clicked", self.on_refresh_clicked)
        button_box.append(refresh_btn)
        
        # Speed Test Button
        speedtest_btn = Gtk.Button(label="🚀 Speed Test")
        speedtest_btn.connect("clicked", self.on_speedtest_clicked)
        button_box.append(speedtest_btn)
        
        main_box.append(button_box)
        
        # ─── Available Networks List ───────────────────────────
        networks_group = Adw.PreferencesGroup(title="Available Networks")
        
        # Scrolled Window for network list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        # ListBox for networks
        self.network_list = Gtk.ListBox()
        self.network_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.network_list.connect("row-activated", self.on_network_selected)
        scrolled.set_child(self.network_list)
        
        networks_group.add(scrolled)
        main_box.append(networks_group)
        
        # ─── Set Window Content ────────────────────────────────
        self.window.set_content(main_box)

    # ═══════════════════════════════════════════════════════════
    # SYSTEM TRAY (Waybar Compatible)
    # ═══════════════════════════════════════════════════════════
    
    def setup_tray(self):
        """Setup system tray icon for Waybar integration"""
        
        try:
            # Create AppIndicator (works with Waybar tray module)
            self.tray = AppIndicator3.Indicator.new(
                "wifi-tool-tray",
                "network-wireless",  # Icon name
                AppIndicator3.IndicatorCategory.COMMUNICATION
            )
            
            self.tray.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
            self.tray.set_title(CONFIG['app_name'])
            self.tray.set_icon("network-wireless")
            
            # Create tray menu
            menu = Gtk.Menu()
            
            # Show Window Item
            show_item = Gtk.MenuItem(label="Show Window")
            show_item.connect("activate", self.on_tray_show)
            menu.append(show_item)
            
            # Separator
            sep = Gtk.SeparatorMenuItem()
            menu.append(sep)
            
            # Scan Item
            scan_item = Gtk.MenuItem(label="Scan Networks")
            scan_item.connect("activate", lambda x: self.scan_networks())
            menu.append(scan_item)
            
            # Separator
            sep2 = Gtk.SeparatorMenuItem()
            menu.append(sep2)
            
            # Quit Item
            quit_item = Gtk.MenuItem(label="Quit")
            quit_item.connect("activate", self.on_quit)
            menu.append(quit_item)
            
            menu.show_all()
            self.tray.set_menu(menu)
            
            print("✓ System tray initialized (Waybar compatible)")
            
        except Exception as e:
            print(f"⚠ Tray setup failed: {e}")
            print("  Make sure: sudo pacman -S libappindicator-gtk3")

    def on_tray_show(self, widget):
        """Show main window when tray icon clicked"""
        self.window.present()
        self.window.set_visible(True)

    def on_quit(self, widget):
        """Quit application"""
        self.quit()

    # ═══════════════════════════════════════════════════════════
    # NETWORK MANAGEMENT (NetworkManager DBus)
    # ═══════════════════════════════════════════════════════════
    
    def get_wifi_device(self):
        """Get the primary WiFi device"""
        devices = self.nm_client.get_devices()
        for device in devices:
            if device.get_device_type() == NM.DeviceType.WIFI:
                return device
        return None

    def get_active_connection(self):
        """Get current active WiFi connection info"""
        device = self.get_wifi_device()
        if not device:
            return None
        
        active = device.get_active_connection()
        if not active:
            return None
        
        return active

    def scan_networks(self):
        """Scan for available WiFi networks"""
        device = self.get_wifi_device()
        if not device:
            print("⚠ No WiFi device found")
            return
        
        print("📡 Scanning for networks...")
        device.request_scan()
        
        # Wait a bit then process results
        GLib.timeout_add(2000, self.process_scan_results)

    def process_scan_results(self):
        """Process scan results and update UI list"""
        device = self.get_wifi_device()
        if not device:
            return False
        
        # Clear existing list
        while self.network_list.get_first_child():
            self.network_list.remove(self.network_list.get_first_child())
        
        self.available_networks = []
        
        # Get access points
        access_points = device.get_access_points()
        
        # Sort by signal strength
        access_points.sort(key=lambda ap: ap.get_strength(), reverse=True)
        
        for ap in access_points:
            ssid = ap.get_ssid()
            if ssid:
                # Convert SSID bytes to string
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
                
                # Create list row
                row = self.create_network_row(network_info)
                self.network_list.append(row)
        
        print(f"✓ Found {len(self.available_networks)} networks")
        return False

    def create_network_row(self, network_info):
        """Create a UI row for a network"""
        row = Adw.ActionRow()
        row.set_title(network_info['ssid'])
        
        # Signal strength icon
        signal_icon = self.get_signal_icon(network_info['strength'])
        row.set_subtitle(f"{signal_icon} {network_info['strength']}% | {network_info['security']}")
        
        # Store network info in row for later use
        row.network_data = network_info
        
        # Connect button
        connect_btn = Gtk.Button()
        connect_btn.set_icon_name("network-wireless-connected-symbolic")
        connect_btn.add_css_class('flat')
        connect_btn.connect("clicked", self.on_connect_network, network_info)
        row.add_suffix(connect_btn)
        
        return row

    def get_signal_icon(self, strength):
        """Get signal icon based on strength"""
        if strength >= 80:
            return "📶"
        elif strength >= 60:
            return "📳"
        elif strength >= 40:
            return "📲"
        else:
            return "📴"

    def get_security_type(self, ap):
        """Get security type of access point"""
        flags = ap.get_flags()
        wpa_flags = ap.get_wpa_flags()
        rsn_flags = ap.get_rsn_flags()
        
        if wpa_flags != NM.AccessPointFlags.NONE or rsn_flags != NM.AccessPointFlags.NONE:
            if rsn_flags != NM.AccessPointFlags.NONE:
                return "WPA2"
            return "WPA"
        elif flags & NM.AccessPointFlags.PRIVACY:
            return "WEP"
        else:
            return "Open"

    def on_network_selected(self, listbox, row):
        """Handle network selection"""
        if hasattr(row, 'network_data'):
            print(f"Selected: {row.network_data['ssid']}")

    def on_connect_network(self, button, network_info):
        """Connect to selected network"""
        device = self.get_wifi_device()
        if not device:
            return
        
        ssid = network_info['ssid']
        print(f"🔗 Connecting to: {ssid}")
        
        # For WPA2 networks, you'll need to handle passwords
        # This is a simplified version - production should use NM secrets
        connection = NM.RemoteConnection.new()
        
        # Show password dialog for secured networks
        if network_info['security'] != 'Open':
            self.show_password_dialog(ssid, network_info)
        else:
            # Open network - connect directly
            self.connect_to_network(ssid, None)

    def show_password_dialog(self, ssid, network_info):
        """Show password dialog for secured networks"""
        dialog = Adw.MessageDialog(
            transient_for=self.window,
            heading="WiFi Password",
            body=f"Enter password for {ssid}"
        )
        
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("connect", "Connect")
        dialog.set_response_appearance("connect", Adw.ResponseAppearance.SUGGESTED)
        
        # Password entry
        entry = Gtk.Entry()
        entry.set_placeholder_text("Password")
        entry.set_visibility(False)  # Hide password
        entry.set_hexpand(True)
        dialog.set_extra_child(entry)
        
        dialog.connect("response", self.on_password_response, entry, ssid)
        dialog.present()

    def on_password_response(self, dialog, response, entry, ssid):
        """Handle password dialog response"""
        if response == "connect":
            password = entry.get_text()
            self.connect_to_network(ssid, password)
        dialog.destroy()

    def connect_to_network(self, ssid, password):
        """Actually connect to network via NetworkManager"""
        device = self.get_wifi_device()
        if not device:
            return
        
        # Use nmcli for simpler connection handling
        if password:
            cmd = f"nmcli device wifi connect '{ssid}' password '{password}'"
        else:
            cmd = f"nmcli device wifi connect '{ssid}'"
        
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                print(f"✓ Connected to {ssid}")
                self.update_connection_info()
            else:
                print(f"✗ Connection failed: {result.stderr}")
                self.show_error_dialog(f"Connection failed:\n{result.stderr}")
                
        except Exception as e:
            print(f"✗ Error: {e}")
            self.show_error_dialog(str(e))

    def show_error_dialog(self, message):
        """Show error dialog"""
        dialog = Adw.MessageDialog(
            transient_for=self.window,
            heading="Error",
            body=message
        )
        dialog.add_response("ok", "OK")
        dialog.present()

    # ═══════════════════════════════════════════════════════════
    # NETWORK STATISTICS & SPEED
    # ═══════════════════════════════════════════════════════════
    
    def update_speed(self):
        """Update network speed every interval"""
        try:
            # Get active interface name
            device = self.get_wifi_device()
            if not device:
                return True
            
            self.active_interface = device.get_interface()
            
            # Read /proc/net/dev for speed calculation
            current_rx, current_tx = self.get_interface_stats(self.active_interface)
            current_time = time.time()
            
            # Calculate speed
            time_delta = current_time - self.prev_time
            if time_delta > 0:
                rx_speed = (current_rx - self.prev_rx_bytes) / time_delta
                tx_speed = (current_tx - self.prev_tx_bytes) / time_delta
                
                # Convert to KB/s
                rx_kbs = rx_speed / 1024
                tx_kbs = tx_speed / 1024
                
                # Update UI label
                if self.speed_label:
                    self.speed_label.set_label(
                        f"↓ {rx_kbs:.1f} KB/s | ↑ {tx_kbs:.1f} KB/s"
                    )
                
                # Update tray tooltip
                if CONFIG['show_speed_in_tray'] and self.tray:
                    self.tray.set_title(
                        f"{CONFIG['app_name']}\n↓ {rx_kbs:.1f} KB/s | ↑ {tx_kbs:.1f} KB/s"
                    )
            
            # Store for next calculation
            self.prev_rx_bytes = current_rx
            self.prev_tx_bytes = current_tx
            self.prev_time = current_time
            
        except Exception as e:
            print(f"Speed update error: {e}")
        
        return True  # Continue timer

    def get_interface_stats(self, interface):
        """Read network statistics from /proc/net/dev"""
        try:
            with open('/proc/net/dev', 'r') as f:
                for line in f:
                    if interface + ':' in line:
                        parts = line.split()
                        # RX bytes is index 1, TX bytes is index 9
                        rx_bytes = int(parts[1])
                        tx_bytes = int(parts[9])
                        return rx_bytes, tx_bytes
        except Exception as e:
            print(f"Error reading stats: {e}")
        return 0, 0

    def update_connection_info(self):
        """Update connection status, IP, signal, etc."""
        active = self.get_active_connection()
        
        if active:
            # Get connection details
            ip_config = active.get_ip4_config()
            device = self.get_wifi_device()
            
            if device and ip_config:
                # Update status
                self.status_label.set_label("🟢 Connected")
                self.status_label.add_css_class('success')
                
                # Get SSID
                ssid = device.get_ssid()
                if ssid:
                    self.ssid_label.set_label(f"SSID: {ssid}")
                
                # Get IP address
                addresses = ip_config.get_addresses()
                if addresses:
                    ip = addresses[0].get_address()
                    self.ip_label.set_label(f"IP: {ip}")
                
                # Get signal strength
                strength = device.get_percent()
                self.signal_label.set_label(f"Signal: {strength}% {self.get_signal_icon(strength)}")
            else:
                self.set_disconnected_state()
        else:
            self.set_disconnected_state()

    def set_disconnected_state(self):
        """Set UI to disconnected state"""
        self.status_label.set_label("⚪ Disconnected")
        self.status_label.remove_css_class('success')
        self.ssid_label.set_label("SSID: --")
        self.ip_label.set_label("IP: --")
        self.signal_label.set_label("Signal: --")

    def auto_scan(self):
        """Periodic auto-scan"""
        self.scan_networks()
        self.update_connection_info()
        return True

    # ═══════════════════════════════════════════════════════════
    # BUTTON HANDLERS
    # ═══════════════════════════════════════════════════════════
    
    def on_scan_clicked(self, button):
        """Manual scan button clicked"""
        self.scan_networks()

    def on_refresh_clicked(self, button):
        """Refresh connection info"""
        self.update_connection_info()

    def on_speedtest_clicked(self, button):
        """Run internet speed test"""
        print("🚀 Running speed test...")
        
        # Show loading dialog
        dialog = Adw.MessageDialog(
            transient_for=self.window,
            heading="Speed Test",
            body="Running speed test...\nThis may take a few seconds."
        )
        dialog.add_response("cancel", "Cancel")
        dialog.present()
        
        # Run speedtest in background
        GLib.timeout_add(100, self.run_speedtest, dialog)

    def run_speedtest(self, dialog):
        """Run speedtest-cli or fast"""
        try:
            # Try speedtest-cli first, fallback to fast
            cmd = "speedtest-cli --simple 2>/dev/null || fast 2>/dev/null || echo 'Install speedtest-cli'"
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            dialog.destroy()
            
            # Show results
            result_dialog = Adw.MessageDialog(
                transient_for=self.window,
                heading="Speed Test Results",
                body=result.stdout if result.stdout else "No results"
            )
            result_dialog.add_response("ok", "OK")
            result_dialog.present()
            
        except Exception as e:
            dialog.destroy()
            self.show_error_dialog(f"Speed test failed:\n{str(e)}")
        
        return False

    def on_device_changed(self, client, device):
        """Handle device add/remove events"""
        self.update_connection_info()
        self.scan_networks()

    # ═══════════════════════════════════════════════════════════
    # CSS STYLING (Optional Custom Styles)
    # ═══════════════════════════════════════════════════════════
    
    def load_css(self):
        """Load custom CSS for styling"""
        css = """
        .status-label {
            font-size: 16px;
            font-weight: bold;
        }
        .speed-label {
            font-size: 14px;
            font-family: monospace;
            color: #3584e4;
        }
        .success {
            color: #26a269;
        }
        .error {
            color: #c01c28;
        }
        """
        
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

# ═══════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import sys
    
    # Import Gdk for CSS (needs to be after gi.require_version)
    gi.require_version('Gdk', '4.0')
    from gi.repository import Gdk
    
    app = WiFiTool()
    app.load_css()
    exit_code = app.run(sys.argv)
    sys.exit(exit_code)