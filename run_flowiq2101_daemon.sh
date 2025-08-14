#!/bin/bash

# FlowIQ2101 Live Data Pipeline to wmbusmeters daemon
# This script captures live BLE data, extracts WM-Bus frames, and feeds them to wmbusmeters daemon

# Exit on any error
set -e

# FlowIQ2101 Configuration
METER_ID="74493770"
METER_KEY="44E9112D06BD762EC2BFECE57E487C9B"
VW1871_DEVICE="VW1871-250111"

# wmbusmeters configuration
WMBUS_CONFIG_DIR="/tmp/wmbusmeters_flowiq"
WMBUS_CONFIG_FILE="$WMBUS_CONFIG_DIR/wmbusmeters.conf"
METER_CONFIG_FILE="$WMBUS_CONFIG_DIR/FlowIQ2101.conf"

echo "=== FlowIQ2101 Live Data Pipeline ==="
echo "Meter ID: $METER_ID"
echo "Device: $VW1871_DEVICE"
echo "Configuration: $WMBUS_CONFIG_DIR"

# Clean up any previous processes
echo "Cleaning up previous processes..."
pkill -f "bluetooth_wmbus_capture" || true
pkill -f "vw1871_frame_extractor" || true
pkill -f "wmbusmeters.*stdin:hex" || true
sleep 2

# Create configuration directory
mkdir -p "$WMBUS_CONFIG_DIR"

# Create wmbusmeters main configuration
cat > "$WMBUS_CONFIG_FILE" << EOF
# wmbusmeters configuration for FlowIQ2101 daemon mode
loglevel=verbose
device=stdin:hex
logtelegrams=true
format=json
meterfiles=$WMBUS_CONFIG_DIR
meterfilesaction=overwrite
logfile=$WMBUS_CONFIG_DIR/wmbusmeters.log
# Timer set to 0 for continuous processing (no timeout)
alarmtimeout=0
alarmexpectedactivity=NONE
EOF

# Create FlowIQ2101 meter configuration  
cat > "$METER_CONFIG_FILE" << EOF
# FlowIQ2101 water meter configuration
name=FlowIQ2101
type=flowiq2101
id=$METER_ID
key=$METER_KEY
# Use JSON format for structured output
json=true
# Add extra debugging for terminal output
verbose=true
EOF

echo "Created configurations:"
echo "  Main config: $WMBUS_CONFIG_FILE"
echo "  Meter config: $METER_CONFIG_FILE"

# Test frame extractor with a sample
echo "Testing frame extractor..."
source .venv/bin/activate
test_result=$(echo "FBFBFBF0590125442D2C703749741F168D20FAA0600221274D02133A410EC22EEBA44BAB7B4E7D1C377D358AFEFE0E0F" | python vw1871_frame_extractor.py 2>/dev/null || echo "ERROR")
if [[ "$test_result" =~ ^25442D2C ]]; then
    echo "✓ Frame extractor working: extracted ${#test_result} character frame"
else
    echo "⚠ Frame extractor test failed: $test_result"
fi

# Create named pipe for frame data
FRAME_PIPE="/tmp/flowiq2101_frames"
rm -f "$FRAME_PIPE"
mkfifo "$FRAME_PIPE"
echo "Created frame pipe: $FRAME_PIPE"

# Function to cleanup on exit
cleanup() {
    echo "Cleaning up..."
    pkill -f "bluetooth_wmbus_capture" || true
    pkill -f "vw1871_frame_extractor" || true
    pkill -f "wmbusmeters.*stdin:hex" || true
    rm -f "$FRAME_PIPE"
    echo "Cleanup complete"
}
trap cleanup EXIT

# Start the BLE capture -> frame extraction pipeline
echo "Starting BLE capture and frame extraction pipeline..."

# Start BLE capture, extract frames, and send to pipe
(
    # Activate virtual environment
    source .venv/bin/activate
    
    echo "Starting bluetooth capture targeting: $VW1871_DEVICE"
    
    # Start BLE capture with bridge mode for continuous hex output
    python bluetooth_wmbus_capture.py --name-contains "$VW1871_DEVICE" --bridge-mode --print-all --duration 0 | \
    while read -r line; do
        # Check if line contains hex data (basic pattern matching)
        if [[ "$line" =~ ^[0-9A-Fa-f]{20,}$ ]]; then
            echo "[$(date '+%H:%M:%S')] VW1871 Raw Data (${#line} chars): $line"
            
            # Pass to frame extractor and capture output
            extracted=$(echo "$line" | python vw1871_frame_extractor.py 2>/dev/null | grep "telegram=")
            
            if [[ -n "$extracted" ]]; then
                # Parse the telegram output format: telegram=|frame|
                if [[ "$extracted" =~ telegram=\|([^|]+)\| ]]; then
                    frame="${BASH_REMATCH[1]}"
                    echo "[$(date '+%H:%M:%S')] ✓ Extracted WM-Bus frame (${#frame} chars): $frame"
                    echo "$frame" > "$FRAME_PIPE"
                else
                    echo "[$(date '+%H:%M:%S')] ⚠ Unexpected extractor output: $extracted"
                fi
            fi
        elif [[ -n "$line" ]]; then
            echo "[$(date '+%H:%M:%S')] BLE Info: $line"
        fi
    done
) &

BLE_PID=$!
echo "Started BLE capture pipeline (PID: $BLE_PID)"

# Give BLE capture time to start
sleep 3

# Start wmbusmeters daemon reading from the pipe
echo "Starting wmbusmeters daemon..."
echo "Command: ./build/wmbusmeters --useconfig=$WMBUS_CONFIG_FILE"

# Read from pipe and feed to wmbusmeters
(
    echo "[$(date '+%H:%M:%S')] 📡 wmbusmeters daemon listening for frames..."
    frame_count=0
    while read -r frame < "$FRAME_PIPE"; do
        if [[ -n "$frame" && "$frame" =~ ^[0-9A-Fa-f]+$ ]]; then
            ((frame_count++))
            echo "[$(date '+%H:%M:%S')] 🔄 Processing frame #$frame_count: $frame"
            
            # Feed to wmbusmeters and capture output
            result=$(echo "$frame" | ./build/wmbusmeters --useconfig="$WMBUS_CONFIG_FILE" --format=json stdin:hex FlowIQ2101 flowiq2101 "$METER_ID" "$METER_KEY" 2>&1)
            
            if [[ $? -eq 0 ]]; then
                echo "[$(date '+%H:%M:%S')] ✅ wmbusmeters result:"
                echo "$result" | jq . 2>/dev/null || echo "$result"
            else
                echo "[$(date '+%H:%M:%S')] ❌ wmbusmeters error:"
                echo "$result"
            fi
            echo "----------------------------------------"
        fi
    done
) &

WMBUS_PID=$!
echo "Started wmbusmeters daemon (PID: $WMBUS_PID)"

# Monitor the processes
echo "=== Pipeline running ==="
echo "BLE Capture PID: $BLE_PID"  
echo "wmbusmeters PID: $WMBUS_PID"
echo "Frame pipe: $FRAME_PIPE"
echo "Logs: $WMBUS_CONFIG_DIR/wmbusmeters.log"
echo "Press Ctrl+C to stop"
echo "========================================"

# Wait for processes and show status
status_count=0
while true; do
    if ! kill -0 $BLE_PID 2>/dev/null; then
        echo "[$(date '+%H:%M:%S')] ❌ ERROR: BLE capture process died"
        break
    fi
    
    if ! kill -0 $WMBUS_PID 2>/dev/null; then
        echo "[$(date '+%H:%M:%S')] ❌ ERROR: wmbusmeters process died"
        break
    fi
    
    ((status_count++))
    echo "[$(date '+%H:%M:%S')] 🔄 Pipeline active (check #$status_count) - Waiting for FlowIQ2101 telegrams..."
    
    # Show recent log entries if available
    if [[ -f "$WMBUS_CONFIG_DIR/wmbusmeters.log" ]]; then
        echo "  📝 Recent log activity:"
        tail -n 2 "$WMBUS_CONFIG_DIR/wmbusmeters.log" 2>/dev/null | sed 's/^/     /' || echo "     (no recent log entries)"
    fi
    
    sleep 15
done

echo "Pipeline stopped"
