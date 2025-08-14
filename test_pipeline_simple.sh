#!/bin/bash

# Simple pipeline test script
# Tests BLE capture → frame extraction → wmbusmeters in parts

set -e

# Configuration
FRAME_PIPE="/tmp/flowiq2101_frames"
CONFIG_DIR="/tmp/wmbusmeters_flowiq"

echo "🧪 FlowIQ2101 Pipeline Test"
echo "==============================="

# Step 1: Test BLE capture for 8 seconds and extract frames
echo "📡 Step 1: BLE capture and frame extraction..."
rm -f "$FRAME_PIPE" 2>/dev/null || true
mkfifo "$FRAME_PIPE" 2>/dev/null || true

# Capture BLE data for 8 seconds and extract frames
python bluetooth_wmbus_capture.py --name-contains "VW1871-250111" --bridge-mode --print-all --duration 8 | \
while IFS= read -r line; do
    # Look for pure hex lines (no timestamps or info)
    if [[ "$line" =~ ^[0-9A-Fa-f]{100,}$ ]]; then
        echo "📥 Raw VW1871 data (${#line} chars): ${line:0:60}..."
        
        # Extract frames using our extractor
        extracted_frames=$(echo "$line" | python vw1871_frame_extractor.py 2>/dev/null | grep "telegram=" || true)
        
        if [[ -n "$extracted_frames" ]]; then
            echo "$extracted_frames" | while IFS= read -r telegram_line; do
                if [[ "$telegram_line" =~ telegram=\|([^|]+)\| ]]; then
                    frame="${BASH_REMATCH[1]}"
                    echo "✅ Extracted frame (${#frame} chars): ${frame:0:40}..."
                    echo "$frame" >> extracted_frames.txt
                fi
            done
        else
            echo "⚠️  No frames extracted from this data"
        fi
    fi
done

echo ""
echo "📊 Step 2: Frame extraction summary..."
if [[ -f extracted_frames.txt ]]; then
    frame_count=$(wc -l < extracted_frames.txt)
    echo "✅ Extracted $frame_count frames total"
    echo "📝 First few frames:"
    head -3 extracted_frames.txt | while IFS= read -r frame; do
        echo "   ${frame:0:60}..."
    done
else
    echo "❌ No frames were extracted"
    exit 1
fi

echo ""
echo "🔧 Step 3: Test wmbusmeters with extracted frames..."

# Ensure config exists
mkdir -p "$CONFIG_DIR"

# Create minimal wmbusmeters config
cat > "$CONFIG_DIR/wmbusmeters.conf" << 'EOF'
loglevel=verbose
device=stdin:hex
logtelegrams=true
format=json
logfile=/tmp/wmbusmeters_flowiq/wmbusmeters.log
pidfile=/tmp/wmbusmeters_flowiq/wmbusmeters.pid
alarmtimeout=0
verbose=true
EOF

# Create meter config
cat > "$CONFIG_DIR/FlowIQ2101.conf" << 'EOF'
name=FlowIQ2101
driver=flowiq2101
id=74493770
key=44E9112D06BD762EC2BFECE57E487C9B
EOF

# Test processing a few frames
echo "📤 Testing frame processing..."
head -3 extracted_frames.txt | while IFS= read -r frame; do
    echo "Testing frame: ${frame:0:40}..."
    echo "$frame" | ./build/wmbusmeters --useconfig="$CONFIG_DIR/wmbusmeters.conf" --verbose
done

echo ""
echo "✅ Pipeline test complete!"
echo "📁 Extracted frames saved to: extracted_frames.txt"
echo "📋 Config directory: $CONFIG_DIR"

# Cleanup
rm -f "$FRAME_PIPE" 2>/dev/null || true
