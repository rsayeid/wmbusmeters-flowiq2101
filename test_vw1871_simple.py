#!/usr/bin/env python3
"""
Simple VW1871 Communication Test
Tests basic serial communication with VW1871 Bluetooth device
"""

import serial
import time
import sys

def test_vw1871():
    device = "/dev/cu.VW1871-250111"
    
    print(f"=== Testing VW1871 Device: {device} ===\n")
    
    # Test different baud rates
    baud_rates = [9600, 19200, 38400, 57600, 115200]
    
    for baud in baud_rates:
        print(f"Testing at {baud} baud...")
        
        try:
            # Open serial connection
            ser = serial.Serial(device, baud, timeout=2)
            print(f"✓ Connected at {baud} baud")
            
            # Listen for incoming data
            print("Listening for data (5 seconds)...")
            start_time = time.time()
            data_received = False
            
            while time.time() - start_time < 5:
                if ser.in_waiting > 0:
                    data = ser.read(ser.in_waiting)
                    print(f"📡 Data received: {data.hex()}")
                    print(f"   ASCII: {data}")
                    data_received = True
                time.sleep(0.1)
            
            if not data_received:
                print("   No data received")
            
            # Try sending commands
            commands = [b'AT\r\n', b'ATI\r\n', b'?\r\n', b'HELP\r\n']
            for cmd in commands:
                print(f"Sending: {cmd}")
                ser.write(cmd)
                time.sleep(0.5)
                
                if ser.in_waiting > 0:
                    response = ser.read(ser.in_waiting)
                    print(f"Response: {response.hex()}")
                    print(f"   ASCII: {response}")
                else:
                    print("   No response")
            
            ser.close()
            print()
            
        except Exception as e:
            print(f"✗ Error at {baud} baud: {e}")
            print()
            continue
    
    print("=== Test Complete ===")
    print("If no data was received:")
    print("1. VW1871 may not be a wM-Bus receiver")
    print("2. Device may need specific initialization")
    print("3. No wM-Bus transmitters in range")
    print("4. Device may be in wrong mode")

if __name__ == "__main__":
    try:
        test_vw1871()
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Test failed: {e}")
