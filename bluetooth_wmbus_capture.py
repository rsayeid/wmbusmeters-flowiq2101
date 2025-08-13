#!/usr/bin/env python3
"""
Bluetooth wM-Bus Telegram Capture
Based on the previous oldblue implementation
Tests Bluetooth devices for wM-Bus telegram reception
"""

import asyncio
import logging
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional
import re
import json

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
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WMBusBluetoothCapture:
    """wM-Bus Bluetooth telegram capture service"""
    
    def __init__(self):
        self.discovered_devices: Dict[str, BLEDevice] = {}
        self.connected_devices: Dict[str, BleakClient] = {}
        self.captured_frames: List[Dict] = []
        self.scanning = False
        
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
        
        print("🔧 wM-Bus Bluetooth Capture initialized")
        print(f"📱 Device patterns: {len(self.device_patterns)}")
        print(f"🔌 Service UUIDs: {len(self.service_uuids)}")
    
    def is_target_device(self, device: BLEDevice, adv_data: AdvertisementData) -> bool:
        """Check if device is a potential wM-Bus device"""
        device_name = device.name or ""
        
        # Check name patterns
        for pattern in self.device_patterns:
            if re.match(pattern, device_name, re.IGNORECASE):
                logger.info(f"📡 Found target device by pattern '{pattern}': {device_name}")
                return True
        
        # Check if device has relevant services
        if hasattr(adv_data, 'service_uuids') and adv_data.service_uuids:
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
        """Connect to a Bluetooth device"""
        try:
            logger.info(f"🔗 Connecting to: {device.name or 'Unknown'} ({device.address})")
            
            client = BleakClient(device, timeout=10.0)
            await client.connect()
            
            if client.is_connected:
                self.connected_devices[device.address] = client
                logger.info(f"✅ Connected to {device.address}")
                await self.discover_services(client, device)
                return client
            else:
                logger.warning(f"❌ Failed to connect to {device.address}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Connection error for {device.address}: {e}")
            return None
    
    async def discover_services(self, client: BleakClient, device: BLEDevice) -> None:
        """Discover services and setup notifications"""
        try:
            services = client.services
            logger.info(f"🔍 Discovering services for {device.address}")
            
            for service in services:
                logger.info(f"  📋 Service: {service.uuid}")
                
                for char in service.characteristics:
                    props = char.properties
                    logger.info(f"    🔧 Characteristic: {char.uuid} (Properties: {props})")
                    
                    # Setup notifications for characteristics that might provide data
                    if "notify" in props or "indicate" in props:
                        logger.info(f"📡 Setting up notifications for: {char.uuid}")
                        await self.setup_notifications(client, char, device)
            
        except Exception as e:
            logger.error(f"❌ Service discovery error: {e}")
    
    async def setup_notifications(self, client: BleakClient, characteristic, device: BLEDevice):
        """Setup notifications for data capture"""
        try:
            def notification_handler(sender: int, data: bytearray):
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
                    
                    logger.info(f"📊 Frame captured from {device.name}: {len(data)} bytes")
                    logger.info(f"    Hex: {hex_data[:50]}{'...' if len(hex_data) > 50 else ''}")
                    
                    # Check if this looks like a wM-Bus telegram
                    if self.is_potential_wmbus_telegram(hex_data):
                        logger.info("🎯 POTENTIAL wM-Bus TELEGRAM DETECTED!")
                        logger.info(f"    Full hex: {hex_data}")
                    
                except Exception as e:
                    logger.error(f"❌ Notification processing error: {e}")
            
            await client.start_notify(characteristic.uuid, notification_handler)
            logger.info(f"✅ Notifications started for {characteristic.uuid}")
            
        except Exception as e:
            logger.error(f"❌ Failed to setup notifications: {e}")
    
    def is_potential_wmbus_telegram(self, hex_data: str) -> bool:
        """Check if hex data looks like a wM-Bus telegram"""
        # Basic checks for wM-Bus telegram structure
        if len(hex_data) < 20:  # Too short
            return False
            
        # wM-Bus telegrams often start with length byte followed by specific patterns
        # Common patterns: 44, 68 (frame start), or other length indicators
        if hex_data.startswith(('44', '68', '2E', '1E', '23', '4D')):
            return True
            
        # Check for manufacturer codes that appear in telegrams
        # Common manufacturer codes in hex: 2C37 (Kamstrup), 2324 (Hydrometer), etc.
        wmbus_patterns = ['2C37', '2324', '11A5', '1592', '5B4', '601']
        for pattern in wmbus_patterns:
            if pattern in hex_data:
                return True
                
        return False
    
    async def monitor_devices(self, duration: float = 300.0) -> None:
        """Monitor connected devices for wM-Bus telegrams"""
        logger.info(f"⏱️  Starting monitoring for {duration} seconds")
        logger.info("📡 Listening for wM-Bus telegrams...")
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            while (asyncio.get_event_loop().time() - start_time) < duration:
                await asyncio.sleep(1)
                
                # Log status every 30 seconds
                if int(asyncio.get_event_loop().time() - start_time) % 30 == 0:
                    logger.info(f"📊 Status: {len(self.captured_frames)} frames captured, "
                              f"{len(self.connected_devices)} devices connected")
        
        except KeyboardInterrupt:
            logger.info("⏹️  Monitoring stopped by user")
    
    async def disconnect_all(self) -> None:
        """Disconnect all devices"""
        for address, client in list(self.connected_devices.items()):
            try:
                await client.disconnect()
                logger.info(f"🔌 Disconnected from {address}")
            except Exception as e:
                logger.error(f"❌ Disconnect error: {e}")
        
        self.connected_devices.clear()
    
    def save_results(self, filename: str = "wmbus_capture.json") -> None:
        """Save captured data to file"""
        results = {
            'capture_timestamp': datetime.utcnow().isoformat(),
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
        logger.info(f"📊 Total frames captured: {len(self.captured_frames)}")
        
        # Show summary of potential telegrams
        potential_telegrams = [f for f in self.captured_frames 
                             if self.is_potential_wmbus_telegram(f['raw_hex'])]
        
        if potential_telegrams:
            logger.info(f"🎯 Potential wM-Bus telegrams: {len(potential_telegrams)}")
            for telegram in potential_telegrams[:5]:  # Show first 5
                logger.info(f"    📡 {telegram['device_name']}: {telegram['raw_hex'][:100]}...")
        else:
            logger.info("⚠️  No potential wM-Bus telegrams detected")


async def main():
    """Main function"""
    print("🚀 Starting wM-Bus Bluetooth Capture")
    print("=" * 50)
    
    capture = WMBusBluetoothCapture()
    
    try:
        # Step 1: Scan for devices
        devices = await capture.scan_for_devices(timeout=20.0)
        
        if not devices:
            print("❌ No target devices found")
            print("\n💡 Tips:")
            print("   - Ensure Bluetooth devices are paired and connected")
            print("   - Check device names match expected patterns")
            print("   - Try running with sudo if needed")
            return
        
        print(f"\n📱 Found {len(devices)} target devices:")
        for device in devices:
            print(f"   - {device.name or 'Unknown'} ({device.address})")
        
        # Step 2: Connect to devices
        print("\n🔗 Connecting to devices...")
        for device in devices:
            await capture.connect_to_device(device)
        
        if not capture.connected_devices:
            print("❌ No successful connections")
            return
        
        print(f"✅ Connected to {len(capture.connected_devices)} devices")
        
        # Step 3: Monitor for telegrams
        print("\n📡 Monitoring for wM-Bus telegrams...")
        print("⏱️  Will monitor for 60 seconds (press Ctrl+C to stop early)")
        
        await capture.monitor_devices(duration=60.0)
        
    except KeyboardInterrupt:
        print("\n⏹️  Stopped by user")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    finally:
        # Cleanup
        await capture.disconnect_all()
        capture.save_results()
        
        print("\n📊 Capture Summary:")
        print(f"   Devices found: {len(capture.discovered_devices)}")
        print(f"   Devices connected: {len(capture.connected_devices)}")
        print(f"   Frames captured: {len(capture.captured_frames)}")


if __name__ == "__main__":
    asyncio.run(main())
