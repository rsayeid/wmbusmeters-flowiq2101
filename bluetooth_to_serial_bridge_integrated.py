#!/usr/bin/env python3
"""
DEPRECATED: Integrated Bluetooth->serial + wmbusmeters bridge.
Use: ./run_flowiq2101_live.sh --stdout --no-prompt \
    EXTRA_CAPTURE_OPTS="--bridge-mode --print-all"
This script now exits immediately; original code left below.
"""
import sys
print("[DEPRECATED] Use run_flowiq2101_live.sh --stdout instead of bluetooth_to_serial_bridge_integrated.py", file=sys.stderr)
sys.exit(1)

# --- Original implementation (inactive) ---

import os
import sys
import time
import pty
import threading
import subprocess
import logging
import signal
from datetime import datetime

class BluetoothSerialBridge:
    def __init__(self):
        self.setup_logging()
        self.master_fd = None
        self.slave_fd = None
        self.slave_name = None
        self.bluetooth_process = None
        self.bridge_thread = None
        self.wmbusmeters_process = None
        self.wmbus_thread = None
        self.running = False

    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def create_virtual_serial_port(self):
        """Create a virtual serial port using pty"""
        try:
            self.master_fd, self.slave_fd = pty.openpty()
            self.slave_name = os.ttyname(self.slave_fd)
            self.logger.info(f"✓ Created virtual serial port: {self.slave_name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to create virtual serial port: {e}")
            return False

    def start_bluetooth_capture(self):
        """Start the bluetooth capture subprocess"""
        try:
            # Determine Python path - prefer virtual environment
            python_path = sys.executable
            venv_path = os.path.join(os.getcwd(), '.venv', 'bin', 'python')
            if os.path.exists(venv_path):
                python_path = venv_path
                self.logger.info(f"Using virtual environment Python: {venv_path}")
            
            # Start bluetooth capture process
            self.bluetooth_process = subprocess.Popen(
                [python_path, 'bluetooth_wmbus_capture.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            self.logger.info("✓ Started Bluetooth capture process")
            return True
        except Exception as e:
            self.logger.error(f"Failed to start Bluetooth capture: {e}")
            return False

    def start_wmbusmeters(self):
        """Start wmbusmeters to read from the virtual serial port"""
        try:
            # Build wmbusmeters command - no meter config, just listen to device
            wmbus_cmd = [
                './build/wmbusmeters',
                '--logtelegrams',
                f'{self.slave_name}:9600:c1,t1'
            ]
            
            self.logger.info(f"Starting wmbusmeters: {' '.join(wmbus_cmd)}")
            
            # Start wmbusmeters process
            self.wmbusmeters_process = subprocess.Popen(
                wmbus_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            self.logger.info("✓ Started wmbusmeters process")
            return True
        except Exception as e:
            self.logger.error(f"Failed to start wmbusmeters: {e}")
            return False

    def bridge_data(self):
        """Bridge data from bluetooth capture to virtual serial port"""
        while self.running:
            try:
                if self.bluetooth_process and self.bluetooth_process.poll() is None:
                    line = self.bluetooth_process.stdout.readline()
                    if line:
                        line = line.strip()
                        self.logger.debug(f"📥 Raw line: {line}")
                        
                        # Look for telegram lines with ||...||
                        if '||' in line and line.count('||') >= 2:
                            # Extract telegram from ||telegram||
                            start = line.find('||') + 2
                            end = line.rfind('||')
                            if start < end:
                                telegram = line[start:end]
                                self.logger.info(f"📡 Bridging: telegram={telegram}")
                                
                                # Write to virtual serial port
                                try:
                                    telegram_with_newline = telegram + '\n'
                                    os.write(self.master_fd, telegram_with_newline.encode())
                                except Exception as e:
                                    self.logger.error(f"Failed to write to serial port: {e}")
                        
                        # Also log bluetooth status messages
                        if any(marker in line for marker in ['🔍 Bluetooth:', '🎯 POTENTIAL', '📊 Frame captured']):
                            self.logger.info(f"🔍 Bluetooth: {line}")
                else:
                    self.logger.warning("⚠️ Bluetooth process terminated")
                    break
                    
            except Exception as e:
                self.logger.error(f"Error in bridge_data: {e}")
                break
                
        self.logger.info("🔄 Bridge thread stopped")

    def read_wmbusmeters_output(self):
        """Read and log wmbusmeters output"""
        while self.running and self.wmbusmeters_process:
            try:
                if self.wmbusmeters_process.poll() is None:
                    line = self.wmbusmeters_process.stdout.readline()
                    if line:
                        line = line.strip()
                        if line:
                            self.logger.info(f"📊 wmbusmeters: {line}")
                else:
                    self.logger.warning("⚠️ wmbusmeters process terminated")
                    break
            except Exception as e:
                self.logger.error(f"Error reading wmbusmeters output: {e}")
                break

    def start_bridge(self):
        """Start the complete bridge service"""
        self.logger.info("🌉 Starting Bluetooth to Serial Bridge with wmbusmeters")
        self.logger.info("=" * 60)
        
        # Create virtual serial port
        if not self.create_virtual_serial_port():
            return False
            
        # Start bluetooth capture
        if not self.start_bluetooth_capture():
            return False
            
        # Start wmbusmeters
        if not self.start_wmbusmeters():
            return False
            
        # Start bridge thread
        self.running = True
        self.bridge_thread = threading.Thread(target=self.bridge_data, daemon=True)
        self.bridge_thread.start()
        self.logger.info("🔄 Starting data bridge thread")
        
        # Start wmbusmeters output thread
        self.wmbus_thread = threading.Thread(target=self.read_wmbusmeters_output, daemon=True)
        self.wmbus_thread.start()
        self.logger.info("🔄 Starting wmbusmeters output thread")
        
        # Log status
        self.logger.info("🚀 Bridge running!")
        self.logger.info(f"📱 Bluetooth source: bluetooth_wmbus_capture.py")
        self.logger.info(f"🔌 Virtual serial port: {self.slave_name}")
        self.logger.info(f"📊 wmbusmeters: ./build/wmbusmeters --logtelegrams {self.slave_name}:9600:c1,t1")
        self.logger.info("💡 wmbusmeters will listen to ALL meters on the device")
        self.logger.info("=" * 60)
        
        return True

    def stop_bridge(self):
        """Stop the bridge service"""
        self.logger.info("🛑 Stopping bridge...")
        self.running = False
        
        # Stop processes
        if self.bluetooth_process:
            self.bluetooth_process.terminate()
            
        if self.wmbusmeters_process:
            self.wmbusmeters_process.terminate()
            
        # Close file descriptors
        if self.master_fd:
            os.close(self.master_fd)
        if self.slave_fd:
            os.close(self.slave_fd)
            
        self.logger.info("✓ Bridge stopped")

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    print("\n🛑 Received interrupt signal, stopping bridge...")
    bridge.stop_bridge()
    sys.exit(0)

if __name__ == "__main__":
    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create and start bridge
    bridge = BluetoothSerialBridge()
    
    if bridge.start_bridge():
        try:
            # Keep the main thread alive
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            bridge.stop_bridge()
    else:
        print("Failed to start bridge")
        sys.exit(1)
