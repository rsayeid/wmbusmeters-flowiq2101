#!/bin/bash

# Simple Bluetooth Bridge for Kamstrup READy
# Uses native macOS tools to bridge Bluetooth data to wmbusmeters

KAMSTRUP_MAC="00:13:43:1c:8b-94"
KAMSTRUP_DEV="/dev/cu.Kamstrup_66501566"
BLUETOOTH_PORT="/dev/cu.Bluetooth-Incoming-Port"

echo "=== Simple Bluetooth Bridge for wM-Bus ==="
echo

# Ensure Kamstrup is connected
echo "1. Ensuring Kamstrup connection..."
blueutil --connect 00-13-43-1c-8b-94 > /dev/null 2>&1
sleep 2

if [ "$(blueutil --is-connected 00-13-43-1c-8b-94)" = "1" ]; then
    echo "✓ Kamstrup connected"
else
    echo "✗ Kamstrup connection failed"
    exit 1
fi

echo "2. Available methods:"
echo "   A) Direct Kamstrup device: $KAMSTRUP_DEV"
echo "   B) Bluetooth incoming port: $BLUETOOTH_PORT"
echo

# Method A: Monitor the Kamstrup device directly with different settings
echo "Method A: Testing Kamstrup device with raw monitoring..."

# Try to see if there's any raw data coming from the device
echo "Monitoring $KAMSTRUP_DEV for 10 seconds with hexdump..."
timeout 10 hexdump -C "$KAMSTRUP_DEV" | head -20 || echo "No data received on Kamstrup device"

echo
echo "Method B: Testing Bluetooth incoming port..."
timeout 10 hexdump -C "$BLUETOOTH_PORT" | head -20 || echo "No data received on Bluetooth port"

echo
echo "Method C: Testing with different baud rates on Kamstrup device..."

for baud in 9600 19200 38400 57600 115200; do
    echo "Testing baud rate: $baud"
    timeout 5 ./build/wmbusmeters --debug --exitafter=5 "$KAMSTRUP_DEV:$baud:c1,t1" 2>&1 | grep -E "(Started|telegram|meter|ERROR)" || echo "No output at $baud baud"
    echo
done

echo "Method D: Raw device access test..."
# Try to open the device and check its properties
stty -f "$KAMSTRUP_DEV" 38400 raw -echo 2>/dev/null && echo "✓ Device accessible at 38400 baud" || echo "✗ Device access failed"

echo
echo "Method E: Check device status..."
ls -la "$KAMSTRUP_DEV" "$BLUETOOTH_PORT" 2>/dev/null

echo
echo "=== Diagnostic Summary ==="
echo "Device files exist: $(ls "$KAMSTRUP_DEV" "$BLUETOOTH_PORT" 2>/dev/null | wc -l)/2"
echo "Bluetooth connected: $(blueutil --is-connected 00-13-43-1c-8b-94)"
echo "wmbusmeters version: $(./build/wmbusmeters --version | head -1)"

echo
echo "If no data is seen above, the issue is likely:"
echo "1. Kamstrup READy needs specific initialization/configuration"
echo "2. Meter is not transmitting wM-Bus (might be different protocol)"
echo "3. Wrong frequency/region settings on the READy device"
echo "4. Hardware issue with the READy device"
