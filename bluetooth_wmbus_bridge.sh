#!/bin/bash

# Bluetooth to Serial Bridge - Creates /dev/ttys001 virtual port
# Bridges VW1871 Bluetooth to virtual serial port for wmbusmeters

set -e

# Target virtual serial port
VIRTUAL_PORT="/tmp/ttys001"

echo "🎯 Bluetooth → ttys001 Serial Bridge"
echo "===================================="
echo "Target: VW1871-250111 Bluetooth device"
echo "Virtual Serial: $VIRTUAL_PORT"
echo "Accessible as: ttys001 style device"
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo "🧹 Cleaning up bridge service..."
    pkill -f "bluetooth_wmbus_capture" || true
    pkill -f "vw1871_frame_extractor" || true
    rm -f "$VIRTUAL_PORT" || true
    echo "✅ Cleanup complete"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Create virtual serial port using socat PTY
echo "📡 Creating virtual serial port: $VIRTUAL_PORT"

# Create a named pipe (FIFO) instead of PTY for better macOS compatibility
mkfifo "$VIRTUAL_PORT" 2>/dev/null || {
    echo "❌ Failed to create FIFO at $VIRTUAL_PORT"
    cleanup
    exit 1
}

echo "✅ Virtual serial port (FIFO) created: $VIRTUAL_PORT"

# Verify the port was created
if [[ -e "$VIRTUAL_PORT" ]]; then
    echo "✅ Virtual serial port ready: $VIRTUAL_PORT"
    ls -la "$VIRTUAL_PORT" 2>/dev/null || true
else
    echo "❌ Failed to create virtual serial port"
    exit 1
fi

echo ""
echo "🚀 Starting Bluetooth → Serial bridge..."
echo ""

# Start bluetooth capture and bridge to serial
(
    source .venv/bin/activate
    python bluetooth_wmbus_capture.py --duration 0 | \
    while IFS= read -r line; do
        # Process hex data lines (look for longer hex strings)
        if [[ "$line" =~ ^[0-9A-Fa-f]{40,}$ ]]; then
            echo "[$(date '+%H:%M:%S')] 📥 BLE Data (${#line} chars): ${line:0:50}..."
            
            # Extract WM-Bus frames using VW1871 preprocessor
            processed=$(echo "$line" | python vw1871_frame_extractor.py 2>/dev/null | grep "telegram=" || true)
            
            if [[ -n "$processed" ]]; then
                echo "$processed" | while IFS= read -r telegram_line; do
                    if [[ "$telegram_line" =~ telegram=\|([^|]+)\| ]]; then
                        frame="${BASH_REMATCH[1]}"
                        echo "[$(date '+%H:%M:%S')] ✅ WM-Bus Frame (${#frame} chars): ${frame:0:50}..."
                        
                        # Send to virtual serial port
                        echo "$frame" > "$VIRTUAL_PORT" 2>/dev/null &
                    fi
                done
            fi
        elif [[ "$line" =~ "Connected to" ]] || [[ "$line" =~ "Found" ]] || [[ "$line" =~ "INFO" ]]; then
            echo "[$(date '+%H:%M:%S')] 🔗 BLE: $line"
        fi
    done
) &

BLE_PID=$!

echo "📊 Bridge Service Status:"
echo "   BLE Capture PID: $BLE_PID"
echo "   Virtual Serial: $VIRTUAL_PORT"
echo ""
echo "🎯 Use with wmbusmeters:"
echo "   ./build/wmbusmeters $VIRTUAL_PORT:38400:c1"
echo "   ./build/wmbusmeters --format=json $VIRTUAL_PORT:38400:c1"
echo ""
echo "Press Ctrl+C to stop bridge"
echo "========================================"

# Monitor bridge status
counter=0
while true; do
    sleep 20
    counter=$((counter + 1))
    
    if ! kill -0 $BLE_PID 2>/dev/null; then
        echo "[$(date '+%H:%M:%S')] ⚠️  BLE capture stopped"
        break
    fi
    
    if ! kill -0 $SOCAT_PID 2>/dev/null; then
        echo "[$(date '+%H:%M:%S')] ⚠️  socat process stopped"
        break
    fi
    
    if [[ ! -e "$LOCAL_PORT" ]]; then
        echo "[$(date '+%H:%M:%S')] ⚠️  Virtual serial port stopped"
        break
    fi
    
    echo "[$(date '+%H:%M:%S')] 🔄 Bridge active (check #$counter) - Virtual port: $VIRTUAL_PORT"
done

cleanup
