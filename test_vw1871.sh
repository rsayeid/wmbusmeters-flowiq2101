#!/bin/bash

# Native VW1871 Communication Test
# Uses only built-in macOS tools to test communication with VW1871-250111

VW1871_DEV="/dev/cu.VW1871-250111"
VW1871_MAC="60-6e-41-e3-18-5f"
BLUETOOTH_PORT="/dev/cu.Bluetooth-Incoming-Port"

echo "=== Native VW1871-250111 Communication Test ==="
echo

# Function to test a device
test_device() {
    local device=$1
    local baud=$2
    local duration=${3:-5}
    
    echo "Testing $device at $baud baud for $duration seconds..."
    
    # Configure the device
    stty -f "$device" "$baud" raw -echo -onlcr 2>/dev/null || {
        echo "✗ Failed to configure $device"
        return 1
    }
    
    echo "✓ Device configured"
    
    # Test 1: Listen for incoming data
    echo "Listening for data..."
    
    # Simple data collection test
    {
        echo "Starting listener..."
        timeout_pid=$$
        (sleep "$duration"; kill -TERM $timeout_pid 2>/dev/null) &
        timeout_child=$!
        
        # Try to read data
        exec 3< "$device"
        if read -t "$duration" -u 3 data 2>/dev/null; then
            echo "📡 Data received: $data"
            echo "$data" | hexdump -C
        else
            echo "   No data received"
        fi
        exec 3<&-
        
        kill $timeout_child 2>/dev/null
    }
    
    # Test 2: Try sending commands
    echo "Testing commands..."
    
    for cmd in "AT" "ATI" "ATZ" "M" "?" "HELP"; do
        echo "Sending: $cmd"
        echo -e "${cmd}\r\n" > "$device" 2>/dev/null
        sleep 0.5
        
        # Try to read response with timeout
        exec 3< "$device"
        if read -t 1 -u 3 response 2>/dev/null; then
            echo "Response: $response"
            echo "$response" | hexdump -C
        else
            echo "No response"
        fi
        exec 3<&-
    done
    
    echo
}

# Check device status
echo "=== VW1871 Device Status ==="
echo "Device MAC: $VW1871_MAC"
echo "Device file: $VW1871_DEV"

# Check connection status
if [ "$(blueutil --is-connected "$VW1871_MAC")" = "1" ]; then
    echo "✓ VW1871 Bluetooth connected"
    blueutil --connected | grep -i VW1871
else
    echo "Connecting to VW1871..."
    blueutil --connect "$VW1871_MAC"
    sleep 3
    if [ "$(blueutil --is-connected "$VW1871_MAC")" = "1" ]; then
        echo "✓ VW1871 connected successfully"
    else
        echo "✗ Failed to connect to VW1871"
        exit 1
    fi
fi

echo

# Check device file properties
echo "=== Device File Properties ==="
ls -la "$VW1871_DEV"
echo "Current settings:"
stty -f "$VW1871_DEV" -a

echo

# Test different configurations
echo "=== Testing Different Configurations ==="

# Test VW1871 device with different baud rates
for baud in 9600 19200 38400 57600 115200; do
    echo "--- Testing VW1871 at $baud baud ---"
    test_device "$VW1871_DEV" "$baud" 3
    echo
done

echo "=== wmbusmeters Tests with VW1871 ==="

# Test with wmbusmeters
echo "Testing wmbusmeters with VW1871 device..."

# Try different wmbusmeters configurations
for mode in "c1,t1" "s1" "c1" "t1"; do
    echo "--- Testing mode: $mode ---"
    echo "Command: ./build/wmbusmeters --debug --verbose --exitafter=10 $VW1871_DEV:38400:$mode"
    ./build/wmbusmeters --debug --verbose --exitafter=10 "$VW1871_DEV:38400:$mode" 2>&1 | grep -E "(telegram|Started|id:|meter|ERROR|bytes|data)" || echo "No relevant output for mode $mode"
    echo
done

echo "=== Extended Listening Test ==="
echo "Performing 30-second extended listen on VW1871..."
./build/wmbusmeters --debug --verbose --exitafter=30 "$VW1871_DEV:38400:c1,t1" 2>&1 | head -50

echo
echo "=== Test Results Summary ==="
echo "Device: VW1871-250111"
echo "MAC: $VW1871_MAC"
echo "Connection: $(blueutil --is-connected "$VW1871_MAC" && echo "Connected" || echo "Disconnected")"
echo "Device file: $VW1871_DEV"

echo
echo "=== Next Steps ==="
if [ "$(blueutil --is-connected "$VW1871_MAC")" = "1" ]; then
    echo "✓ Device is connected and accessible"
    echo "If no data detected:"
    echo "1. 📡 Device may be a different type (not wM-Bus receiver)"
    echo "2. 🔧 May need specific initialization commands"
    echo "3. 📻 Could be wrong protocol/frequency"
    echo "4. 📊 May not be compatible with wM-Bus"
else
    echo "✗ Connection issues detected"
fi
