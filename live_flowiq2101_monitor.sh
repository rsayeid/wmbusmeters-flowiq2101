#!/bin/bash

# Live FlowIQ2101 Monitor - Complete BLE → wmbusmeters Pipeline
# Shows real-time frame capture, extraction, and processing

set -e

# Configuration
VW1871_DEVICE="VW1871-250111"
FRAME_PIPE="/tmp/flowiq2101_frames"
CONFIG_DIR="/tmp/wmbusmeters_flowiq"

echo "🚀 FlowIQ2101 Live Monitor"
echo "=========================="
echo "Device: $VW1871_DEVICE"
echo "Pipeline: BLE → Frame Extraction → wmbusmeters"
echo "Note: Driver deleted, will show 'unknown' driver warnings"
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo "🧹 Cleaning up..."
    pkill -f "bluetooth_wmbus_capture" || true
    pkill -f "wmbusmeters" || true
    pkill -f "vw1871_frame_extractor" || true
    rm -f "$FRAME_PIPE" 2>/dev/null || true
    echo "✅ Cleanup complete"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Create configurations
mkdir -p "$CONFIG_DIR"

cat > "$CONFIG_DIR/wmbusmeters.conf" << 'EOF'
loglevel=normal
device=stdin:hex
logtelegrams=true
format=json
alarmtimeout=0
EOF

cat > "$CONFIG_DIR/FlowIQ2101.conf" << 'EOF'
name=FlowIQ2101
driver=unknown
id=74493770
key=44E9112D06BD762EC2BFECE57E487C9B
EOF

echo "📁 Created configurations in: $CONFIG_DIR"

# Create named pipe
rm -f "$FRAME_PIPE" 2>/dev/null || true
mkfifo "$FRAME_PIPE"
echo "📡 Created frame pipe: $FRAME_PIPE"

echo ""
echo "🔄 Starting live monitoring pipeline..."
echo ""

# Start BLE capture and frame extraction
(
    python bluetooth_wmbus_capture.py --name-contains "$VW1871_DEVICE" --bridge-mode --print-all --duration 0 | \
    while IFS= read -r line; do
        # Check for hex data lines (100+ characters, all hex)
        if [[ "$line" =~ ^[0-9A-Fa-f]{100,}$ ]]; then
            echo "[$(date '+%H:%M:%S')] 📥 VW1871 Data (${#line} chars): ${line:0:60}..."
            
            # Extract frames
            extracted=$(echo "$line" | python vw1871_frame_extractor.py 2>/dev/null | grep "telegram=" || true)
            
            if [[ -n "$extracted" ]]; then
                echo "$extracted" | while IFS= read -r telegram_line; do
                    if [[ "$telegram_line" =~ telegram=\|([^|]+)\| ]]; then
                        frame="${BASH_REMATCH[1]}"
                        echo "[$(date '+%H:%M:%S')] ✅ Extracted Frame (${#frame} chars): ${frame:0:50}..."
                        echo "$frame" > "$FRAME_PIPE"
                    fi
                done
            fi
        elif [[ "$line" =~ "Connected to" ]]; then
            echo "[$(date '+%H:%M:%S')] 🔗 $line"
        elif [[ "$line" =~ "Disconnected from" ]]; then
            echo "[$(date '+%H:%M:%S')] 🔌 $line"
        fi
    done
) &

BLE_PID=$!

# Start wmbusmeters to process frames
(
    sleep 2  # Give BLE time to start
    echo "[$(date '+%H:%M:%S')] 🔧 Starting wmbusmeters daemon..."
    ./build/wmbusmeters --useconfig="$CONFIG_DIR/wmbusmeters.conf" < "$FRAME_PIPE"
) &

WMBUS_PID=$!

echo "📊 Pipeline Status:"
echo "   BLE Capture PID: $BLE_PID"
echo "   wmbusmeters PID: $WMBUS_PID"
echo "   Frame Pipe: $FRAME_PIPE"
echo ""
echo "🎯 Monitoring live FlowIQ2101 data..."
echo "   - BLE notifications from VW1871-250111"
echo "   - Frame extraction with VW1871 wrapper removal"
echo "   - Live feeding to wmbusmeters (unknown driver)"
echo ""
echo "Press Ctrl+C to stop monitoring"
echo "========================================"

# Keep the script running and show periodic status
counter=0
while true; do
    sleep 15
    counter=$((counter + 1))
    
    # Check if processes are still running
    if ! kill -0 $BLE_PID 2>/dev/null; then
        echo "[$(date '+%H:%M:%S')] ⚠️  BLE capture stopped, restarting..."
        break
    fi
    
    if ! kill -0 $WMBUS_PID 2>/dev/null; then
        echo "[$(date '+%H:%M:%S')] ⚠️  wmbusmeters stopped, restarting..."
        break
    fi
    
    echo "[$(date '+%H:%M:%S')] 🔄 Pipeline active (check #$counter) - Monitoring FlowIQ2101..."
done

cleanup
