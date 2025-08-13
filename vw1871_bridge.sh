#!/bin/bash

# Native macOS Bluetooth Bridge for VW1871-250111 (FlowIQ2101)
# This script creates a direct connection to the VW1871 concentrator

VW1871_DEV="/dev/cu.VW1871-250111"
BRIDGE_PORT="/tmp/vw1871_bridge"
WMBUSMETERS_BIN="./build/wmbusmeters"

echo "=== VW1871-250111 Bluetooth Bridge for FlowIQ2101 ==="
echo

# Function to cleanup on exit
cleanup() {
    echo "Cleaning up..."
    pkill -f "cat.*$VW1871_DEV" 2>/dev/null
    pkill -f "wmbusmeters.*$BRIDGE_PORT" 2>/dev/null
    rm -f "$BRIDGE_PORT" 2>/dev/null
    exit 0
}

trap cleanup INT TERM

# Step 1: Check if VW1871 device is available
echo "1. Checking VW1871-250111 connection..."
if [ -e "$VW1871_DEV" ]; then
    echo "✓ VW1871-250111 device found at $VW1871_DEV"
else
    echo "✗ VW1871-250111 device not found at $VW1871_DEV"
    echo "Available devices:"
    ls -la /dev/cu.* | grep -E "(VW|Bluetooth)"
    exit 1
fi

# Step 2: Create named pipe for bridging
echo "2. Setting up bridge..."
rm -f "$BRIDGE_PORT" 2>/dev/null
mkfifo "$BRIDGE_PORT"

if [ -p "$BRIDGE_PORT" ]; then
    echo "✓ Bridge pipe created at $BRIDGE_PORT"
else
    echo "✗ Failed to create bridge pipe"
    exit 1
fi

# Step 3: Start data forwarding from VW1871 to bridge
echo "3. Starting VW1871 data bridge..."
cat "$VW1871_DEV" > "$BRIDGE_PORT" &
BRIDGE_PID=$!

echo "✓ Bridge running (PID: $BRIDGE_PID)"
sleep 2

# Step 4: Test connection with short wmbusmeters run
echo "4. Testing connection..."
echo "Running 10-second test with wmbusmeters..."

timeout 10 "$WMBUSMETERS_BIN" --logtelegrams "$BRIDGE_PORT:9600:c1,t1" 2>&1 | tee /tmp/vw1871_test.log

echo "Test completed. Check /tmp/vw1871_test.log for results."

# Step 5: Start full monitoring session
echo "5. Starting full FlowIQ2101 monitoring..."
echo "Press Ctrl+C to stop monitoring..."
echo

"$WMBUSMETERS_BIN" --logtelegrams "$BRIDGE_PORT:9600:c1,t1" FlowIQ2101 flowiq2101 74493770 44E9112D06BD762EC2BFECE57E487C9B

cleanup
