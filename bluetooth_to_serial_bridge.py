#!/usr/bin/env python3
"""
DEPRECATED: This legacy Bluetooth-to-virtual-serial bridge is no longer used.

Use the unified stdout pipeline instead:
    ./run_flowiq2101_live.sh --stdout --no-prompt \
         EXTRA_CAPTURE_OPTS="--bridge-mode --print-all --name-contains VW1871"

If you truly need a PTY, create a symlink yourself:
    ./run_flowiq2101_live.sh --stdout | tee live_logs/frames_latest.hex

This script now exits immediately to prevent accidental usage.
"""
import sys
print("[DEPRECATED] Use run_flowiq2101_live.sh --stdout instead of bluetooth_to_serial_bridge.py", file=sys.stderr)
sys.exit(1)

# Original implementation retained below (unreachable) for reference.

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
        self.timer_thread = None
        self.running = False
        self.start_time = None
        self.telegram_count = 0
        self.timeout_minutes = 5  # Stop after 5 minutes

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
            # Use absolute path for virtual environment python
            current_dir = os.getcwd()
            venv_path = os.path.join(current_dir, ".venv", "bin", "python")
            capture_script = os.path.join(current_dir, "bluetooth_wmbus_capture.py")
            
            if os.path.exists(venv_path):
                python_cmd = venv_path
                self.logger.info(f"Using virtual environment Python: {venv_path}")
            else:
                python_cmd = "python3"
                self.logger.warning("Virtual environment not found, using system python3")

            # Verify the capture script exists
            if not os.path.exists(capture_script):
                self.logger.error(f"Bluetooth capture script not found: {capture_script}")
                return False

            # Start bluetooth capture with explicit paths and unbuffered output
            cmd = [python_cmd, "-u", capture_script, "--bridge-mode"]  # -u for unbuffered output, --bridge-mode for stdout output
            self.logger.info(f"Starting bluetooth capture: {' '.join(cmd)}")
            
            self.bluetooth_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=0,  # Unbuffered
                cwd=current_dir  # Set working directory explicitly
            )
            self.logger.info("✓ Started Bluetooth capture process")
            return True
        except Exception as e:
            self.logger.error(f"Failed to start Bluetooth capture: {e}")
            return False

    def timer_thread_func(self):
        """Timer thread to stop bridge after specified minutes"""
        time.sleep(self.timeout_minutes * 60)  # Convert minutes to seconds
        if self.running and self.start_time is not None:
            elapsed = time.time() - self.start_time
            self.logger.info(f"🕰️ Timeout reached after {self.timeout_minutes} minutes ({elapsed:.1f}s)")
            self.logger.info(f"📊 Total telegrams processed: {self.telegram_count}")
            self.stop_bridge()

    def bridge_data(self):
        """Bridge data from bluetooth capture to virtual serial port"""
        self.logger.info("🔄 Starting data bridge...")
        
        while self.running and self.bluetooth_process:
            try:
                if self.bluetooth_process.poll() is None and self.bluetooth_process.stdout:
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
                                        self.telegram_count += 1
                                        
                                        # Display telegram on screen
                                        print(f"\n📡 TELEGRAM #{self.telegram_count}")
                                        print(f"🕐 Time: {datetime.now().strftime('%H:%M:%S')}")
                                        print(f"📏 Length: {len(telegram)} chars")
                                        print(f"📧 Data: {telegram}")
                                        print("-" * 50)
                                        
                                        self.logger.info(f"📡 Bridging telegram #{self.telegram_count}: {telegram[:40]}...")
                                        
                                        # Write to virtual serial port in wmbusmeters format
                                        if self.master_fd is not None:
                                            try:
                                                # Format as wmbusmeters expects: telegram=|HEX_DATA|
                                                wmbus_format = f"telegram=|{telegram}|\n"
                                                os.write(self.master_fd, wmbus_format.encode())
                                            except Exception as e:
                                                self.logger.error(f"Failed to write to serial port: {e}")
                            else:
                                telegram = line
                                self.telegram_count += 1
                                
                                # Display telegram on screen
                                print(f"\n📡 TELEGRAM #{self.telegram_count}")
                                print(f"🕐 Time: {datetime.now().strftime('%H:%M:%S')}")
                                print(f"📏 Length: {len(telegram)} chars")
                                print(f"📧 Data: {telegram}")
                                print("-" * 50)
                                
                                self.logger.info(f"📡 Bridging telegram #{self.telegram_count}: {telegram[:40]}...")
                                
                                # Write to virtual serial port in wmbusmeters format
                                if self.master_fd is not None:
                                    try:
                                        # Format as wmbusmeters expects: telegram=|HEX_DATA|
                                        wmbus_format = f"telegram=|{telegram}|\n"
                                        os.write(self.master_fd, wmbus_format.encode())
                                    except Exception as e:
                                        self.logger.error(f"Failed to write to serial port: {e}")
                        else:
                            # Log non-telegram output for debugging
                            if line:
                                self.logger.debug(f"🔍 Bluetooth debug: {line}")
                else:
                    # Check if bluetooth process has errors
                    if self.bluetooth_process.poll() is not None:
                        return_code = self.bluetooth_process.returncode
                        stderr_output = self.bluetooth_process.stderr.read() if self.bluetooth_process.stderr else "No error output"
                        self.logger.warning(f"⚠️ Bluetooth process terminated with code {return_code}")
                        if stderr_output:
                            self.logger.error(f"Bluetooth process stderr: {stderr_output}")
                    else:
                        self.logger.warning("⚠️ Bluetooth process stdout ended but process still running")
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
        self.start_time = time.time()  # Initialize start time
        self.bridge_thread = threading.Thread(target=self.bridge_data)
        self.bridge_thread.start()
        
        # Start timer thread
        self.timer_thread = threading.Thread(target=self.timer_thread_func)
        self.timer_thread.start()
        
        self.logger.info("🚀 Bridge running!")
        self.logger.info(f"📱 Bluetooth source: bluetooth_wmbus_capture.py")
        self.logger.info(f"🔌 Virtual serial port: {self.slave_name}")
        self.logger.info(f"📊 Connect wmbusmeters to: {self.slave_name}:9600")
        self.logger.info(f"⏰ Will stop automatically after {self.timeout_minutes} minutes")
        self.logger.info("💡 Telegrams will be displayed on screen")
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

        # Wait for timer thread
        if self.timer_thread and self.timer_thread.is_alive():
            self.timer_thread.join(timeout=2)

        # Close file descriptors
        if self.master_fd:
            os.close(self.master_fd)
            self.master_fd = None
        if self.slave_fd:
            os.close(self.slave_fd)
            self.slave_fd = None

        # Final statistics
        if self.start_time is not None:
            elapsed = time.time() - self.start_time
            self.logger.info(f"📊 Session ended: {self.telegram_count} telegrams in {elapsed:.1f}s")
        
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
