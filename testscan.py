#!/usr/bin/env python3
import gi
gi.require_version('NM', '1.0')
from gi.repository import NM, GLib
import time

client = NM.Client.new(None)

def test_scan():
    devices = client.get_devices()
    for dev in devices:
        if dev.get_device_type() == NM.DeviceType.WIFI:
            print(f"✓ WiFi Device: {dev.get_interface()}")
            dev.request_scan(None)
            time.sleep(3)
            
            aps = dev.get_access_points()
            print(f"✓ Found {len(aps)} networks:")
            for ap in aps:
                ssid = ap.get_ssid()
                if ssid:
                    print(f"  - {ssid.get_data().decode('utf-8')} ({ap.get_strength()}%)")
            return False
    print("✗ No WiFi device found")
    return False

GLib.timeout_add(1000, test_scan)
GLib.main()