#!/usr/bin/env python3
"""
VW1871-250111 to wmbusmeters Bridge
Captures telegrams from VW1871 Bluetooth device and feeds to wmbusmeters
"""

import asyncio
import subprocess
import json
import sys
from datetime import datetime

try:
    import bleak
    from bleak import BleakScanner, BleakClient
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData
except ImportError:
    print("Error: bleak library not available. Install with: pip install bleak")
    sys.exit(1)

class FlowIQ2101Bridge:
    """Bridge VW1871 Bluetooth data to wmbusmeters for FlowIQ 2101 processing"""
    
    def __init__(self):
        self.device_address = "F0F41E39-111C-1E4B-018D-4363539FF186"  # VW1871-250111
        self.device_name = "VW1871-250111"
        self.client = None
        self.telegram_count = 0
        
        # wmbusmeters configuration for FlowIQ 2101
        self.wmbusmeters_config = {
            'name': 'FlowIQ2101',
            'driver': 'iperl',
            'id': '74493770',
            'key': ''  # Encryption key needed for full decoding
        }
    
    async def connect_to_device(self):
        """Connect to the VW1871 device"""
        try:
            print(f"🔗 Connecting to {self.device_name}...")
            self.client = BleakClient(self.device_address, timeout=10.0)
            await self.client.connect()
            
            if self.client.is_connected:
                print(f"✅ Connected to {self.device_name}")
                await self.setup_notifications()
                return True
            else:
                print(f"❌ Failed to connect to {self.device_name}")
                return False
                
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False
    
    async def setup_notifications(self):
        """Setup notifications for telegram capture"""
        try:
            # Find the characteristic that provides wM-Bus data
            # Based on our previous capture, this appears to be:
            telegram_char_uuid = "49535343-1e4d-4bd9-ba61-23c647249616"
            
            def telegram_handler(sender: int, data: bytearray):
                """Process incoming telegram data"""
                try:
                    hex_data = data.hex().upper()
                    
                    # Check if this looks like a wM-Bus telegram (based on our analysis)
                    if len(hex_data) > 40 and "442D2C" in hex_data:  # Kamstrup manufacturer code
                        self.process_telegram(hex_data)
                
                except Exception as e:
                    print(f"❌ Telegram processing error: {e}")
            
            await self.client.start_notify(telegram_char_uuid, telegram_handler)
            print(f"📡 Listening for FlowIQ 2101 telegrams...")
            
        except Exception as e:
            print(f"❌ Failed to setup notifications: {e}")
    
    def process_telegram(self, hex_data):
        """Process and parse telegram with wmbusmeters"""
        try:
            # Extract the wM-Bus portion (remove framing bytes)
            if hex_data.startswith("FBFBFBF0"):
                # Remove preamble
                telegram = hex_data[8:]
            else:
                telegram = hex_data
            
            # Look for the start of the actual wM-Bus frame
            # Based on our analysis, the telegram starts around the manufacturer code
            mfct_pos = telegram.find("442D2C")
            if mfct_pos > 0:
                # Extract from length byte before manufacturer code
                start_pos = max(0, mfct_pos - 2)
                telegram = telegram[start_pos:]
            
            # Remove any trailing framing
            if "FEFE" in telegram:
                telegram = telegram[:telegram.find("FEFE")]
            
            self.telegram_count += 1
            timestamp = datetime.now().isoformat()
            
            print(f"\n📊 Telegram {self.telegram_count} captured at {timestamp}")
            print(f"Raw hex: {telegram}")
            
            # Parse with wmbusmeters
            self.parse_with_wmbusmeters(telegram)
            
        except Exception as e:
            print(f"❌ Telegram processing error: {e}")
    
    def parse_with_wmbusmeters(self, telegram):
        """Parse telegram using wmbusmeters"""
        try:
            cmd = [
                "./build/wmbusmeters",
                "--format=json",
                "--silent",
                "stdin",
                self.wmbusmeters_config['name'],
                self.wmbusmeters_config['driver'],
                self.wmbusmeters_config['id'],
                self.wmbusmeters_config['key']
            ]
            
            # Run wmbusmeters with the telegram
            result = subprocess.run(
                cmd,
                input=telegram + "\n",
                text=True,
                capture_output=True,
                timeout=10
            )
            
            if result.stdout.strip():
                try:
                    # Parse JSON output
                    data = json.loads(result.stdout.strip())
                    print(f"✅ Parsed: {data}")
                    
                    # Extract key information
                    if 'total_m3' in data:
                        print(f"   Water consumption: {data['total_m3']} m³")
                    if 'timestamp' in data:
                        print(f"   Meter timestamp: {data['timestamp']}")
                        
                except json.JSONDecodeError:
                    print(f"📄 Output: {result.stdout.strip()}")
            
            if result.stderr and "failed decryption" in result.stderr:
                print("🔐 Telegram is encrypted - encryption key needed for full data")
            elif result.stderr:
                print(f"⚠️  Parse issues: {result.stderr.strip()}")
                
        except subprocess.TimeoutExpired:
            print("⏰ wmbusmeters timeout")
        except Exception as e:
            print(f"❌ Parse error: {e}")
    
    async def monitor(self, duration=300):
        """Monitor for telegrams"""
        try:
            print(f"⏱️  Monitoring for {duration} seconds...")
            print("💡 Press Ctrl+C to stop")
            
            start_time = asyncio.get_event_loop().time()
            
            while (asyncio.get_event_loop().time() - start_time) < duration:
                await asyncio.sleep(1)
                
                # Status update every 30 seconds
                elapsed = int(asyncio.get_event_loop().time() - start_time)
                if elapsed % 30 == 0 and elapsed > 0:
                    print(f"📊 Status: {self.telegram_count} telegrams processed after {elapsed}s")
        
        except KeyboardInterrupt:
            print("\n⏹️  Monitoring stopped by user")
    
    async def disconnect(self):
        """Disconnect from device"""
        if self.client and self.client.is_connected:
            await self.client.disconnect()
            print(f"🔌 Disconnected from {self.device_name}")

async def main():
    """Main function"""
    print("🚀 FlowIQ 2101 Bridge via VW1871-250111")
    print("=" * 50)
    
    bridge = FlowIQ2101Bridge()
    
    try:
        # Connect to VW1871
        if not await bridge.connect_to_device():
            return
        
        # Monitor for telegrams
        await bridge.monitor(duration=120)  # 2 minutes
        
    except KeyboardInterrupt:
        print("\n⏹️  Stopped by user")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    finally:
        # Cleanup
        await bridge.disconnect()
        
        print(f"\n📊 Session Summary:")
        print(f"   Telegrams captured: {bridge.telegram_count}")
        print(f"   Device: {bridge.device_name}")
        print(f"   FlowIQ 2101 ID: {bridge.wmbusmeters_config['id']}")

if __name__ == "__main__":
    asyncio.run(main())
