#!/usr/bin/env python3
"""
Bluetooth wM-Bus Telegram Capture (Enhanced)
Configurable scan / monitor durations, dynamic patterns, bridge mode output.
"""
import asyncio
import logging
import sys
import signal
from datetime import datetime
from typing import List, Dict, Any, Optional
import re
import json
import argparse

try:
    import bleak
    from bleak import BleakScanner, BleakClient
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData
    BLEAK_AVAILABLE = True
    print("✓ Bleak library available")
except ImportError:
    BLEAK_AVAILABLE = False
    print("✗ Bleak library not available. Install with: pip install bleak")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Use default SIGPIPE behavior so the process exits quietly if downstream pipe closes (e.g., head)
try:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except Exception:
    pass

class WMBusBluetoothCapture:
    """wM-Bus Bluetooth telegram capture service"""
    def __init__(self, patterns: Optional[List[str]] = None, name_contains: Optional[str] = None, bridge_mode: bool = False, print_all: bool = False):
        # Attributes
        self.discovered_devices: Dict[str, BLEDevice] = {}
        self.connected_devices: Dict[str, BleakClient] = {}
        self.captured_frames: List[Dict[str, Any]] = []
        self.scanning = False
        self.bridge_mode = bridge_mode
        self.print_all = print_all
        self._stdout_active = True  # Track downstream stdout availability to silence BrokenPipe

        # Patterns & UUIDs
        self.device_patterns = [
            r'FlowIQ.*', r'FIQ.*', r'Kamstrup.*', r'Multical.*', r'MC21.*', r'VW.*', r'.*66501566.*', r'.*250111.*'
        ]
        if patterns:
            self.device_patterns.extend(patterns)
        if name_contains:
            self.device_patterns.append(f'.*{re.escape(name_contains)}.*')
        self.service_uuids = [
            '0000180f-0000-1000-8000-00805f9b34fb', '6e400001-b5a3-f393-e0a9-e50e24dcca9e',
            '0000ffe0-0000-1000-8000-00805f9b34fb', '0000fff0-0000-1000-8000-00805f9b34fb'
        ]

        # Startup info
        self._safe_print("🔧 wM-Bus Bluetooth Capture initialized")
        self._safe_print(f"📱 Device patterns: {len(self.device_patterns)} (user added: {len(patterns) if patterns else 0})")
        self._safe_print(f"🔌 Service UUIDs: {len(self.service_uuids)}")
        if self.bridge_mode:
            if self.print_all:
                self._safe_print("🌉 Bridge mode enabled: ALL notifications hex emitted (--print-all)")
            else:
                self._safe_print("🌉 Bridge mode enabled: potential telegram hex emitted (filtering)")

    def _safe_print(self, *args, **kwargs):
        """Print wrapper that suppresses BrokenPipeError and flips stdout_active flag."""
        if not self._stdout_active:
            return
        try:
            print(*args, **kwargs)
        except BrokenPipeError:
            if self._stdout_active:
                self._stdout_active = False
                logger.warning("🔇 Downstream consumer closed pipe (BrokenPipe) during print. Further prints suppressed.")
        except Exception as e:
            logger.error(f"❌ Print error: {e}")

    def is_target_device(self, device: BLEDevice, adv_data: AdvertisementData) -> bool:
        name = device.name or ""
        for pattern in self.device_patterns:
            if re.match(pattern, name, re.IGNORECASE):
                logger.info(f"📡 Found target device by pattern '{pattern}': {name}")
                return True
        if hasattr(adv_data, 'service_uuids') and adv_data.service_uuids:
            lowered = [s.lower() for s in adv_data.service_uuids]
            for uuid in self.service_uuids:
                if uuid.lower() in lowered:
                    logger.info(f"🔌 Found target device by service UUID: {name}")
                    return True
        if "66501566" in name or "250111" in name:
            logger.info(f"🎯 Found specific target device: {name}")
            return True
        return False

    async def scan_for_devices(self, timeout: float = 30.0) -> List[BLEDevice]:
        self.scanning = True
        logger.info(f"🔍 Starting Bluetooth scan (timeout: {timeout}s)")
        def detection_callback(device: BLEDevice, adv_data: AdvertisementData):
            if self.is_target_device(device, adv_data):
                if device.address not in self.discovered_devices:
                    self.discovered_devices[device.address] = device
                    logger.info(f"📱 Target device discovered: {device.name or 'Unknown'} ({device.address})")
        try:
            scanner = BleakScanner(detection_callback=detection_callback)
            await scanner.start()
            await asyncio.sleep(timeout)
            await scanner.stop()
            logger.info(f"✅ Scan complete. Found {len(self.discovered_devices)} target devices")
            return list(self.discovered_devices.values())
        except Exception as e:
            logger.error(f"❌ Scan error: {e}")
            return []
        finally:
            self.scanning = False

    async def connect_to_device(self, device: BLEDevice) -> Optional[BleakClient]:
        try:
            logger.info(f"🔗 Connecting to: {device.name or 'Unknown'} ({device.address})")
            client = BleakClient(device, timeout=10.0)
            await client.connect()
            if client.is_connected:
                self.connected_devices[device.address] = client
                logger.info(f"✅ Connected to {device.address}")
                await self.discover_services(client, device)
                return client
            logger.warning(f"❌ Failed to connect to {device.address}")
            return None
        except Exception as e:
            logger.error(f"❌ Connection error for {device.address}: {e}")
            return None

    async def discover_services(self, client: BleakClient, device: BLEDevice) -> None:
        try:
            services = client.services
            logger.info(f"🔍 Discovering services for {device.address}")
            for service in services:
                logger.info(f"  📋 Service: {service.uuid}")
                for char in service.characteristics:
                    props = char.properties
                    logger.info(f"    🔧 Characteristic: {char.uuid} (Properties: {props})")
                    if "notify" in props or "indicate" in props:
                        logger.info(f"📡 Setting up notifications for: {char.uuid}")
                        await self.setup_notifications(client, char, device)
        except Exception as e:
            logger.error(f"❌ Service discovery error: {e}")

    async def setup_notifications(self, client: BleakClient, characteristic, device: BLEDevice):
        try:
            def notification_handler(chr_obj, data: bytearray):
                try:
                    hex_data = data.hex().upper()
                    ts = datetime.utcnow().isoformat()
                    frame = {
                        'timestamp': ts,
                        'device_name': device.name or 'Unknown',
                        'device_address': device.address,
                        'characteristic_uuid': str(characteristic.uuid),
                        'data_length': len(data),
                        'raw_hex': hex_data,
                        'raw_ascii': ''.join(chr(b) if 32 <= b <= 126 else '.' for b in data)
                    }
                    self.captured_frames.append(frame)
                    logger.info(f"📊 Frame captured from {device.name}: {len(data)} bytes")
                    logger.info(f"    Hex: {hex_data[:50]}{'...' if len(hex_data) > 50 else ''}")
                    # Emit rules:
                    # 1. If --print-all and bridge_mode: always print hex_data
                    # 2. Else only when classified as potential telegram
                    is_potential = self.is_potential_wmbus_telegram(hex_data)
                    if is_potential:
                        logger.info("🎯 POTENTIAL wM-Bus TELEGRAM DETECTED!")
                        logger.info(f"    Full hex: {hex_data}")
                    if self.bridge_mode and self._stdout_active and (self.print_all or is_potential):
                        try:
                            print(hex_data, flush=True)
                        except BrokenPipeError:
                            # Downstream pipe closed (e.g. head). Silence further emissions.
                            if self._stdout_active:  # first occurrence
                                self._stdout_active = False
                                logger.warning("🔇 Downstream consumer closed pipe (BrokenPipe). Suppressing further stdout frames.")
                        except Exception as pe:  # Other print-related issues
                            logger.error(f"❌ Stdout emission error: {pe}")
                except BrokenPipeError:
                    # Should be caught above, but guard just in case
                    if self._stdout_active:
                        self._stdout_active = False
                        logger.warning("🔇 Downstream consumer closed pipe (BrokenPipe) during processing. Emission disabled.")
                except Exception as e:
                    logger.error(f"❌ Notification processing error: {e}")
            await client.start_notify(characteristic.uuid, notification_handler)
            logger.info(f"✅ Notifications started for {characteristic.uuid}")
        except Exception as e:
            logger.error(f"❌ Failed to setup notifications: {e}")

    def is_potential_wmbus_telegram(self, hex_data: str) -> bool:
        if len(hex_data) < 20:
            return False
        if hex_data.startswith('FBFBFBF0'):
            return True
        if hex_data.startswith(('44', '68', '2E', '1E', '23', '4D')):
            return True
        for pattern in ['2D2C', '2C37', '2324', '11A5', '1592', '5B4', '601']:
            if pattern in hex_data:
                return True
        return False

    async def monitor_devices(self, duration: float = 300.0) -> None:
        if duration == 0:
            logger.info("⏱️  Starting monitoring (infinite duration)")
        else:
            logger.info(f"⏱️  Starting monitoring for {duration} seconds")
        logger.info("📡 Listening for wM-Bus telegrams...")
        start = asyncio.get_event_loop().time()
        try:
            while True:
                if duration != 0 and (asyncio.get_event_loop().time() - start) >= duration:
                    break
                await asyncio.sleep(1)
                elapsed = int(asyncio.get_event_loop().time() - start)
                if elapsed % 30 == 0:
                    logger.info(f"📊 Status: {len(self.captured_frames)} frames captured, {len(self.connected_devices)} devices connected; elapsed={elapsed}s")
        except KeyboardInterrupt:
            logger.info("⏹️  Monitoring stopped by user")

    async def disconnect_all(self) -> None:
        for address, client in list(self.connected_devices.items()):
            try:
                await client.disconnect()
                logger.info(f"🔌 Disconnected from {address}")
            except Exception as e:
                logger.error(f"❌ Disconnect error: {e}")
        self.connected_devices.clear()

    def save_results(self, filename: str = "wmbus_capture.json") -> None:
        results = {
            'capture_timestamp': datetime.utcnow().isoformat(),
            'discovered_devices': [
                {'name': d.name, 'address': d.address} for d in self.discovered_devices.values()
            ],
            'total_frames': len(self.captured_frames),
            'frames': self.captured_frames
        }
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"💾 Results saved to {filename}")
        logger.info(f"📊 Total frames captured: {len(self.captured_frames)}")
        potential = [f for f in self.captured_frames if self.is_potential_wmbus_telegram(f['raw_hex'])]
        if potential:
            logger.info(f"🎯 Potential wM-Bus telegrams: {len(potential)}")
            for t in potential[:5]:
                logger.info(f"    📡 {t['device_name']}: {t['raw_hex'][:100]}...")
        else:
            logger.info("⚠️  No potential wM-Bus telegrams detected")

async def main():
    parser = argparse.ArgumentParser(description="Bluetooth wM-Bus telegram capture")
    parser.add_argument('--scan-time', type=float, default=20.0, help='Scan duration seconds (default 20)')
    parser.add_argument('--duration', type=float, default=60.0, help='Monitoring duration seconds (0=infinite)')
    parser.add_argument('--bridge-mode', action='store_true', help='Emit potential telegram hex to stdout')
    parser.add_argument('--print-all', action='store_true', help='With --bridge-mode, emit ALL notification hex (no filtering)')
    parser.add_argument('--name-contains', type=str, help='Substring added as a match pattern')
    parser.add_argument('--pattern', action='append', help='Additional regex pattern(s) (repeatable)')
    parser.add_argument('--auto-connect', action='store_true', help='Reserved compatibility (no-op)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()
    if args.debug:
        logger.setLevel(logging.DEBUG)
    # Use raw print early (prior to object) then safe prints via instance
    print("🚀 Starting wM-Bus Bluetooth Capture")
    print("=" * 50)
    capture = WMBusBluetoothCapture(patterns=args.pattern, name_contains=args.name_contains, bridge_mode=args.bridge_mode, print_all=args.print_all)
    try:
        devices = await capture.scan_for_devices(timeout=args.scan_time)
        if not devices:
            capture._safe_print("❌ No target devices found")
            capture._safe_print("\n💡 Tips:\n   - Ensure Bluetooth devices are powered and advertising\n   - Adjust --scan-time\n   - Add --pattern / --name-contains\n   - Enable --debug for verbose output")
            return
        capture._safe_print(f"\n📱 Found {len(devices)} target devices:")
        for d in devices:
            capture._safe_print(f"   - {d.name or 'Unknown'} ({d.address})")
        capture._safe_print("\n🔗 Connecting to devices...")
        for d in devices:
            await capture.connect_to_device(d)
        if not capture.connected_devices:
            capture._safe_print("❌ No successful connections")
            return
        capture._safe_print(f"✅ Connected to {len(capture.connected_devices)} devices")
        capture._safe_print("\n📡 Monitoring for wM-Bus telegrams...")
        if args.duration == 0:
            capture._safe_print("⏱️  Monitoring indefinitely (Ctrl+C to stop)")
        else:
            capture._safe_print(f"⏱️  Will monitor for {args.duration} seconds (Ctrl+C to stop early)")
        await capture.monitor_devices(duration=args.duration)
    except KeyboardInterrupt:
        capture._safe_print("\n⏹️  Stopped by user")
    except Exception as e:
        capture._safe_print(f"\n❌ Error: {e}")
    finally:
        await capture.disconnect_all()
        capture.save_results()
        capture._safe_print("\n📊 Capture Summary:")
        capture._safe_print(f"   Devices found: {len(capture.discovered_devices)}")
        capture._safe_print(f"   Devices connected: {len(capture.connected_devices)}")
        capture._safe_print(f"   Frames captured: {len(capture.captured_frames)}")

if __name__ == "__main__":
    asyncio.run(main())
