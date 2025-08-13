#!/usr/bin/env python3
"""
Bluetooth to Serial Bridge for wM-Bus
Bridges Bluetooth wM-Bus data to a virtual serial port for wmbusmeters consumption
"""

import asyncio
import logging
import signal
import sys
import os
import pty
import threading
import time
import subprocess
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for more verbose output
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BluetoothToSerialBridge:
    def __init__(self):
        self.master_fd = None
        self.slave_fd = None
        self.slave_name = None
        self.bluetooth_process = None
        self.running = False
        
    def create_virtual_serial_port(self):
        """Create a virtual serial port pair"""
        try:
            self.master_fd, self.slave_fd = pty.openpty()
            self.slave_name = os.ttyname(self.slave_fd)
            logger.info(f"✓ Created virtual serial port: {self.slave_name}")
            return True
        except Exception as e:
            logger.error(f"✗ Failed to create virtual serial port: {e}")
            return False
    
    def start_bluetooth_capture(self):
        """Start the Bluetooth capture process"""
        try:
            import subprocess
            import os
            # Use virtual environment Python if available, fallback to system Python
            venv_python = "/Volumes/dev/space/wmblatest/wmbusmeters/.venv/bin/python"
            python_executable = venv_python if os.path.exists(venv_python) else sys.executable
            
            # Start the bluetooth capture script with unbuffered output
            cmd = [
                python_executable, 
                "-u",  # Unbuffered output
                "/Volumes/dev/space/wmblatest/wmbusmeters/bluetooth_wmbus_capture.py"
            ]
            
            self.bluetooth_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                text=True,
                bufsize=0,  # Unbuffered
                universal_newlines=True,
                env=dict(os.environ, PYTHONUNBUFFERED="1")  # Force unbuffered
            )
            
            logger.info("✓ Started Bluetooth capture process")
            return True
        except Exception as e:
            logger.error(f"✗ Failed to start Bluetooth capture: {e}")
            return False
    
    def bridge_data(self):
        """Bridge data from Bluetooth capture to serial port"""
        logger.info("🔄 Starting data bridge thread")
        try:
            while self.running and self.bluetooth_process and self.bluetooth_process.stdout:
                # Check if process is still alive
                if self.bluetooth_process.poll() is not None:
                    logger.warning("⚠️ Bluetooth process terminated")
                    break
                
                # Read line from bluetooth process with timeout
                try:
                    line = self.bluetooth_process.stdout.readline()
                    if not line:
                        time.sleep(0.1)
                        continue
                    
                    # Log all output for debugging
                    logger.debug(f"📥 Raw line: {line.strip()}")
                    
                    # Check if this is hex data from bluetooth capture
                    if "Hex: " in line:
                        # Extract hex data after "Hex: "
                        hex_start = line.find("Hex: ")
                        if hex_start != -1:
                            hex_data = line[hex_start + 5:].strip()
                            # Remove trailing "..." if present
                            if hex_data.endswith("..."):
                                hex_data = hex_data[:-3]
                            
                            # Format as wmbusmeters telegram format
                            telegram_data = f"telegram=||{hex_data}||"
                            logger.info(f"📡 Bridging: {telegram_data}")
                            
                            # Write to virtual serial port
                            if self.master_fd is not None:
                                os.write(self.master_fd, (telegram_data + "\n").encode())
                    
                    # Also log other important messages
                    elif any(keyword in line for keyword in ["Found", "Connected", "Error", "Failed", "Frame captured", "Started"]):
                        logger.info(f"🔍 Bluetooth: {line.strip()}")
                        
                except Exception as read_error:
                    logger.error(f"Read error: {read_error}")
                    time.sleep(0.1)
                    
        except Exception as e:
            logger.error(f"✗ Bridge error: {e}")
        finally:
            logger.info("🔄 Data bridge thread ended")
    
    def start_bridge(self):
        """Start the complete bridge"""
        logger.info("🌉 Starting Bluetooth to Serial Bridge")
        logger.info("=" * 50)
        
        # Create virtual serial port
        if not self.create_virtual_serial_port():
            return False
        
        # Start bluetooth capture
        if not self.start_bluetooth_capture():
            return False
        
        self.running = True
        
        # Start bridging in a separate thread
        bridge_thread = threading.Thread(target=self.bridge_data)
        bridge_thread.daemon = True
        bridge_thread.start()
        
        logger.info(f"🚀 Bridge running!")
        logger.info(f"📱 Bluetooth source: bluetooth_wmbus_capture.py")
        logger.info(f"🔌 Virtual serial port: {self.slave_name}")
        logger.info(f"💡 Use with wmbusmeters: ./build/wmbusmeters --logtelegrams {self.slave_name}:9600:c1,t1")
        logger.info("=" * 50)
        
        try:
            # Keep the main thread alive
            while self.running:
                time.sleep(1)
                
                # Check if bluetooth process is still running
                if self.bluetooth_process and self.bluetooth_process.poll() is not None:
                    logger.warning("⚠️ Bluetooth process terminated")
                    break
                    
        except KeyboardInterrupt:
            logger.info("🛑 Received interrupt signal")
        
        self.stop_bridge()
        return True
    
    def stop_bridge(self):
        """Stop the bridge"""
        logger.info("🛑 Stopping bridge...")
        self.running = False
        
        if self.bluetooth_process:
            self.bluetooth_process.terminate()
            try:
                self.bluetooth_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.bluetooth_process.kill()
        
        if self.master_fd:
            os.close(self.master_fd)
        if self.slave_fd:
            os.close(self.slave_fd)
        
        logger.info("✓ Bridge stopped")

def signal_handler(signum, frame):
    """Handle interrupt signals"""
    logger.info(f"🛑 Received signal {signum} - stopping bridge gracefully...")
    # The bridge will be stopped in the main function
    
def main():
    bridge = None
    
    def cleanup():
        if bridge:
            bridge.stop_bridge()
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Create and start bridge
        bridge = BluetoothToSerialBridge()
        success = bridge.start_bridge()
        
        if not success:
            logger.error("✗ Failed to start bridge")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("🛑 Keyboard interrupt received")
    except Exception as e:
        logger.error(f"✗ Bridge error: {e}")
    finally:
        cleanup()

if __name__ == "__main__":
    main()
