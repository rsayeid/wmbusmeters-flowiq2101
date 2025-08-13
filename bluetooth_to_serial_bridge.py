#!/usr/bin/env python3
"""
Bluetooth to Serial Bridge with wmbusmeters Integration
Captures wM-Bus telegrams via Bluetooth and processes them with wmbusmeters
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
        self.wmbusmeters_process = None
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
            # Build wmbusmeters command
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
        self.last_reading = None
        
    def bridge_data(self):
        """Bridge data from bluetooth capture to virtual serial port and wmbusmeters"""
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
                                    telegram_with_newline = telegram + '
'
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
        self.logger.info("🌉 Starting Bluetooth to Serial Bridge")
        self.logger.info("=" * 50)
        
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
        self.logger.info("=" * 50)
        
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
    print("
🛑 Received interrupt signal, stopping bridge...")
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
        sys.exit(1)    def create_telegram_file(self, hex_data):
        """Create a temporary file with the telegram data for wmbusmeters"""
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
                # Write telegram in the format wmbusmeters expects
                f.write(f"telegram=||{hex_data}||\n")
                return f.name
        except Exception as e:
            logger.error(f"✗ Failed to create telegram file: {e}")
            return None
    
    def process_telegram_with_wmbusmeters(self, hex_data):
        """Process a single telegram using wmbusmeters"""
        try:
            # Create temporary telegram file
            telegram_file = self.create_telegram_file(hex_data)
            if not telegram_file:
                return None
            
            # Build wmbusmeters command
            cmd = [
                "./build/wmbusmeters",
                "--format=json",
                "--logtelegrams",
                telegram_file,
                self.meter_config['name'],
                self.meter_config['driver'], 
                self.meter_config['id'],
                self.meter_config['key']
            ]
            
            # Execute wmbusmeters
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Clean up temporary file
            os.unlink(telegram_file)
            
            if result.returncode == 0:
                # Parse JSON output
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if line.startswith('{') and 'media' in line:
                        try:
                            reading = json.loads(line)
                            return reading
                        except json.JSONDecodeError:
                            continue
                            
            else:
                logger.debug(f"wmbusmeters stderr: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            logger.warning("⚠️ wmbusmeters processing timeout")
        except Exception as e:
            logger.error(f"✗ wmbusmeters processing error: {e}")
            
        return None
    
    def format_reading_output(self, reading):
        """Format meter reading for display"""
        if not reading:
            return None
            
        try:
            output = []
            output.append("=" * 60)
            output.append(f"🚰 FlowIQ2101 Reading #{self.telegram_count}")
            output.append(f"📅 Timestamp: {reading.get('timestamp', 'N/A')}")
            output.append(f"🆔 Meter ID: {reading.get('id', 'N/A')}")
            
            # Water volume information
            if 'total_m3' in reading:
                output.append(f"💧 Total Volume: {reading['total_m3']} m³")
            if 'target_m3' in reading:
                output.append(f"🎯 Target Volume: {reading['target_m3']} m³")
            if 'max_flow_m3h' in reading:
                output.append(f"📊 Max Flow: {reading['max_flow_m3h']} m³/h")
                
            # Temperature information  
            if 'flow_temperature_c' in reading:
                output.append(f"🌡️ Flow Temperature: {reading['flow_temperature_c']}°C")
            if 'external_temperature_c' in reading:
                output.append(f"🌡️ External Temperature: {reading['external_temperature_c']}°C")
                
            # Status information
            if 'status' in reading:
                output.append(f"📊 Status: {reading['status']}")
            if 'error_flags' in reading:
                output.append(f"⚠️ Error Flags: {reading['error_flags']}")
                
            output.append("=" * 60)
            
            return '\n'.join(output)
            
        except Exception as e:
            logger.error(f"✗ Failed to format reading: {e}")
            return f"Raw reading: {reading}"
    
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
        """Process Bluetooth data and decode with integrated wmbusmeters"""
        logger.info("🔄 Starting telegram processing thread")
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
                            
                            self.telegram_count += 1
                            logger.info(f"📡 Processing telegram #{self.telegram_count}: {hex_data[:20]}...")
                            
                            # Process telegram with wmbusmeters
                            reading = self.process_telegram_with_wmbusmeters(hex_data)
                            
                            if reading:
                                self.last_reading = reading
                                formatted_output = self.format_reading_output(reading)
                                if formatted_output:
                                    print(formatted_output)
                                else:
                                    logger.info(f"✅ Telegram processed successfully: {reading}")
                            else:
                                logger.warning(f"⚠️ Could not decode telegram: {hex_data[:40]}...")
                    
                    # Also log other important messages
                    elif any(keyword in line for keyword in ["Found", "Connected", "Error", "Failed", "Frame captured", "Started"]):
                        logger.info(f"🔍 Bluetooth: {line.strip()}")
                        
                except Exception as read_error:
                    logger.error(f"Read error: {read_error}")
                    time.sleep(0.1)
                    
        except Exception as e:
            logger.error(f"✗ Processing error: {e}")
        finally:
            logger.info("🔄 Telegram processing thread ended")
    
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
