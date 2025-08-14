#!/bin/bash

# Simple Bluetooth # Create virtual USB serial port using simple pipe method
echo "📡 Creating USB-style serial port: $VIRTUAL_PORT"

# Create named pipe for more reliable operation
rm -f "$VIRTUAL_PORT" 2>/dev/null || true
mkfifo "$VIRTUAL_PORT"
echo "✅ Created named pipe: $VIRTUAL_PORT"rtual Serial AMB8465 Bridge
# No configs, just raw bluetooth to virtual serial port

set -e

# Virtual serial port setup (USB-style)
VIRTUAL_PORT="/tmp/ttyUSB1"
VIRTUAL_PORT_SLAVE="/tmp/ttyUSB1_slave"

echo "🎯 Bluetooth → AMB8465:C1 USB Serial Emulation"
echo "=============================================="
echo "Emulating: /dev/ttyUSB1:amb8465:c1"
echo "Master Port: $VIRTUAL_PORT"
echo "Slave Port: $VIRTUAL_PORT_SLAVE"
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo "🧹 Cleaning up AMB8465:C1 emulation..."
    pkill -f "bluetooth_wmbus_capture" || true
    pkill -f "socat" || true
    pkill -f "vw1871_frame_extractor" || true
    rm -f "$VIRTUAL_PORT" "$VIRTUAL_PORT_SLAVE" || true
    echo "✅ Cleanup complete"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Create virtual serial port using socat
echo "� Creating virtual serial port: $VIRTUAL_PORT"
socat pty,link="$VIRTUAL_PORT",raw,echo=0 - &
SOCAT_PID=$!

sleep 1
echo "✅ USB serial port ready: $VIRTUAL_PORT"

echo ""
echo "🚀 Starting simple bluetooth capture..."
echo ""

# Start bluetooth capture (listen to VW1871 device specifically)
(
    source .venv/bin/activate
    python bluetooth_wmbus_capture.py --name-contains "VW1871-250111" --bridge-mode --print-all --duration 0 | \
    while IFS= read -r line; do
        # Process any hex data (no filtering)
        if [[ "$line" =~ ^[0-9A-Fa-f]{20,}$ ]]; then
            echo "[$(date '+%H:%M:%S')] 📥 Raw Hex (${#line} chars): ${line:0:50}..."
            
            # Pre-process hex as per rules and extract frames
            processed=$(echo "$line" | source .venv/bin/activate && python vw1871_frame_extractor.py 2>/dev/null | grep "telegram=" || true)
            
            if [[ -n "$processed" ]]; then
                echo "$processed" | while IFS= read -r telegram_line; do
                    if [[ "$telegram_line" =~ telegram=\|([^|]+)\| ]]; then
                        frame="${BASH_REMATCH[1]}"
                        echo "[$(date '+%H:%M:%S')] ✅ Processed Frame (${#frame} chars): ${frame:0:40}..."
                        
                        # Send to USB serial port (AMB8465:C1 format)
                        echo "$frame" > "$VIRTUAL_PORT"
                    fi
                done
            fi
        elif [[ "$line" =~ "Connected to" ]] || [[ "$line" =~ "Found" ]]; then
            echo "[$(date '+%H:%M:%S')] � BLE: $line"
        fi
    done
) &

BLE_PID=$!

echo "📊 AMB8465:C1 USB Serial Emulation Status:"
echo "   BLE Capture PID: $BLE_PID"
echo "   USB Serial Port: $VIRTUAL_PORT"
echo ""
echo "🎯 AMB8465:C1 USB Serial Port: $VIRTUAL_PORT"
echo "   - Targeting VW1871-250111 device"
echo "   - Pre-processing hex data per rules"
echo "   - Emulating /dev/ttyUSB1:amb8465:c1"
echo ""
echo "Use this port in wmbusmeters: $VIRTUAL_PORT:amb8465:c1"
echo "Press Ctrl+C to stop"
echo "========================================"

# Monitor status
counter=0
while true; do
    sleep 15
    counter=$((counter + 1))
    
    if ! kill -0 $BLE_PID 2>/dev/null; then
        echo "[$(date '+%H:%M:%S')] ⚠️  BLE capture stopped"
        break
    fi
    
    if [[ ! -p "$VIRTUAL_PORT" ]]; then
        echo "[$(date '+%H:%M:%S')] ⚠️  USB serial port stopped"
        break
    fi
    
    echo "[$(date '+%H:%M:%S')] 🔄 Bluetooth → Serial active (check #$counter)"
done

cleanup
