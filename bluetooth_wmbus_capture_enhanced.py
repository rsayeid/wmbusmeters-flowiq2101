#!/usr/bin/env python3
"""
Enhanced Bluetooth wM-Bus Telegram Capture
Based on bluetooth_wmbus_capture.py with improved feature                # Display telegram header
                print(f"\n🔶 TELEGRAM #{i+1}/{len(self.telegram_buffer)} - {formatted_time} - {device}")
                print(f"📋 Size: {len(hex_data)//2} bytes")- Interactive timeout period selection
- Comprehensive data display
- Detailed logging of all events and data
- Enhanced visualization of captured telegrams

For FlowIQ2101 meters and VW1871 concentrators
"""

import asyncio
import logging
import sys
import os
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
import re
import json
import time

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

# Configure logging
LOG_FILE = "bluetooth_wmbus_capture_enhanced.log"
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class EnhancedWMBusBluetoothCapture:
    """Enhanced wM-Bus Bluetooth telegram capture service"""
    
    def __init__(self, verbose=True):
        self.discovered_devices: Dict[str, BLEDevice] = {}
        self.connected_devices: Dict[str, BleakClient] = {}
        self.captured_frames: List[Dict] = []
        self.telegram_buffer: List[Dict] = []  # Buffer for collecting telegrams
        self.buffer_size = 5  # Max telegrams before pausing
        self.pending_display = False  # Flag for telegram display
        self.last_display_time = time.time()
        self.display_interval = 2.0  # Seconds between automatic displays
        self.scanning = False
        self.verbose = verbose
        self.start_time = datetime.now()
        
        # Device patterns from previous implementation
        self.device_patterns = [
            r'FlowIQ.*',
            r'FIQ.*', 
            r'Kamstrup.*',
            r'Multical.*',
            r'MC21.*',
            r'VW.*',      # Added for VW1871
            r'.*66501566.*',  # Kamstrup device ID
            r'.*250111.*'     # VW1871 device ID
        ]
        
        # Service UUIDs that might contain wM-Bus data
        self.service_uuids = [
            '0000180f-0000-1000-8000-00805f9b34fb',  # Battery Service
            '6e400001-b5a3-f393-e0a9-e50e24dcca9e',  # Nordic UART Service
            '0000ffe0-0000-1000-8000-00805f9b34fb',  # Generic UART
            '0000fff0-0000-1000-8000-00805f9b34fb'   # Custom service
        ]
        
        logger.info("🔧 Enhanced wM-Bus Bluetooth Capture initialized")
        logger.info(f"📱 Device patterns: {self.device_patterns}")
        logger.info(f"🔌 Service UUIDs: {self.service_uuids}")
        logger.info(f"📝 Log file: {os.path.abspath(LOG_FILE)}")
        
        self.print_header()
        
    def print_header(self):
        """Print initialization header"""
        print("\n" + "=" * 80)
        print("📡 ENHANCED wM-Bus BLUETOOTH CAPTURE SERVICE")
        print("=" * 80)
        print("🔍 For FlowIQ2101 meters and VW1871 concentrators")
        print("📝 Logging to:", os.path.abspath(LOG_FILE))
        print("⏱️  Started at:", self.start_time.strftime("%Y-%m-%d %H:%M:%S"))
        print("=" * 80 + "\n")
    
    def display_telegram_buffer(self, force=False):
        """Display buffered telegrams with paging"""
        current_time = time.time()
        
        # Check if it's time to display or if we're forcing display
        if (len(self.telegram_buffer) >= self.buffer_size or 
            (force and len(self.telegram_buffer) > 0) or
            (len(self.telegram_buffer) > 0 and current_time - self.last_display_time > self.display_interval)):
            
            # Clear screen for better visibility
            os.system('clear' if os.name == 'posix' else 'cls')
            
            # Display header with stats
            print("\n" + "=" * 80)
            print(f"📡 wM-Bus TELEGRAMS ({len(self.telegram_buffer)} new, {len(self.captured_frames)} total)")
            print("=" * 80)
            
            # Display each telegram in the buffer
            for i, telegram in enumerate(self.telegram_buffer):
                hex_data = telegram.get('raw_hex', '')
                device = telegram.get('device_name', 'Unknown')
                timestamp = telegram.get('timestamp', '')
                formatted_time = datetime.fromisoformat(timestamp).strftime('%H:%M:%S') if timestamp else ''
                
                # Format hex data for display
                formatted_hex = ' '.join([hex_data[i:i+2] for i in range(0, len(hex_data), 2)])
                
                # Display telegram header
                print(f"\n� TELEGRAM #{i+1}/{len(self.telegram_buffer)} - {formatted_time} - {device}")
                print(f"📋 Size: {len(hex_data)//2} bytes")
                
                # Show data in blocks for better readability
                print("-" * 80)
                for j in range(0, len(formatted_hex), 48):
                    block = formatted_hex[j:j+48]
                    print(f"{block}")
                print("-" * 80)
                
                # Display any telegram info
                if 'info' in telegram:
                    print("TELEGRAM INFO:")
                    for key, value in telegram['info'].items():
                        print(f"  {key}: {value}")
                    print("-" * 80)
            
            # If buffer is large, prompt user to continue
            if len(self.telegram_buffer) >= 3:
                try:
                    input("Press Enter to continue...")
                except KeyboardInterrupt:
                    print("\nDisplay interrupted.")
            
            # Clear the buffer
            self.telegram_buffer = []
            self.last_display_time = current_time
            self.pending_display = False
            
    def add_to_telegram_buffer(self, telegram_data, info):
        """Add a telegram to the buffer with its analysis info"""
        # Create a complete telegram record
        telegram_record = telegram_data.copy()
        telegram_record['info'] = info
        
        # Add to buffer
        self.telegram_buffer.append(telegram_record)
        self.pending_display = True
        
        # If we've reached buffer size, display immediately
        if len(self.telegram_buffer) >= self.buffer_size:
            self.display_telegram_buffer()
    
    def is_target_device(self, device: BLEDevice, adv_data: Optional[AdvertisementData] = None) -> bool:
        """Check if device is a potential wM-Bus device"""
        device_name = device.name or ""
        device_address = device.address
        
        # Debug log to see all device names
        logger.debug(f"Found device: {device_name} ({device_address})")
        
        # First check common FlowIQ and VW1871 device names
        if any([
            "flowiq" in device_name.lower(),
            "kamstrup" in device_name.lower(),
            "vw" in device_name.lower(),
            "250111" in device_address or "250111" in device_name,
            "66501566" in device_address or "66501566" in device_name
        ]):
            logger.info(f"🎯 Found specific target device by name: {device_name}")
            return True
        
        # Check name patterns
        for pattern in self.device_patterns:
            if re.match(pattern, device_name, re.IGNORECASE):
                logger.info(f"📡 Found target device by pattern '{pattern}': {device_name}")
                return True
        
        # Check if device has relevant services
        if adv_data and hasattr(adv_data, 'service_uuids') and adv_data.service_uuids:
            for uuid in self.service_uuids:
                if uuid.lower() in [s.lower() for s in adv_data.service_uuids]:
                    logger.info(f"🔌 Found target device by service UUID: {device_name}")
                    return True
        
        # Check for any device with "66501566" or "250111" in name (our specific devices)
        if "66501566" in device_name or "250111" in device_name:
            logger.info(f"🎯 Found specific target device: {device_name}")
            return True
            
        return False
    
    async def scan_for_devices(self, timeout: float = 30.0) -> List[BLEDevice]:
        """Scan for Bluetooth devices"""
        self.scanning = True
        
        logger.info(f"🔍 Starting Bluetooth scan (timeout: {timeout}s)")
        print(f"\n🔍 Scanning for Bluetooth devices for {timeout} seconds...")
        print("   Looking for FlowIQ meters, Kamstrup devices, and VW1871 concentrators")
        
        # Progress display
        scan_start = time.time()
        
        def detection_callback(device: BLEDevice, adv_data: AdvertisementData):
            if self.is_target_device(device, adv_data):
                if device.address not in self.discovered_devices:
                    self.discovered_devices[device.address] = device
                    logger.info(f"📱 Target device discovered: {device.name or 'Unknown'} ({device.address})")
                    # Log advertisement data for debugging
                    logger.debug(f"📦 Advertisement data for {device.address}: {adv_data}")
                    
                    # Live discovery feedback
                    elapsed = time.time() - scan_start
                    print(f"   [{elapsed:.1f}s] 📱 Found: {device.name or 'Unknown'} ({device.address})")
        
        try:
            scanner = BleakScanner(detection_callback=detection_callback)
            await scanner.start()
            
            # Show progress while scanning
            for i in range(int(timeout)):
                if not self.scanning:
                    break
                await asyncio.sleep(1)
                # Print a dot every second to show progress
                if i % 5 == 0 and self.verbose:
                    devices_found = len(self.discovered_devices)
                    print(f"   Scanning... {i}/{int(timeout)}s - Found {devices_found} devices", end="\r")
            
            await scanner.stop()
            
            print("\n")  # Clear the progress line
            logger.info(f"✅ Scan complete. Found {len(self.discovered_devices)} target devices")
            print(f"✅ Scan complete. Found {len(self.discovered_devices)} target devices")
            return list(self.discovered_devices.values())
            
        except Exception as e:
            logger.error(f"❌ Scan error: {e}")
            print(f"❌ Scan error: {e}")
            return []
        finally:
            self.scanning = False
    
    async def connect_to_device(self, device: BLEDevice) -> Optional[BleakClient]:
        """Connect to a Bluetooth device"""
        try:
            logger.info(f"🔗 Connecting to: {device.name or 'Unknown'} ({device.address})")
            print(f"🔗 Connecting to: {device.name or 'Unknown'} ({device.address})...")
            
            client = BleakClient(device, timeout=15.0)
            await client.connect()
            
            if client.is_connected:
                self.connected_devices[device.address] = client
                logger.info(f"✅ Connected to {device.address}")
                print(f"✅ Connected to {device.name or 'Unknown'}")
                
                # Display detailed device info when connected
                details = {
                    "name": device.name,
                    "address": device.address,
                    "details": str(device.details) if hasattr(device, 'details') else "N/A"
                }
                logger.debug(f"📱 Device details: {details}")
                
                await self.discover_services(client, device)
                return client
            else:
                logger.warning(f"❌ Failed to connect to {device.address}")
                print(f"❌ Failed to connect to {device.name or 'Unknown'}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Connection error for {device.address}: {e}")
            print(f"❌ Connection error for {device.name or 'Unknown'}: {e}")
            return None
    
    async def discover_services(self, client: BleakClient, device: BLEDevice) -> None:
        """Discover services and setup notifications"""
        try:
            services = client.services
            logger.info(f"🔍 Discovering services for {device.address}")
            print(f"🔍 Discovering services for {device.name or 'Unknown'}...")
            
            characteristic_count = 0
            notify_count = 0
            
            for service in services:
                logger.info(f"  📋 Service: {service.uuid}")
                
                for char in service.characteristics:
                    characteristic_count += 1
                    props = char.properties
                    logger.info(f"    🔧 Characteristic: {char.uuid} (Properties: {props})")
                    
                    # Setup notifications for characteristics that might provide data
                    if "notify" in props or "indicate" in props:
                        notify_count += 1
                        logger.info(f"📡 Setting up notifications for: {char.uuid}")
                        await self.setup_notifications(client, char, device)
            
            service_count = sum(1 for _ in services)
            print(f"  Found {service_count} services, {characteristic_count} characteristics")
            print(f"  Listening on {notify_count} notification-enabled characteristics")
            
        except Exception as e:
            logger.error(f"❌ Service discovery error: {e}")
            print(f"❌ Service discovery error: {e}")
    
    async def setup_notifications(self, client: BleakClient, characteristic, device: BLEDevice):
        """Setup notifications for data capture"""
        try:
            # Use an async function to properly handle Bleak's notification callback
            async def notification_handler(char, data: bytearray):
                """Handle incoming notification data"""
                try:
                    hex_data = data.hex().upper()
                    timestamp = datetime.utcnow().isoformat()
                    
                    frame = {
                        'timestamp': timestamp,
                        'device_name': device.name or 'Unknown',
                        'device_address': device.address,
                        'characteristic_uuid': str(characteristic.uuid),
                        'data_length': len(data),
                        'raw_hex': hex_data,
                        'raw_ascii': ''.join(chr(b) if 32 <= b <= 126 else '.' for b in data)
                    }
                    
                    self.captured_frames.append(frame)
                    
                    # Enhanced logging of all received data
                    logger.debug(f"📊 Raw data received: {hex_data}")
                    logger.info(f"📊 Frame captured from {device.name}: {len(data)} bytes")
                    
                    # Check if this looks like a wM-Bus telegram and analyze it
                    if self.is_potential_wmbus_telegram(hex_data):
                        # Log that we found a potential wM-Bus telegram
                        logger.info("🎯 POTENTIAL wM-Bus TELEGRAM DETECTED!")
                        logger.info(f"    Full hex: {hex_data}")
                        
                        # Analyze the telegram
                        telegram_info = self.analyze_wmbus_telegram(hex_data, device)
                        
                        # Add to our buffer system for structured display
                        self.add_to_telegram_buffer(frame, telegram_info)
                        
                        # Output to stdout for bridge mode
                        if len(sys.argv) > 1 and sys.argv[1] == '--bridge-mode':
                            print(hex_data, flush=True)  # Output pure hex for bridge
                    else:
                        # For non-wMBus data, just log it without printing to console
                        # This prevents flooding the console with non-relevant data
                        logger.debug(f"Data from {device.name or 'Unknown'}: {len(data)} bytes")
                        logger.debug(f"Hex: {hex_data}")
                    
                except Exception as e:
                    logger.error(f"❌ Notification processing error: {e}")
                    print(f"❌ Notification processing error: {e}")
            
            await client.start_notify(characteristic.uuid, notification_handler)
            logger.info(f"✅ Notifications started for {characteristic.uuid}")
            
        except Exception as e:
            logger.error(f"❌ Failed to setup notifications: {e}")
            print(f"❌ Failed to setup notifications: {e}")
    
    def analyze_wmbus_telegram(self, hex_data: str, device: Optional[Union[str, BLEDevice]]) -> Dict[str, str]:
        """Attempt to extract meaningful information from the telegram"""
        # Create a dictionary to store telegram information
        telegram_info = {}
        
        # Get device name if device is a BLEDevice object, otherwise use as is
        try:
            device_name = device.name if isinstance(device, BLEDevice) else device
        except:
            device_name = None
        
        # Extract common wM-Bus telegram fields if present
        # Note: This is a simplified analysis and may need adjustment for specific meters
        
        # Check for Kamstrup manufacturer code (2D2C)
        if "2D2C" in hex_data:
            telegram_info["Manufacturer"] = "Kamstrup (2D2C)"
            logger.info("  📊 Manufacturer: Kamstrup (2D2C)")
        
        # Try to extract meter ID if present in common format
        # Example pattern: last 4 bytes before 2D2C might be meter ID in some formats
        kamstrup_id_match = re.search(r'([0-9A-F]{8})2D2C', hex_data)
        if kamstrup_id_match:
            meter_id = kamstrup_id_match.group(1)
            telegram_info["Meter ID"] = meter_id
            logger.info(f"  📊 Possible Meter ID: {meter_id}")
        
        # Check for specific VW1871 header
        if hex_data.startswith('FBFBFBF0'):
            telegram_info["Device Type"] = "VW1871 Concentrator"
            logger.info("  📊 VW1871 Concentrator frame detected")
        
        # Check for transmission pattern (7 compact + 1 full frame)
        # Simplified check based on frame size
        if device_name and isinstance(device_name, str) and ("VW" in device_name or "250111" in device_name):
            if len(hex_data) < 40:  # Likely a compact frame
                telegram_info["Frame Type"] = "Compact frame"
                logger.info("  📊 Appears to be a compact frame")
            else:  # Likely a full frame
                telegram_info["Frame Type"] = "Full frame"
                logger.info("  📊 Appears to be a full frame")
        
        # FlowIQ2101 specific information
        if "74493770" in hex_data:
            telegram_info["Device"] = "FlowIQ2101 (74493770)"
            
        return telegram_info
    
    def is_potential_wmbus_telegram(self, hex_data: str) -> bool:
        """Check if hex data looks like a wM-Bus telegram"""
        # Basic checks for wM-Bus telegram structure
        if len(hex_data) < 20:  # Too short
            return False
            
        # VW1871 format: starts with FBFBFBF0 header
        if hex_data.startswith('FBFBFBF0'):
            return True
            
        # Standard wM-Bus telegrams: start with length byte followed by specific patterns
        # Common patterns: 44, 68 (frame start), or other length indicators
        if hex_data.startswith(('44', '68', '2E', '1E', '23', '4D')):
            return True
            
        # Check for manufacturer codes that appear in telegrams
        # Common manufacturer codes in hex: 2D2C (Kamstrup), 2C37, 2324 (Hydrometer), etc.
        wmbus_patterns = ['2D2C', '2C37', '2324', '11A5', '1592', '5B4', '601']
        for pattern in wmbus_patterns:
            if pattern in hex_data:
                return True
                
        return False
    
    async def monitor_devices(self, duration: float = 300.0) -> None:
        """Monitor connected devices for wM-Bus telegrams"""
        logger.info(f"⏱️  Starting monitoring for {duration} seconds")
        print(f"\n⏱️  Monitoring for {duration} seconds")
        print("📡 Listening for wM-Bus telegrams...")
        print("   Press Ctrl+C to stop monitoring early")
        
        start_time = asyncio.get_event_loop().time()
        end_time = start_time + duration
        frames_last_update = 0
        last_buffer_check = time.time()
        
        try:
            # Display a countdown timer
            while (asyncio.get_event_loop().time() < end_time):
                remaining = end_time - asyncio.get_event_loop().time()
                await asyncio.sleep(1)
                
                # Check if we should display any buffered telegrams
                current_time = time.time()
                if current_time - last_buffer_check >= 10:  # Check every 10 seconds
                    if self.pending_display:
                        self.display_telegram_buffer(force=True)
                    last_buffer_check = current_time
                
                # Update status every 10 seconds
                if int(remaining) % 10 == 0:
                    logger.info(f"📊 Status: {len(self.captured_frames)} frames captured, "
                              f"{len(self.connected_devices)} devices connected")
                    
                    # Only show status update if we received new frames
                    if self.verbose or len(self.captured_frames) > frames_last_update:
                        time_left = int(remaining)
                        hours, remainder = divmod(time_left, 3600)
                        minutes, seconds = divmod(remainder, 60)
                        time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"
                        
                        # Calculate new frames since last update
                        new_frames = len(self.captured_frames) - frames_last_update
                        if new_frames > 0:
                            print(f"\n⏱️  Status: +{new_frames} new frames | Total: {len(self.captured_frames)} | Time left: {time_str}")
                            frames_last_update = len(self.captured_frames)
        
        except KeyboardInterrupt:
            logger.info("⏹️  Monitoring stopped by user")
            print("\n⏹️  Monitoring stopped by user")
        except Exception as e:
            logger.error(f"❌ Monitoring error: {e}")
        
        finally:
            # Display any remaining buffered telegrams
            if self.pending_display:
                self.display_telegram_buffer(force=True)
                
            # Show monitoring summary
            elapsed = asyncio.get_event_loop().time() - start_time
            logger.info(f"✅ Monitoring completed after {elapsed:.1f} seconds")
            print(f"\n✅ Monitoring completed after {elapsed:.1f} seconds")
            print(f"📊 Captured {len(self.captured_frames)} frames from {len(self.connected_devices)} devices")
    
    async def disconnect_all(self) -> None:
        """Disconnect all devices"""
        print("\n🔌 Disconnecting devices...")
        
        for address, client in list(self.connected_devices.items()):
            try:
                await client.disconnect()
                logger.info(f"🔌 Disconnected from {address}")
                print(f"  ✓ Disconnected from {address}")
            except Exception as e:
                logger.error(f"❌ Disconnect error: {e}")
                print(f"  ✗ Error disconnecting from {address}: {e}")
        
        self.connected_devices.clear()
    
    def save_results(self, filename: str = "wmbus_capture_enhanced.json") -> None:
        """Save captured data to file"""
        results = {
            'capture_timestamp': datetime.utcnow().isoformat(),
            'capture_duration': (datetime.now() - self.start_time).total_seconds(),
            'discovered_devices': [
                {
                    'name': device.name,
                    'address': device.address
                } for device in self.discovered_devices.values()
            ],
            'total_frames': len(self.captured_frames),
            'frames': self.captured_frames
        }
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"💾 Results saved to {filename}")
        print(f"\n💾 Results saved to {os.path.abspath(filename)}")
        
        # Count potential telegrams
        potential_telegrams = [f for f in self.captured_frames 
                             if self.is_potential_wmbus_telegram(f['raw_hex'])]
        
        print(f"📊 Total frames captured: {len(self.captured_frames)}")
        print(f"🎯 Potential wM-Bus telegrams identified: {len(potential_telegrams)}")
        
        if potential_telegrams:
            logger.info(f"🎯 Potential wM-Bus telegrams: {len(potential_telegrams)}")
            print("\n📡 TELEGRAM SUMMARY:")
            
            # Group by device
            by_device = {}
            for telegram in potential_telegrams:
                device = telegram['device_name']
                if device not in by_device:
                    by_device[device] = []
                by_device[device].append(telegram)
            
            # Show summary by device
            for device, telegrams in by_device.items():
                print(f"  📱 {device}: {len(telegrams)} telegrams")
                # Show first 3 telegram excerpts
                for i, telegram in enumerate(telegrams[:3]):
                    hex_data = telegram['raw_hex']
                    print(f"     {i+1}. {hex_data[:40]}...")
            
            print(f"\nUse the saved JSON file for detailed analysis: {filename}")
        else:
            logger.info("⚠️  No potential wM-Bus telegrams detected")
            print("\n⚠️  No potential wM-Bus telegrams detected")


async def main():
    """Main function with interactive features"""
    parser = argparse.ArgumentParser(description='Enhanced wM-Bus Bluetooth Capture')
    parser.add_argument('--timeout', type=float, help='Monitoring timeout in seconds')
    parser.add_argument('--scan-time', type=float, default=20.0, help='Device scan time in seconds')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('--bridge-mode', action='store_true', help='Run in bridge mode (output raw hex)')
    parser.add_argument('--output', type=str, default="wmbus_capture_enhanced.json", 
                      help='Output file for captured data')
    parser.add_argument('--all-devices', action='store_true', help='Connect to all discovered devices, not just wmbus targets')
    parser.add_argument('--device-address', type=str, help='Connect to a specific device by address')
    parser.add_argument('--fallback', action='store_true', help='Fallback to connect to any nearby devices if no target devices found')
    args = parser.parse_args()
    
    print("🚀 Starting Enhanced wM-Bus Bluetooth Capture")
    print("=" * 50)
    
    # Interactive timeout selection if not provided via args
    timeout = args.timeout
    if timeout is None:
        try:
            timeout_input = input("⏱️  Enter monitoring duration in seconds [300]: ")
            timeout = float(timeout_input) if timeout_input.strip() else 300.0
        except ValueError:
            timeout = 300.0
            print("⚠️  Invalid input, using default of 300 seconds (5 minutes)")
            
    capture = EnhancedWMBusBluetoothCapture(verbose=args.verbose)
    
    try:
        # Step 1: Scan for devices
        all_devices = []
        target_devices = []
        
        # If specific device address provided, connect to it directly
        if args.device_address:
            print(f"🎯 Will connect to specific device: {args.device_address}")
            # Create a dummy BLEDevice with the provided address
            from bleak.backends.device import BLEDevice
            specific_device = BLEDevice(args.device_address, args.device_address, {})
            target_devices = [specific_device]
        else:
            # Scan for devices
            print(f"\n🔍 Scanning for Bluetooth devices for {args.scan_time} seconds...")
            
            # Most reliable approach is to use the discover method directly
            try:
                all_devices = await BleakScanner.discover(timeout=args.scan_time)
                print(f"✅ Discovered {len(all_devices)} Bluetooth devices")
            except Exception as e:
                logger.error(f"❌ Scanner error: {e}")
                print(f"❌ Scanner error: {e}")
                # Fallback for older Bleak versions
                scanner = BleakScanner()
                await scanner.start()
                await asyncio.sleep(args.scan_time)
                await scanner.stop()
                
                # Try to access discovered devices based on Bleak version
                try:
                    # Different Bleak versions store devices differently
                    all_devices = list(scanner.__dict__.get("_discovered_devices", {}).values())
                except:
                    print("⚠️ Could not retrieve discovered devices using standard methods")
                    logger.warning("Could not retrieve discovered devices using standard methods")
                    all_devices = []
            
            # Log all discovered devices for debugging
            print(f"\n📱 Found {len(all_devices)} Bluetooth devices")
            logger.info(f"Found {len(all_devices)} total Bluetooth devices")
            
            # Extract and print manufacturer data for debugging
            print("🔍 Analyzing device manufacturer data...")
            
            for i, device in enumerate(all_devices):
                is_target = capture.is_target_device(device, None)
                
                # Extract any manufacturer data for better identification
                manufacturer_info = ""
                try:
                    # Try to access manufacturer data if available in different Bleak versions
                    if hasattr(device, 'details') and device.details:
                        details_str = str(device.details)
                        if 'manufacturer_data' in details_str or 'ManufacturerData' in details_str:
                            manufacturer_info = " [Has manufacturer data]"
                        elif 'kCBAdvDataManufacturerData' in details_str:
                            manufacturer_info = " [Has manufacturer data (Core Bluetooth)]"
                except Exception as e:
                    logger.debug(f"Could not extract manufacturer data: {e}")
                
                # Provide detailed info in logs
                logger.info(f"Device {i+1}: {device.name or 'Unknown'} ({device.address}) - Target: {is_target}{manufacturer_info}")
                
                # Only show targets and devices with manufacturer data in console unless verbose
                show_device = args.verbose or is_target or manufacturer_info
                if show_device:
                    print(f"   {i+1}. {device.name or 'Unknown'} ({device.address}){' 🎯' if is_target else ''}{manufacturer_info}")
                
                # Save target devices and devices with manufacturer data that might be wM-Bus related
                if is_target or args.all_devices or "manufacturer" in manufacturer_info.lower():
                    target_devices.append(device)
                    capture.discovered_devices[device.address] = device
        
        # Handle no target devices found
        if not target_devices:
            print("❌ No target devices found")
            
            if args.fallback:
                print("\n🔄 Fallback mode: will connect to all nearby devices")
                print("   This may help discover devices that don't match target patterns")
                target_devices = all_devices[:5]  # Limit to first 5 devices to avoid overload
                print(f"   Will try {len(target_devices)} nearby devices")
            else:
                print("\n💡 Troubleshooting tips:")
                print("   - Ensure target Bluetooth devices are powered on and nearby")
                print("   - Check device names match expected patterns (FlowIQ, VW1871, etc.)")
                print("   - Try running with --fallback to connect to all nearby devices")
                print("   - Try running with sudo if needed for Bluetooth permissions")
                print("   - Try increasing scan time with --scan-time parameter")
                print("   - Try specifying a device address with --device-address")
                return
        
        print(f"\n🎯 Will connect to {len(target_devices)} devices:")
        for i, device in enumerate(target_devices):
            print(f"   {i+1}. {device.name or 'Unknown'} ({device.address})")
        
        # Step 2: Connect to devices
        print("\n🔗 Connecting to devices...")
        for device in target_devices:
            await capture.connect_to_device(device)
        
        if not capture.connected_devices:
            print("❌ No successful connections")
            return
        
        print(f"✅ Connected to {len(capture.connected_devices)} devices")
        
        # Step 3: Monitor for telegrams
        print("\n📡 Monitoring for wM-Bus telegrams...")
        print(f"⏱️  Will monitor for {timeout} seconds (press Ctrl+C to stop early)")
        
        await capture.monitor_devices(duration=timeout)
        
    except KeyboardInterrupt:
        print("\n⏹️  Stopped by user")
    
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        print(f"\n❌ Error: {e}")
    
    finally:
        # Cleanup
        if hasattr(capture, 'disconnect_all'):
            await capture.disconnect_all()
        if hasattr(capture, 'save_results'):
            capture.save_results(filename=args.output)
        
        print("\n📊 CAPTURE SUMMARY:")
        print(f"   Devices found: {len(capture.discovered_devices)}")
        print(f"   Devices connected: {len(capture.connected_devices)}")
        print(f"   Frames captured: {len(capture.captured_frames)}")
        print(f"   Log file: {os.path.abspath(LOG_FILE)}")
        print(f"   Data file: {os.path.abspath(args.output)}")
        print("\n🔍 Next steps: Analyze the captured data with wmbusmeters")
        print("   Example: wmbusmeters --analyze wmbus_capture_enhanced.json")
        
        print("\n⚠️  SERVICE CLEANUP")
        print("   Remember to run cleanup commands if needed:")
        print("   pkill -f \"bluetooth.*bridge\" && pkill -f \"bluetooth.*capture\"")


if __name__ == "__main__":
    asyncio.run(main())
