#!/usr/bin/env python3
"""
Interactive BLE Service (Mac compatible)
---------------------------------------
A minimal interactive Bluetooth Low Energy exploration and passive data logger.

Features:
 - Scans for nearby BLE devices (using macOS internal adapter)
 - Presents indexed list; user selects a device to connect
 - Discovers all services & characteristics
 - Subscribes to every characteristic that supports notify/indicate
 - Logs ALL incoming notification/indication payloads without altering them
 - Displays structured, readable output (timestamp, UUIDs, lengths, hex, ASCII)
 - Optionally saves session log to a timestamped JSONL file
 - Graceful Ctrl+C handling & clean disconnect

Non-Goals / Guarantees:
 - Does NOT modify, filter, decrypt, parse, or mutate incoming data
 - Does NOT write to the device
 - Read-only passive subscription where permitted by device properties

Dependencies: bleak
Install: pip install bleak

Usage:
  python interactive_ble_service.py            # normal interactive run
  python interactive_ble_service.py --timeout 20 --logdir logs

Press Ctrl+C at any time to stop.
"""
import asyncio
import argparse
import json
import os
import re
import signal
import sys
import time
from datetime import datetime
from typing import Optional, List

try:
    from bleak import BleakScanner, BleakClient
    from bleak.backends.device import BLEDevice
    BLEAK_AVAILABLE = True
except ImportError:
    BLEAK_AVAILABLE = False

"""
Classic Bluetooth / serial functionality was added previously (pyserial / pybluez
support, baud scanning, IEC handshake, probes). At the user's request this has
been fully removed to return the script to a pure BLE passive logger.

If future reinstatement is desired, retrieve the earlier revision from VCS
history on branch 'settingup' before this removal commit.
"""

LOG_COLORS = True if sys.stdout.isatty() else False

def color(code: str, text: str) -> str:
    if not LOG_COLORS:
        return text
    return f"\033[{code}m{text}\033[0m"

def ts() -> str:
    return datetime.utcnow().isoformat()

class InteractiveBLELogger:
    def __init__(self, args):
        self.args = args
        # Resolve log directory relative to script if relative
        if self.args.logdir:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            if not os.path.isabs(self.args.logdir):
                self.args.logdir = os.path.join(base_dir, self.args.logdir)
        # Filters
        self.target_address_norm = normalize_address(self.args.target_address) if getattr(self.args, 'target_address', None) else None
        self.name_contains = self.args.name_contains.lower() if self.args.name_contains else None
        # BLE state
        self.selected_device: Optional[BLEDevice] = None
        self.client: Optional[BleakClient] = None
        # Runtime / logging
        self.running = True
        self.log_file_path: Optional[str] = None
        self.log_file_handle = None
        self.notification_count = 0
        self.start_time = None

    async def scan_once(self, timeout: int) -> List[BLEDevice]:
        if self.args.debug:
            print(color('36', f"[{ts()}] Scan attempt (timeout={timeout}s)"))
        devices = await BleakScanner.discover(timeout=timeout)
        if self.args.debug:
            for d in devices:
                print(color('90', f"  RAW: name={d.name} address={d.address}"))
        return devices

    def device_matches_filters(self, device: BLEDevice) -> bool:
        if self.target_address_norm:
            if normalize_address(device.address) == self.target_address_norm:
                return True
        if self.name_contains:
            if (device.name or '').lower().find(self.name_contains) != -1:
                return True
        return False

    async def find_target_device(self) -> Optional[BLEDevice]:
        if not (self.target_address_norm or self.name_contains):
            return None  # no filters specified
        attempts = self.args.scan_attempts
        for attempt in range(1, attempts + 1):
            devices = await self.scan_once(self.args.scan_timeout)
            for d in devices:
                if self.device_matches_filters(d):
                    print(color('32', f"[{ts()}] Target device matched on attempt {attempt}: {d.name or 'Unknown'} ({d.address})"))
                    return d
            print(color('33', f"[{ts()}] Target not found (attempt {attempt}/{attempts})."))
        print(color('31', f"[{ts()}] Target device not found after {attempts} attempts."))
        return None

    async def interactive_scan_select(self) -> Optional[BLEDevice]:
        print(color('36', f"[{ts()}] Scanning for BLE devices (timeout={self.args.timeout}s)..."))
        devices = await BleakScanner.discover(timeout=self.args.timeout)
        if not devices:
            print(color('33', f"[{ts()}] No devices found."))
            return None
        print(color('32', f"[{ts()}] Found {len(devices)} devices."))
        return self.choose_device(devices)

    def choose_device(self, devices: List[BLEDevice]) -> Optional[BLEDevice]:
        if not devices:
            return None
        print("\nDiscovered devices:")
        for idx, d in enumerate(devices):
            name = d.name or 'Unknown'
            print(f"  [{idx}] {name}  ({d.address})")
        while True:
            try:
                choice = input(color('36', "Select device index (or press Enter to cancel): "))
                if choice.strip() == '':
                    print(color('33', 'No selection made. Exiting.'))
                    return None
                i = int(choice)
                if 0 <= i < len(devices):
                    return devices[i]
                else:
                    print(color('31', 'Invalid index.'))
            except ValueError:
                print(color('31', 'Please enter a valid integer.'))
            except EOFError:
                return None

    async def connect(self, device: BLEDevice) -> bool:
        print(color('36', f"[{ts()}] Connecting to {device.name or 'Unknown'} ({device.address})..."))
        self.client = BleakClient(device, timeout=15.0)
        try:
            await self.client.connect()
        except Exception as e:
            print(color('31', f"[{ts()}] Connection failed: {e}"))
            return False
        if self.client.is_connected:
            print(color('32', f"[{ts()}] Connected."))
            return True
        print(color('31', f"[{ts()}] Connection failed (unknown reason)."))
        return False

    async def discover_and_subscribe(self):
        if not self.client:
            return
        _ = self.client.services
        print(color('36', f"[{ts()}] Discovering services & characteristics..."))
        sub_targets = []
        read_targets = []
        for svc in self.client.services:
            print(color('35', f" Service {svc.uuid}"))
            for char in svc.characteristics:
                props = ','.join(char.properties)
                print(f"   Char {char.uuid}  props=[{props}]  handle={char.handle}")
                if any(p in char.properties for p in ("notify", "indicate")):
                    sub_targets.append(char)
                if self.args.read_all and 'read' in char.properties:
                    read_targets.append(char)
        if sub_targets:
            print(color('36', f"[{ts()}] Subscribing to {len(sub_targets)} characteristics..."))
            for char in sub_targets:
                try:
                    async def _cb(ch, data, self_ref=self):
                        self_ref._notification_handler(ch, data)
                    await self.client.start_notify(char.uuid, _cb)
                    print(color('32', f"  Subscribed {char.uuid}"))
                except Exception as e:
                    print(color('31', f"  Failed subscribe {char.uuid}: {e}"))
        else:
            print(color('33', f"[{ts()}] No notifiable/indicatable characteristics found."))
        # Perform read-all after subscriptions
        if read_targets:
            print(color('36', f"[{ts()}] Reading {len(read_targets)} readable characteristics (one-shot)..."))
            for char in read_targets:
                try:
                    data = await self.client.read_gatt_char(char.uuid)
                    self._emit_read_record(char, data)
                except Exception as e:
                    print(color('31', f"  Read failed {char.uuid}: {e}"))

    def _emit_read_record(self, char, data: bytes):
        hex_data = data.hex().upper()
        ascii_data = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in data)
        record = {
            'ts': ts(),
            'type': 'read',
            'uuid': str(char.uuid),
            'length': len(data),
            'raw_hex': hex_data,
            'raw_ascii': ascii_data,
        }
        print(color('34', f"[{record['ts']}] READ uuid={record['uuid']} len={record['length']}"))
        print(f"   HEX  {hex_data}")
        print(f"   ASCII {ascii_data}")
        if self.log_file_handle:
            self.log_file_handle.write(json.dumps(record) + '\n')

    def _open_log_file(self):
        # Always open log file (args.logdir has default)
        os.makedirs(self.args.logdir, exist_ok=True)
        fname = f"ble_session_{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.jsonl"
        self.log_file_path = os.path.join(self.args.logdir, fname)
        self.log_file_handle = open(self.log_file_path, 'a', buffering=1)
        print(color('32', f"[{ts()}] Logging raw notifications to {self.log_file_path}"))

    def _close_log_file(self):
        if self.log_file_handle:
            self.log_file_handle.close()
            self.log_file_handle = None

    def _notification_handler(self, characteristic_or_handle, data: bytearray):
        # characteristic_or_handle may be a BleakGATTCharacteristic or an int handle depending on backend
        sender_handle = getattr(characteristic_or_handle, 'handle', characteristic_or_handle)
        self.notification_count += 1
        hex_data = data.hex().upper()
        ascii_data = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in data)
        record = {
            'ts': ts(),
            'sender_handle': sender_handle,
            'length': len(data),
            'raw_hex': hex_data,
            'raw_ascii': ascii_data,
        }
        print(color('34', f"[{record['ts']}] NOTIF #{self.notification_count} handle={sender_handle} len={record['length']}"))
        print(f"   HEX  {hex_data}")
        print(f"   ASCII {ascii_data}")
        if self.log_file_handle:
            self.log_file_handle.write(json.dumps(record) + '\n')

    async def run(self):
        if not BLEAK_AVAILABLE:
            print(color('31', 'Bleak not installed. Install with: pip install bleak'))
            return 1
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._signal_stop)
            except NotImplementedError:
                pass
        self._open_log_file()
        # BLE path only
        if self.target_address_norm or self.name_contains:
            self.selected_device = await self.find_target_device()
            if not self.selected_device:
                return 4
        else:
            self.selected_device = await self.interactive_scan_select()
            if not self.selected_device:
                return 0
        connected = await self.connect(self.selected_device)
        if not connected:
            self._close_log_file()
            return 2
        await self.discover_and_subscribe()
        print(color('36', f"[{ts()}] Listening for notifications (Ctrl+C to stop)..."))
        self.start_time = time.time()
        start = self.start_time
        try:
            while self.running:
                if self.args.duration and (time.time() - start) >= self.args.duration:
                    self.running = False
                    break
                await asyncio.sleep(0.5)
        finally:
            duration = time.time() - start
            print(color('36', f"[{ts()}] Stopping ({duration:.1f}s, {self.notification_count} notifications)."))
            await self.cleanup()
        return 0

    def _signal_stop(self):
        self.running = False

    async def cleanup(self):
        if self.client and self.client.is_connected:
            try:
                await self.client.disconnect()
                print(color('32', f"[{ts()}] Disconnected."))
            except Exception as e:
                print(color('31', f"[{ts()}] Disconnect error: {e}"))
        self._close_log_file()



# Helper to normalize MAC-like addresses (remove separators, uppercase)
def normalize_address(addr: Optional[str]) -> Optional[str]:
    if not addr:
        return None
    return re.sub(r'[^A-Fa-f0-9]', '', addr).upper()


def parse_args():
    p = argparse.ArgumentParser(description="Interactive BLE passive logger (read-only)")
    p.add_argument('--timeout', type=int, default=12, help='Scan timeout seconds for interactive mode (default 12)')
    p.add_argument('--logdir', type=str, default='logs', help='Directory to store JSONL notification log (default: logs)')
    p.add_argument('--target-address', type=str, default=None, help='Directly look for device with this BLE address (case-insensitive, separators optional)')
    p.add_argument('--name-contains', type=str, default=None, help='Match first device whose name contains this substring (case-insensitive)')
    p.add_argument('--scan-attempts', type=int, default=5, help='Number of repeated scan attempts when using filters (default 5)')
    p.add_argument('--scan-timeout', type=int, default=8, help='Per-attempt scan timeout when using filters (default 8)')
    p.add_argument('--debug', action='store_true', help='Verbose discovery output (list all raw devices each attempt)')
    p.add_argument('--duration', type=int, default=0, help='If >0, auto-stop after N seconds (useful for tests)')
    p.add_argument('--read-all', action='store_true', help='After connecting BLE, read every characteristic that supports read')
    return p.parse_args()

async def amain():
    args = parse_args()
    logger = InteractiveBLELogger(args)
    rc = await logger.run()
    return rc

if __name__ == '__main__':
    try:
        exit(asyncio.run(amain()))
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)
