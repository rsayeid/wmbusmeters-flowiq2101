#!/usr/bin/env python3
"""
Simple Bluetooth to Serial Bridge
Captures wM-Bus telegrams via Bluetooth and bridges them to a virtual serial port
"""

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
        self.running = False

    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
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
            # Find virtual environment python if it exists
            venv_path = ".venv/bin/python"
            if os.path.exists(venv_path):
                python_cmd = venv_path
                self.logger.info(f"Using virtual environment Python: {venv_path}")
            else:
                python_cmd = "python3"

            # Start bluetooth capture
            self.bluetooth_process = subprocess.Popen(
                [python_cmd, "bluetooth_wmbus_capture.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )
            self.logger.info("✓ Started Bluetooth capture process")
            return True
        except Exception as e:
            self.logger.error(f"Failed to start Bluetooth capture: {e}")
            return False

    def bridge_data(self):
        """Bridge data from bluetooth capture to virtual serial port"""
        self.logger.info("🔄 Starting data bridge...")
        
        while self.running and self.bluetooth_process:
            try:
                if self.bluetooth_process.poll() is None:
                    line = self.bluetooth_process.stdout.readline()
                    if line:
                        line = line.strip()
                        self.logger.debug(f"📥 Raw line: {line}")
                        
                        # Look for telegram patterns (hex strings)
                        if len(line) >= 40 and all(c in '0123456789ABCDEFabcdef' for c in line):
                            # Extract telegram data
                            start = 0
                            end = len(line)
                            
                            # Find actual telegram boundaries if needed
                            if '|' in line:
                                parts = line.split('|')
                                for part in parts:
                                    if len(part) >= 40 and all(c in '0123456789ABCDEFabcdef' for c in part):
                                        telegram = part.strip()
                                        self.logger.info(f"📡 Bridging telegram: {telegram[:40]}...")
                                        
                                        # Write to virtual serial port
                                        if self.master_fd is not None:
                                            try:
                                                telegram_with_newline = telegram + '\n'
                                                os.write(self.master_fd, telegram_with_newline.encode())
                                            except Exception as e:
                                                self.logger.error(f"Failed to write to serial port: {e}")
                            else:
                                telegram = line
                                self.logger.info(f"📡 Bridging telegram: {telegram[:40]}...")
                                
                                # Write to virtual serial port
                                if self.master_fd is not None:
                                    try:
                                        telegram_with_newline = telegram + '\n'
                                        os.write(self.master_fd, telegram_with_newline.encode())
                                    except Exception as e:
                                        self.logger.error(f"Failed to write to serial port: {e}")
                        else:
                            # Log non-telegram output for debugging
                            if line:
                                self.logger.debug(f"🔍 Bluetooth debug: {line}")
                else:
                    self.logger.warning("⚠️ Bluetooth process terminated")
                    break
                    
            except Exception as e:
                self.logger.error(f"Error in bridge_data: {e}")
                break

        self.logger.info("🔄 Bridge thread stopped")

    def start_bridge(self):
        """Start the complete bridge service"""
        self.logger.info("🌉 Starting Bluetooth to Serial Bridge")
        self.logger.info("=" * 50)
        
        # Create virtual serial port
        if not self.create_virtual_serial_port():
            return False
            
        # Start bluetooth capture
        if not self.start_bluetooth_capture():
            return False

        # Start bridging
        self.running = True
        self.bridge_thread = threading.Thread(target=self.bridge_data)
        self.bridge_thread.start()
        
        self.logger.info("🚀 Bridge running!")
        self.logger.info(f"📱 Bluetooth source: bluetooth_wmbus_capture.py")
        self.logger.info(f"🔌 Virtual serial port: {self.slave_name}")
        self.logger.info(f"📊 Connect wmbusmeters to: {self.slave_name}:9600")
        self.logger.info("=" * 50)
        
        return True

    def stop_bridge(self):
        """Stop the bridge and cleanup"""
        self.logger.info("🛑 Stopping bridge...")
        self.running = False
        
        # Stop bluetooth process
        if self.bluetooth_process:
            self.bluetooth_process.terminate()
            try:
                self.bluetooth_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.bluetooth_process.kill()
            self.bluetooth_process = None

        # Wait for bridge thread
        if self.bridge_thread and self.bridge_thread.is_alive():
            self.bridge_thread.join(timeout=5)

        # Close file descriptors
        if self.master_fd:
            os.close(self.master_fd)
            self.master_fd = None
        if self.slave_fd:
            os.close(self.slave_fd)
            self.slave_fd = None

        self.logger.info("✓ Bridge stopped")

# Global bridge instance for signal handler
bridge = None

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    print("\n🛑 Received interrupt signal, stopping bridge...")
    if bridge:
        bridge.stop_bridge()
    sys.exit(0)

if __name__ == "__main__":
    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and start bridge
    bridge = BluetoothSerialBridge()
    
    try:
        if bridge.start_bridge():
            # Keep running until stopped
            while bridge.running:
                time.sleep(1)
        else:
            print("Failed to start bridge")
            sys.exit(1)
    except KeyboardInterrupt:
        print("Keyboard interrupt received")
        bridge.stop_bridge()
    except Exception as e:
        print(f"Bridge error: {e}")
        bridge.stop_bridge()
        sys.exit(1)
