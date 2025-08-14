#!/bin/bash

# FlowIQ2101 Virtual Serial Port Bridge
# Creates a virtual serial port for wmbusmeters device configuration

set -e

VW1871_DEVICE="VW1871-250111"
CONFIG_DIR="/tmp/wmbusmeters_flowiq"

echo "🔧 FlowIQ2101 Virtual Serial Port Setup"
echo "======================================"

# Cleanup function
cleanup() {
    echo ""
    echo "🧹 Cleaning up..."
    pkill -f "bluetooth_wmbus_capture" || true
    pkill -f "wmbusmeters" || true
    pkill -f "vw1871_frame_extractor" || true
    echo "✅ Cleanup complete"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start the integrated bridge which creates virtual serial port
echo "🚀 Starting integrated bridge with virtual serial port..."
echo ""

# The integrated bridge will:
# 1. Create a virtual serial port (e.g., /dev/ttys001)
# 2. Connect to VW1871-250111 via BLE
# 3. Extract frames and write to virtual serial port
# 4. Start wmbusmeters to read from the virtual serial port

python bluetooth_to_serial_bridge_integrated.py &

BRIDGE_PID=$!

echo ""
echo "📊 Bridge Status:"
echo "   Bridge PID: $BRIDGE_PID"
echo "   Virtual serial port will be created automatically"
echo "   wmbusmeters will start automatically"
echo ""
echo "Press Ctrl+C to stop the bridge"
echo "========================================"

# Monitor the bridge
while true; do
    sleep 15
    
    if ! kill -0 $BRIDGE_PID 2>/dev/null; then
        echo "⚠️  Bridge stopped"
        break
    fi
    
    # Show active virtual serial ports
    echo "[$(date '+%H:%M:%S')] 🔄 Bridge active - Virtual serial ports:"
    ls -la /dev/ttys* 2>/dev/null | grep "$(whoami)" | head -3 || echo "   No user-owned virtual ports found"
done

cleanup
