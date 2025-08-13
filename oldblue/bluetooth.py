"""
Universal Bluetooth Service

Handles Bluetooth Low Energy (BLE) device discovery, connection management,
and real-time frame capture from meter devices
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Callable, Set, Union
import json
from pathlib import Path
import re

try:
    import bleak
    from bleak import BleakScanner, BleakClient
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData
    BLEAK_AVAILABLE = True
    
    # Type aliases for actual bleak types
    BluetoothDevice = BLEDevice
    BluetoothClient = BleakClient
    BluetoothScanner = BleakScanner
    BluetoothAdvertisementData = AdvertisementData
    
except ImportError:
    BLEAK_AVAILABLE = False
    # Fallback types when bleak is not available
    BluetoothDevice = Any
    BluetoothClient = Any
    BluetoothScanner = Any
    BluetoothAdvertisementData = Any

try:
    from core.models import FrameData, FrameStatus, MeterInfo, SystemConfig
    from services.configurator import MeterConfigurator
except ImportError:
    # Handle relative import issues
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from core.models import FrameData, FrameStatus, MeterInfo, SystemConfig
    from services.configurator import MeterConfigurator


class BluetoothServiceError(Exception):
    """Custom exception for Bluetooth service errors"""
    pass


class BluetoothService:
    """
    Universal Bluetooth service for meter device discovery and frame capture
    """
    
    def __init__(self, config: SystemConfig, logger: Optional[logging.Logger] = None):
        """
        Initialize Bluetooth service
        
        Args:
            config: System configuration
            logger: Optional logger instance
        """
        if not BLEAK_AVAILABLE:
            raise BluetoothServiceError("Bleak library not available. Install with: pip install bleak")
        
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        
        # Service state
        self.discovered_devices: Dict[str, BluetoothDevice] = {}
        self.connected_devices: Dict[str, BluetoothClient] = {}
        self.target_meters: Dict[str, MeterInfo] = {}
        self.frame_buffer: List[FrameData] = []
        self.scanning = False
        self.collecting = False
        
        # Bluetooth configuration
        self.bt_config = self._get_bluetooth_config()
        
        # Frame processing callback
        self.frame_callback: Optional[Callable[[FrameData], None]] = None
        
        # Statistics
        self.stats = {
            'scan_sessions': 0,
            'devices_discovered': 0,
            'connections_attempted': 0,
            'successful_connections': 0,
            'frames_captured': 0,
            'last_scan_time': None,
            'last_frame_time': None
        }
        
        self.logger.info("Bluetooth service initialized")
    
    def _get_bluetooth_config(self) -> Dict[str, Any]:
        """Get Bluetooth configuration with defaults"""
        default_config = {
            'scan_timeout': 30.0,
            'scan_interval': 5.0,
            'connection_timeout': 10.0,
            'retry_attempts': 3,
            'retry_delay': 2.0,
            'frame_timeout': 60.0,
            'buffer_size': 1000,
            'device_name_patterns': [
                r'FlowIQ.*',
                r'FIQ.*',
                r'Kamstrup.*',
                r'Multical.*',
                r'MC21.*'
            ],
            'service_uuids': [
                # Common Kamstrup/meter UUIDs (add as discovered)
                '0000180f-0000-1000-8000-00805f9b34fb',  # Battery Service
                '6e400001-b5a3-f393-e0a9-e50e24dcca9e'   # Nordic UART Service
            ],
            'auto_connect': True,
            'continuous_scan': False
        }
        
        # Merge with user configuration
        user_config = self.config.bluetooth_config
        return {**default_config, **user_config}
    
    def set_target_meters(self, meters: Dict[str, MeterInfo]) -> None:
        """
        Set target meters for discovery and connection
        
        Args:
            meters: Dictionary of serial -> MeterInfo
        """
        self.target_meters = meters.copy()
        self.logger.info(f"Target meters set: {list(meters.keys())}")
    
    def load_targets_from_configurator(self, configurator: MeterConfigurator, 
                                     serials: Optional[List[str]] = None) -> None:
        """
        Load target meters from configurator
        
        Args:
            configurator: Meter configurator instance
            serials: Optional list of specific serials to target
        """
        available_meters = configurator.get_available_meters()
        
        if serials:
            # Filter to specific serials
            self.target_meters = {
                serial: meter for serial, meter in available_meters.items()
                if serial in serials
            }
        else:
            # Use all available meters
            self.target_meters = available_meters
        
        self.logger.info(f"Loaded {len(self.target_meters)} target meters from configurator")
    
    def set_frame_callback(self, callback: Callable[[FrameData], None]) -> None:
        """
        Set callback function for frame processing
        
        Args:
            callback: Function to call when frames are captured
        """
        self.frame_callback = callback
        self.logger.info("Frame callback registered")
    
    async def scan_for_devices(self, timeout: Optional[float] = None) -> List[BluetoothDevice]:
        """
        Scan for Bluetooth devices
        
        Args:
            timeout: Scan timeout in seconds
            
        Returns:
            List of discovered devices
        """
        if not BLEAK_AVAILABLE:
            raise BluetoothServiceError("Bluetooth scanning requires bleak library")
        
        timeout = timeout or self.bt_config['scan_timeout']
        self.scanning = True
        self.stats['scan_sessions'] += 1
        
        try:
            self.logger.info(f"Starting Bluetooth scan (timeout: {timeout}s)")
            
            def detection_callback(device: BluetoothDevice, advertisement_data: BluetoothAdvertisementData):
                """Handle device detection"""
                if self._is_target_device(device, advertisement_data):
                    if device.address not in self.discovered_devices:
                        self.discovered_devices[device.address] = device
                        self.stats['devices_discovered'] += 1
                        self.logger.info(f"Target device discovered: {device.name or 'Unknown'} ({device.address})")
            
            # Start scanning
            scanner = BleakScanner(detection_callback=detection_callback)
            await scanner.start()
            
            # Wait for timeout
            await asyncio.sleep(timeout)
            
            # Stop scanning
            await scanner.stop()
            
            self.stats['last_scan_time'] = datetime.utcnow()
            self.logger.info(f"Scan complete. Discovered {len(self.discovered_devices)} target devices")
            
            return list(self.discovered_devices.values())
            
        except Exception as e:
            self.logger.error(f"Bluetooth scan error: {e}")
            raise BluetoothServiceError(f"Scan failed: {e}")
        
        finally:
            self.scanning = False
    
    def _is_target_device(self, device: BluetoothDevice, advertisement_data: BluetoothAdvertisementData) -> bool:
        """
        Check if device is a target meter device
        
        Args:
            device: BLE device
            advertisement_data: Advertisement data
            
        Returns:
            True if device matches target criteria
        """
        # Check device name patterns
        device_name = getattr(device, 'name', None) or ""
        for pattern in self.bt_config['device_name_patterns']:
            if re.match(pattern, device_name, re.IGNORECASE):
                return True
        
        # Check if device name contains target serial numbers
        for serial in self.target_meters.keys():
            if serial in device_name:
                return True
            # Check last 6 digits for shorter names
            if len(serial) >= 6 and serial[-6:] in device_name:
                return True
        
        # Check service UUIDs
        advertised_services = getattr(advertisement_data, 'service_uuids', None) or []
        for uuid in self.bt_config['service_uuids']:
            if uuid.lower() in [s.lower() for s in advertised_services]:
                return True
        
        # Check manufacturer data for Kamstrup
        manufacturer_data = getattr(advertisement_data, 'manufacturer_data', None) or {}
        # Kamstrup manufacturer ID (if known)
        kamstrup_ids = [0x02E5]  # Example - adjust based on actual manufacturer ID
        for mfg_id in kamstrup_ids:
            if mfg_id in manufacturer_data:
                return True
        
        return False
    
    async def connect_to_device(self, device: BluetoothDevice) -> Optional[BluetoothClient]:
        """
        Connect to a Bluetooth device
        
        Args:
            device: BLE device to connect to
            
        Returns:
            Connected client or None if failed
        """
        if not BLEAK_AVAILABLE:
            raise BluetoothServiceError("Bluetooth connection requires bleak library")
        
        self.stats['connections_attempted'] += 1
        
        try:
            device_name = getattr(device, 'name', None) or 'Unknown'
            device_address = getattr(device, 'address', 'Unknown')
            self.logger.info(f"Connecting to device: {device_name} ({device_address})")
            
            client = BleakClient(device, timeout=self.bt_config['connection_timeout'])
            
            await client.connect()
            
            if client.is_connected:
                self.connected_devices[device_address] = client
                self.stats['successful_connections'] += 1
                self.logger.info(f"Successfully connected to {device_address}")
                
                # Discover services and characteristics
                await self._discover_services(client, device)
                
                return client
            else:
                self.logger.warning(f"Failed to connect to {device_address}")
                return None
                
        except Exception as e:
            self.logger.error(f"Connection error for {device_address}: {e}")
            return None
    
    async def _discover_services(self, client: BluetoothClient, device: BluetoothDevice) -> None:
        """
        Discover services and characteristics for a connected device
        
        Args:
            client: Connected BLE client
            device: BLE device
        """
        try:
            device_address = getattr(device, 'address', 'Unknown')
            services = client.services
            self.logger.debug(f"Device {device_address} services:")
            
            for service in services:
                self.logger.debug(f"  Service: {service.uuid}")
                
                for char in service.characteristics:
                    props = char.properties
                    self.logger.debug(f"    Characteristic: {char.uuid} (Properties: {props})")
                    
                    # Look for notify characteristics that might provide frame data
                    if "notify" in props or "indicate" in props:
                        self.logger.info(f"Found notification characteristic: {char.uuid}")
                        # Start notifications if this looks like frame data
                        await self._setup_frame_notifications(client, char)
            
        except Exception as e:
            device_address = getattr(device, 'address', 'Unknown')
            self.logger.error(f"Service discovery error for {device_address}: {e}")
    
    async def _setup_frame_notifications(self, client: BluetoothClient, characteristic) -> None:
        """
        Setup notifications for frame data characteristics
        
        Args:
            client: Connected BLE client
            characteristic: Characteristic to monitor
        """
        try:
            def notification_handler(sender: int, data: bytearray):
                """Handle incoming notification data"""
                try:
                    # Convert raw data to frame
                    client_address = getattr(client, 'address', 'Unknown')
                    frame = self._process_raw_notification(data, client_address)
                    if frame:
                        self.frame_buffer.append(frame)
                        self.stats['frames_captured'] += 1
                        self.stats['last_frame_time'] = datetime.utcnow()
                        
                        # Call callback if registered
                        if self.frame_callback:
                            try:
                                self.frame_callback(frame)
                            except Exception as e:
                                self.logger.error(f"Frame callback error: {e}")
                        
                        self.logger.debug(f"Frame captured from {client_address}: {len(data)} bytes")
                
                except Exception as e:
                    self.logger.error(f"Notification processing error: {e}")
            
            # Start notifications
            await client.start_notify(characteristic.uuid, notification_handler)
            client_address = getattr(client, 'address', 'Unknown')
            self.logger.info(f"Started notifications for {characteristic.uuid} on {client_address}")
            
        except Exception as e:
            self.logger.error(f"Failed to setup notifications: {e}")
    
    def _process_raw_notification(self, data: bytearray, device_address: str) -> Optional[FrameData]:
        """
        Process raw notification data into frame data
        
        Args:
            data: Raw notification data
            device_address: Device Bluetooth address
            
        Returns:
            FrameData object or None if invalid
        """
        try:
            # Convert to hex string
            hex_data = data.hex().upper()
            
            # Basic validation - minimum frame length
            if len(hex_data) < 20:  # Minimum reasonable frame size
                return None
            
            # Try to extract device address/serial from hex data
            # This is device/protocol specific and may need adjustment
            meter_serial = self._extract_meter_serial(hex_data, device_address)
            
            # Create frame data
            frame = FrameData(
                raw_hex=hex_data,
                timestamp=datetime.utcnow(),
                device_address=device_address,
                meter_serial=meter_serial,
                frame_length=len(data),
                status=FrameStatus.RAW,  # Use RAW instead of CAPTURED
                metadata={
                    'source': 'bluetooth',
                    'device_address': device_address,
                    'data_length': len(data)
                }
            )
            
            return frame
            
        except Exception as e:
            self.logger.error(f"Frame processing error: {e}")
            return None
    
    def _extract_meter_serial(self, hex_data: str, device_address: str) -> Optional[str]:
        """
        Extract meter serial number from hex data
        
        Args:
            hex_data: Frame hex data
            device_address: Device Bluetooth address
            
        Returns:
            Meter serial number or None
        """
        # Try to match with target meters
        for serial, meter_info in self.target_meters.items():
            # Check if this frame could be from this meter
            # This is a simplified check - real implementation would parse the frame
            if len(hex_data) > 20:  # Basic validation
                return serial
        
        # Fallback - use device address mapping
        return device_address.replace(':', '')[-8:]  # Last 8 chars as pseudo-serial
    
    async def connect_to_all_discovered(self) -> List[BluetoothClient]:
        """
        Connect to all discovered target devices
        
        Returns:
            List of connected clients
        """
        clients = []
        
        for device in self.discovered_devices.values():
            device_address = getattr(device, 'address', 'Unknown')
            if device_address not in self.connected_devices:
                client = await self.connect_to_device(device)
                if client:
                    clients.append(client)
                    
                # Small delay between connections
                await asyncio.sleep(1.0)
        
        self.logger.info(f"Connected to {len(clients)} devices")
        return clients
    
    async def start_continuous_collection(self, scan_interval: Optional[float] = None) -> None:
        """
        Start continuous device scanning and frame collection
        
        Args:
            scan_interval: Interval between scans in seconds
        """
        scan_interval = scan_interval or self.bt_config['scan_interval']
        self.collecting = True
        
        self.logger.info(f"Starting continuous collection (scan interval: {scan_interval}s)")
        
        try:
            while self.collecting:
                # Scan for new devices
                await self.scan_for_devices()
                
                # Connect to new discoveries if auto-connect enabled
                if self.bt_config['auto_connect']:
                    await self.connect_to_all_discovered()
                
                # Wait for next scan
                await asyncio.sleep(scan_interval)
                
        except asyncio.CancelledError:
            self.logger.info("Continuous collection cancelled")
        except Exception as e:
            self.logger.error(f"Continuous collection error: {e}")
        finally:
            self.collecting = False
            await self.disconnect_all()
    
    async def stop_continuous_collection(self) -> None:
        """Stop continuous collection"""
        self.collecting = False
        self.logger.info("Stopping continuous collection")
    
    async def disconnect_device(self, device_address: str) -> None:
        """
        Disconnect from a specific device
        
        Args:
            device_address: Device Bluetooth address
        """
        if device_address in self.connected_devices:
            client = self.connected_devices[device_address]
            try:
                await client.disconnect()
                del self.connected_devices[device_address]
                self.logger.info(f"Disconnected from {device_address}")
            except Exception as e:
                self.logger.error(f"Disconnect error for {device_address}: {e}")
    
    async def disconnect_all(self) -> None:
        """Disconnect from all connected devices"""
        for device_address in list(self.connected_devices.keys()):
            await self.disconnect_device(device_address)
    
    def get_frame_buffer(self, clear_after_read: bool = False) -> List[FrameData]:
        """
        Get captured frames from buffer
        
        Args:
            clear_after_read: Whether to clear buffer after reading
            
        Returns:
            List of captured frames
        """
        frames = self.frame_buffer.copy()
        
        if clear_after_read:
            self.frame_buffer.clear()
        
        return frames
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get service statistics"""
        return {
            **self.stats,
            'discovered_devices': len(self.discovered_devices),
            'connected_devices': len(self.connected_devices),
            'buffer_size': len(self.frame_buffer),
            'target_meters': len(self.target_meters)
        }
    
    def export_captured_data(self, output_path: str, format: str = 'json') -> None:
        """
        Export captured frame data
        
        Args:
            output_path: Output file path
            format: Export format (json, csv)
        """
        output_path_obj = Path(output_path)
        
        if format.lower() == 'json':
            data = {
                'export_timestamp': datetime.utcnow().isoformat(),
                'statistics': self.get_statistics(),
                'frames': [frame.to_dict() for frame in self.frame_buffer]
            }
            
            with open(output_path_obj, 'w') as f:
                json.dump(data, f, indent=2)
        
        elif format.lower() == 'csv':
            import csv
            
            with open(output_path_obj, 'w', newline='') as f:
                if self.frame_buffer:
                    writer = csv.DictWriter(f, fieldnames=[
                        'timestamp', 'device_address', 'meter_serial',
                        'frame_length', 'status', 'raw_hex'
                    ])
                    writer.writeheader()
                    
                    for frame in self.frame_buffer:
                        row = frame.to_dict()
                        # Simplify for CSV
                        row.pop('metadata', None)
                        writer.writerow(row)
        
        self.logger.info(f"Exported {len(self.frame_buffer)} frames to {output_path}")


# Example usage and testing functions
async def test_bluetooth_scan(timeout: float = 30.0) -> List[str]:
    """Test Bluetooth scanning functionality"""
    from ..core.models import SystemConfig
    
    config = SystemConfig()
    service = BluetoothService(config)
    
    try:
        devices = await service.scan_for_devices(timeout)
        device_info = []
        
        for device in devices:
            device_name = getattr(device, 'name', None) or 'Unknown'
            device_address = getattr(device, 'address', 'Unknown')
            info = f"{device_name} ({device_address})"
            device_info.append(info)
            print(f"Found: {info}")
        
        return device_info
        
    except BluetoothServiceError as e:
        print(f"Bluetooth error: {e}")
        return []


async def monitor_specific_meters(serials: List[str], duration: float = 300.0) -> List[FrameData]:
    """Monitor specific meters for a duration"""
    from ..core.models import SystemConfig, MeterInfo, MeterType
    
    # Create mock meter info for testing
    meters = {}
    for serial in serials:
        meters[serial] = MeterInfo(
            serial_number=serial,
            hex_key="00112233445566778899AABBCCDDEEFF",  # Mock key
            meter_type=MeterType.FLOWIQ_2101
        )
    
    config = SystemConfig()
    service = BluetoothService(config)
    service.set_target_meters(meters)
    
    # Frame collection callback
    captured_frames = []
    
    def frame_handler(frame: FrameData):
        captured_frames.append(frame)
        print(f"Frame captured: {frame.meter_serial} at {frame.timestamp}")
    
    service.set_frame_callback(frame_handler)
    
    try:
        # Start monitoring
        collection_task = asyncio.create_task(service.start_continuous_collection())
        
        # Wait for duration
        await asyncio.sleep(duration)
        
        # Stop monitoring
        await service.stop_continuous_collection()
        collection_task.cancel()
        
        print(f"Monitoring complete. Captured {len(captured_frames)} frames")
        return captured_frames
        
    except Exception as e:
        print(f"Monitoring error: {e}")
        return captured_frames

import asyncio
import logging
import signal
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Callable, Set
import json
from pathlib import Path
import re

try:
    import bleak
    from bleak import BleakScanner, BleakClient
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData
    BLEAK_AVAILABLE = True
except ImportError:
    BLEAK_AVAILABLE = False
    # Define placeholder types when bleak is not available
    class BLEDevice:
        pass
    class BleakClient:
        pass
    class BleakScanner:
        pass
    class AdvertisementData:
        pass

try:
    from core.models import FrameData, FrameStatus, MeterInfo, SystemConfig
except ImportError:
    # Handle relative import issues
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from core.models import FrameData, FrameStatus, MeterInfo, SystemConfig
from .configurator import MeterConfigurator


class BluetoothServiceError(Exception):
    """Custom exception for Bluetooth service errors"""
    pass


class BluetoothService:
    """
    Universal Bluetooth service for meter device discovery and frame capture
    """
    
    def __init__(self, config: SystemConfig, logger: Optional[logging.Logger] = None):
        """
        Initialize Bluetooth service
        
        Args:
            config: System configuration
            logger: Optional logger instance
        """
        if not BLEAK_AVAILABLE:
            raise BluetoothServiceError("Bleak library not available. Install with: pip install bleak")
        
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        
        # Service state
        self.discovered_devices: Dict[str, BLEDevice] = {}
        self.connected_devices: Dict[str, BleakClient] = {}
        self.target_meters: Dict[str, MeterInfo] = {}
        self.frame_buffer: List[FrameData] = []
        self.scanning = False
        self.collecting = False
        
        # Bluetooth configuration
        self.bt_config = self._get_bluetooth_config()
        
        # Frame processing callback
        self.frame_callback: Optional[Callable[[FrameData], None]] = None
        
        # Statistics
        self.stats = {
            'scan_sessions': 0,
            'devices_discovered': 0,
            'connections_attempted': 0,
            'successful_connections': 0,
            'frames_captured': 0,
            'last_scan_time': None,
            'last_frame_time': None
        }
        
        self.logger.info("Bluetooth service initialized")
    
    def _get_bluetooth_config(self) -> Dict[str, Any]:
        """Get Bluetooth configuration with defaults"""
        default_config = {
            'scan_timeout': 30.0,
            'scan_interval': 5.0,
            'connection_timeout': 10.0,
            'retry_attempts': 3,
            'retry_delay': 2.0,
            'frame_timeout': 60.0,
            'buffer_size': 1000,
            'device_name_patterns': [
                r'FlowIQ.*',
                r'FIQ.*',
                r'Kamstrup.*',
                r'Multical.*',
                r'MC21.*'
            ],
            'service_uuids': [
                # Common Kamstrup/meter UUIDs (add as discovered)
                '0000180f-0000-1000-8000-00805f9b34fb',  # Battery Service
                '6e400001-b5a3-f393-e0a9-e50e24dcca9e'   # Nordic UART Service
            ],
            'auto_connect': True,
            'continuous_scan': False
        }
        
        # Merge with user configuration
        user_config = self.config.bluetooth_config
        return {**default_config, **user_config}
    
    def set_target_meters(self, meters: Dict[str, MeterInfo]) -> None:
        """
        Set target meters for discovery and connection
        
        Args:
            meters: Dictionary of serial -> MeterInfo
        """
        self.target_meters = meters.copy()
        self.logger.info(f"Target meters set: {list(meters.keys())}")
    
    def load_targets_from_configurator(self, configurator: MeterConfigurator, 
                                     serials: Optional[List[str]] = None) -> None:
        """
        Load target meters from configurator
        
        Args:
            configurator: Meter configurator instance
            serials: Optional list of specific serials to target
        """
        available_meters = configurator.get_available_meters()
        
        if serials:
            # Filter to specific serials
            self.target_meters = {
                serial: meter for serial, meter in available_meters.items()
                if serial in serials
            }
        else:
            # Use all available meters
            self.target_meters = available_meters
        
        self.logger.info(f"Loaded {len(self.target_meters)} target meters from configurator")
    
    def set_frame_callback(self, callback: Callable[[FrameData], None]) -> None:
        """
        Set callback function for frame processing
        
        Args:
            callback: Function to call when frames are captured
        """
        self.frame_callback = callback
        self.logger.info("Frame callback registered")
    
    async def scan_for_devices(self, timeout: Optional[float] = None) -> List[BLEDevice]:
        """
        Scan for Bluetooth devices
        
        Args:
            timeout: Scan timeout in seconds
            
        Returns:
            List of discovered devices
        """
        timeout = timeout or self.bt_config['scan_timeout']
        self.scanning = True
        self.stats['scan_sessions'] += 1
        
        try:
            self.logger.info(f"Starting Bluetooth scan (timeout: {timeout}s)")
            
            def detection_callback(device: BLEDevice, advertisement_data: AdvertisementData):
                """Handle device detection"""
                if self._is_target_device(device, advertisement_data):
                    if device.address not in self.discovered_devices:
                        self.discovered_devices[device.address] = device
                        self.stats['devices_discovered'] += 1
                        self.logger.info(f"Target device discovered: {device.name or 'Unknown'} ({device.address})")
            
            # Start scanning
            scanner = BleakScanner(detection_callback=detection_callback)
            await scanner.start()
            
            # Wait for timeout
            await asyncio.sleep(timeout)
            
            # Stop scanning
            await scanner.stop()
            
            self.stats['last_scan_time'] = datetime.utcnow()
            self.logger.info(f"Scan complete. Discovered {len(self.discovered_devices)} target devices")
            
            return list(self.discovered_devices.values())
            
        except Exception as e:
            self.logger.error(f"Bluetooth scan error: {e}")
            raise BluetoothServiceError(f"Scan failed: {e}")
        
        finally:
            self.scanning = False
    
    def _is_target_device(self, device: BLEDevice, advertisement_data: AdvertisementData) -> bool:
        """
        Check if device is a target meter device
        
        Args:
            device: BLE device
            advertisement_data: Advertisement data
            
        Returns:
            True if device matches target criteria
        """
        # Check device name patterns
        device_name = device.name or ""
        for pattern in self.bt_config['device_name_patterns']:
            if re.match(pattern, device_name, re.IGNORECASE):
                return True
        
        # Check if device name contains target serial numbers
        for serial in self.target_meters.keys():
            if serial in device_name:
                return True
            # Check last 6 digits for shorter names
            if len(serial) >= 6 and serial[-6:] in device_name:
                return True
        
        # Check service UUIDs
        advertised_services = advertisement_data.service_uuids or []
        for uuid in self.bt_config['service_uuids']:
            if uuid.lower() in [s.lower() for s in advertised_services]:
                return True
        
        # Check manufacturer data for Kamstrup
        manufacturer_data = advertisement_data.manufacturer_data or {}
        # Kamstrup manufacturer ID (if known)
        kamstrup_ids = [0x02E5]  # Example - adjust based on actual manufacturer ID
        for mfg_id in kamstrup_ids:
            if mfg_id in manufacturer_data:
                return True
        
        return False
    
    async def connect_to_device(self, device: BLEDevice) -> Optional[BleakClient]:
        """
        Connect to a Bluetooth device
        
        Args:
            device: BLE device to connect to
            
        Returns:
            Connected client or None if failed
        """
        self.stats['connections_attempted'] += 1
        
        try:
            self.logger.info(f"Connecting to device: {device.name or 'Unknown'} ({device.address})")
            
            client = BleakClient(device, timeout=self.bt_config['connection_timeout'])
            
            await client.connect()
            
            if client.is_connected:
                self.connected_devices[device.address] = client
                self.stats['successful_connections'] += 1
                self.logger.info(f"Successfully connected to {device.address}")
                
                # Discover services and characteristics
                await self._discover_services(client, device)
                
                return client
            else:
                self.logger.warning(f"Failed to connect to {device.address}")
                return None
                
        except Exception as e:
            self.logger.error(f"Connection error for {device.address}: {e}")
            return None
    
    async def _discover_services(self, client: BleakClient, device: BLEDevice) -> None:
        """
        Discover services and characteristics for a connected device
        
        Args:
            client: Connected BLE client
            device: BLE device
        """
        try:
            services = client.services
            self.logger.debug(f"Device {device.address} services:")
            
            for service in services:
                self.logger.debug(f"  Service: {service.uuid}")
                
                for char in service.characteristics:
                    props = char.properties
                    self.logger.debug(f"    Characteristic: {char.uuid} (Properties: {props})")
                    
                    # Look for notify characteristics that might provide frame data
                    if "notify" in props or "indicate" in props:
                        self.logger.info(f"Found notification characteristic: {char.uuid}")
                        # Start notifications if this looks like frame data
                        await self._setup_frame_notifications(client, char)
            
        except Exception as e:
            self.logger.error(f"Service discovery error for {device.address}: {e}")
    
    async def _setup_frame_notifications(self, client: BleakClient, characteristic) -> None:
        """
        Setup notifications for frame data characteristics
        
        Args:
            client: Connected BLE client
            characteristic: Characteristic to monitor
        """
        try:
            def notification_handler(sender: int, data: bytearray):
                """Handle incoming notification data"""
                try:
                    # Convert raw data to frame
                    frame = self._process_raw_notification(data, client.address)
                    if frame:
                        self.frame_buffer.append(frame)
                        self.stats['frames_captured'] += 1
                        self.stats['last_frame_time'] = datetime.utcnow()
                        
                        # Call callback if registered
                        if self.frame_callback:
                            try:
                                self.frame_callback(frame)
                            except Exception as e:
                                self.logger.error(f"Frame callback error: {e}")
                        
                        self.logger.debug(f"Frame captured from {client.address}: {len(data)} bytes")
                
                except Exception as e:
                    self.logger.error(f"Notification processing error: {e}")
            
            # Start notifications
            await client.start_notify(characteristic.uuid, notification_handler)
            self.logger.info(f"Started notifications for {characteristic.uuid} on {client.address}")
            
        except Exception as e:
            self.logger.error(f"Failed to setup notifications: {e}")
    
    def _process_raw_notification(self, data: bytearray, device_address: str) -> Optional[FrameData]:
        """
        Process raw notification data into frame data
        
        Args:
            data: Raw notification data
            device_address: Device Bluetooth address
            
        Returns:
            FrameData object or None if invalid
        """
        try:
            # Convert to hex string
            hex_data = data.hex().upper()
            
            # Basic validation - minimum frame length
            if len(hex_data) < 20:  # Minimum reasonable frame size
                return None
            
            # Try to extract device address/serial from hex data
            # This is device/protocol specific and may need adjustment
            meter_serial = self._extract_meter_serial(hex_data, device_address)
            
            # Create frame data
            frame = FrameData(
                raw_hex=hex_data,
                timestamp=datetime.utcnow(),
                device_address=device_address,
                meter_serial=meter_serial,
                frame_length=len(data),
                status=FrameStatus.CAPTURED,
                metadata={
                    'source': 'bluetooth',
                    'device_address': device_address,
                    'data_length': len(data)
                }
            )
            
            return frame
            
        except Exception as e:
            self.logger.error(f"Frame processing error: {e}")
            return None
    
    def _extract_meter_serial(self, hex_data: str, device_address: str) -> Optional[str]:
        """
        Extract meter serial number from hex data
        
        Args:
            hex_data: Frame hex data
            device_address: Device Bluetooth address
            
        Returns:
            Meter serial number or None
        """
        # Try to match with target meters
        for serial, meter_info in self.target_meters.items():
            # Check if this frame could be from this meter
            # This is a simplified check - real implementation would parse the frame
            if len(hex_data) > 20:  # Basic validation
                return serial
        
        # Fallback - use device address mapping
        return device_address.replace(':', '')[-8:]  # Last 8 chars as pseudo-serial
    
    async def connect_to_all_discovered(self) -> List[BleakClient]:
        """
        Connect to all discovered target devices
        
        Returns:
            List of connected clients
        """
        clients = []
        
        for device in self.discovered_devices.values():
            if device.address not in self.connected_devices:
                client = await self.connect_to_device(device)
                if client:
                    clients.append(client)
                    
                # Small delay between connections
                await asyncio.sleep(1.0)
        
        self.logger.info(f"Connected to {len(clients)} devices")
        return clients
    
    async def start_continuous_collection(self, scan_interval: Optional[float] = None) -> None:
        """
        Start continuous device scanning and frame collection
        
        Args:
            scan_interval: Interval between scans in seconds
        """
        scan_interval = scan_interval or self.bt_config['scan_interval']
        self.collecting = True
        
        self.logger.info(f"Starting continuous collection (scan interval: {scan_interval}s)")
        
        try:
            while self.collecting:
                # Scan for new devices
                await self.scan_for_devices()
                
                # Connect to new discoveries if auto-connect enabled
                if self.bt_config['auto_connect']:
                    await self.connect_to_all_discovered()
                
                # Wait for next scan
                await asyncio.sleep(scan_interval)
                
        except asyncio.CancelledError:
            self.logger.info("Continuous collection cancelled")
        except Exception as e:
            self.logger.error(f"Continuous collection error: {e}")
        finally:
            self.collecting = False
            await self.disconnect_all()
    
    async def stop_continuous_collection(self) -> None:
        """Stop continuous collection"""
        self.collecting = False
        self.logger.info("Stopping continuous collection")
    
    async def disconnect_device(self, device_address: str) -> None:
        """
        Disconnect from a specific device
        
        Args:
            device_address: Device Bluetooth address
        """
        if device_address in self.connected_devices:
            client = self.connected_devices[device_address]
            try:
                await client.disconnect()
                del self.connected_devices[device_address]
                self.logger.info(f"Disconnected from {device_address}")
            except Exception as e:
                self.logger.error(f"Disconnect error for {device_address}: {e}")
    
    async def disconnect_all(self) -> None:
        """Disconnect from all connected devices"""
        for device_address in list(self.connected_devices.keys()):
            await self.disconnect_device(device_address)
    
    def get_frame_buffer(self, clear_after_read: bool = False) -> List[FrameData]:
        """
        Get captured frames from buffer
        
        Args:
            clear_after_read: Whether to clear buffer after reading
            
        Returns:
            List of captured frames
        """
        frames = self.frame_buffer.copy()
        
        if clear_after_read:
            self.frame_buffer.clear()
        
        return frames
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get service statistics"""
        return {
            **self.stats,
            'discovered_devices': len(self.discovered_devices),
            'connected_devices': len(self.connected_devices),
            'buffer_size': len(self.frame_buffer),
            'target_meters': len(self.target_meters)
        }
    
    def export_captured_data(self, output_path: str, format: str = 'json') -> None:
        """
        Export captured frame data
        
        Args:
            output_path: Output file path
            format: Export format (json, csv)
        """
        output_path = Path(output_path)
        
        if format.lower() == 'json':
            data = {
                'export_timestamp': datetime.utcnow().isoformat(),
                'statistics': self.get_statistics(),
                'frames': [frame.to_dict() for frame in self.frame_buffer]
            }
            
            with open(output_path, 'w') as f:
                json.dump(data, f, indent=2)
        
        elif format.lower() == 'csv':
            import csv
            
            with open(output_path, 'w', newline='') as f:
                if self.frame_buffer:
                    writer = csv.DictWriter(f, fieldnames=[
                        'timestamp', 'device_address', 'meter_serial',
                        'frame_length', 'status', 'raw_hex'
                    ])
                    writer.writeheader()
                    
                    for frame in self.frame_buffer:
                        row = frame.to_dict()
                        # Simplify for CSV
                        row.pop('metadata', None)
                        writer.writerow(row)
        
        self.logger.info(f"Exported {len(self.frame_buffer)} frames to {output_path}")


# Example usage and testing functions
async def test_bluetooth_scan(timeout: float = 30.0) -> List[str]:
    """Test Bluetooth scanning functionality"""
    from ..core.models import SystemConfig
    
    config = SystemConfig()
    service = BluetoothService(config)
    
    try:
        devices = await service.scan_for_devices(timeout)
        device_info = []
        
        for device in devices:
            info = f"{device.name or 'Unknown'} ({device.address})"
            device_info.append(info)
            print(f"Found: {info}")
        
        return device_info
        
    except BluetoothServiceError as e:
        print(f"Bluetooth error: {e}")
        return []


async def monitor_specific_meters(serials: List[str], duration: float = 300.0) -> List[FrameData]:
    """Monitor specific meters for a duration"""
    from ..core.models import SystemConfig, MeterInfo, MeterType
    
    # Create mock meter info for testing
    meters = {}
    for serial in serials:
        meters[serial] = MeterInfo(
            serial_number=serial,
            hex_key="00112233445566778899AABBCCDDEEFF",  # Mock key
            meter_type=MeterType.FLOWIQ_2101
        )
    
    config = SystemConfig()
    service = BluetoothService(config)
    service.set_target_meters(meters)
    
    # Frame collection callback
    captured_frames = []
    
    def frame_handler(frame: FrameData):
        captured_frames.append(frame)
        print(f"Frame captured: {frame.meter_serial} at {frame.timestamp}")
    
    service.set_frame_callback(frame_handler)
    
    try:
        # Start monitoring
        collection_task = asyncio.create_task(service.start_continuous_collection())
        
        # Wait for duration
        await asyncio.sleep(duration)
        
        # Stop monitoring
        await service.stop_continuous_collection()
        collection_task.cancel()
        
        print(f"Monitoring complete. Captured {len(captured_frames)} frames")
        return captured_frames
        
    except Exception as e:
        print(f"Monitoring error: {e}")
        return captured_frames
