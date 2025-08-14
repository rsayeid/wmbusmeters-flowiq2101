#!/bin/bash

# FlowIQ2101 Live Frame Monitor
# Continuously captures VW1871 BLE data and extracts WM-Bus frames
# Shows live frame data for analysis

set -e

VW1871_DEVICE="VW1871-250111"
CAPTURE_LOG="/tmp/flowiq2101_live_frames.txt"

echo "🌊 FlowIQ2101 Live Frame Monitor"
echo "=================================="
echo "Device: $VW1871_DEVICE"
echo "Capture Log: $CAPTURE_LOG"
echo "Press Ctrl+C to stop"
echo ""

# Initialize log file
echo "# FlowIQ2101 Live Frame Capture - $(date)" > "$CAPTURE_LOG"
echo "# Device: $VW1871_DEVICE" >> "$CAPTURE_LOG"
echo "" >> "$CAPTURE_LOG"

# Counter for frames
frame_count=0
session_start=$(date '+%H:%M:%S')

echo "📡 Starting BLE capture for $VW1871_DEVICE..."
echo "⏱️  Session started at: $session_start"
echo ""

# Continuous BLE capture with frame extraction
python bluetooth_wmbus_capture.py --name-contains "$VW1871_DEVICE" --bridge-mode --print-all --duration 0 | \
while IFS= read -r line; do
    timestamp=$(date '+%H:%M:%S')
    
    # Look for pure hex lines (potential VW1871 data)
    if [[ "$line" =~ ^[0-9A-Fa-f]{100,}$ ]]; then
        hex_length=${#line}
        byte_length=$((hex_length / 2))
        
        echo "[$timestamp] 📥 VW1871 Raw Data: $byte_length bytes (${line:0:60}...)"
        echo "[$timestamp] VW1871_RAW: $line" >> "$CAPTURE_LOG"
        
        # Extract WM-Bus frames
        extracted_frames=$(echo "$line" | python vw1871_frame_extractor.py 2>/dev/null | grep "telegram=" || true)
        
        if [[ -n "$extracted_frames" ]]; then
            echo "$extracted_frames" | while IFS= read -r telegram_line; do
                if [[ "$telegram_line" =~ telegram=\|([^|]+)\| ]]; then
                    frame="${BASH_REMATCH[1]}"
                    frame_count=$((frame_count + 1))
                    frame_length=${#frame}
                    
                    echo "[$timestamp] ✅ Frame #$frame_count: $((frame_length / 2)) bytes (${frame:0:40}...)"
                    echo "[$timestamp] WMBUS_FRAME: $frame" >> "$CAPTURE_LOG"
                    
                    # Basic frame analysis
                    if [[ "$frame" =~ ^25442D2C703749741F16 ]]; then
                        echo "[$timestamp]    📊 Type: FlowIQ2101 Compact Frame (0x25)"
                    elif [[ "$frame" =~ ^30442D2C703749741F16 ]]; then
                        echo "[$timestamp]    📊 Type: FlowIQ2101 Full Frame (0x30)"
                    else
                        echo "[$timestamp]    ⚠️  Type: Unknown frame format"
                    fi
                fi
            done
        else
            echo "[$timestamp] ⚠️  No WM-Bus frames extracted from this data"
        fi
        
        echo ""
        
    elif [[ -n "$line" ]]; then
        # BLE info/status messages
        if [[ "$line" == *"Connected to"* ]]; then
            echo "[$timestamp] 🔗 $line"
        elif [[ "$line" == *"Disconnected from"* ]]; then
            echo "[$timestamp] 🔌 $line"
        elif [[ "$line" == *"Frame captured"* ]]; then
            echo "[$timestamp] 📊 $line"
        fi
    fi
done

echo ""
echo "📊 Session ended at: $(date '+%H:%M:%S')"
echo "💾 Frames saved to: $CAPTURE_LOG"
