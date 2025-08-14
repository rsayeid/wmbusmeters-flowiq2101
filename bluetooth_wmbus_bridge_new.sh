#!/bin/bash

# Bluetooth to Serial Bridge - WM-Bus Device Emulation
# Bridges VW1871 Bluetooth to virtual serial port for wmbusmeters integration

# VW1871 Device Configuration
VW1871_DEVICE="VW1871-250111"
VW1871_UUID="F0F41E39-111C-1E4B-018D-4363539FF186"

# Virtual serial port setup
VIRTUAL_PORT="/dev/ttys001"
VIRTUAL_LINK="/dev/ttys002"

echo "🎯 Bluetooth → Serial WM-Bus Bridge"
echo "==================================="
echo "Target: VW1871-250111 Bluetooth device"
echo "Virtual Device: $VIRTUAL_LINK"
echo "Emulating: WM-Bus device for wmbusmeters"
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo "🧹 Cleaning up bridge service..."
    
    # Kill capture processes
    pkill -f "bluetooth_wmbus_capture" || true
    pkill -f "vw1871_frame_extractor" || true
    
    # Kill socat processes
    pkill -f "socat.*$VIRTUAL_PORT" || true
    pkill -f "socat.*$VIRTUAL_LINK" || true
    
    # Remove virtual serial port files
    rm -f "$VIRTUAL_PORT" || true
    rm -f "$VIRTUAL_LINK" || true
    
    echo "✅ Cleanup complete"
}

# Set trap for cleanup on exit
trap cleanup EXIT INT TERM

echo "📡 Step 1: Creating virtual serial port at $VIRTUAL_LINK"

# Create virtual serial port using socat
echo "Creating socat PTY pair..."
socat pty,raw,echo=0,link="$VIRTUAL_PORT" pty,raw,echo=0,link="$VIRTUAL_LINK" &
SOCAT_PID=$!

# Wait for socat to create the devices
echo "Waiting for socat to create devices..."
sleep 3

# Check if devices were created
if [[ ! -e "$VIRTUAL_LINK" ]]; then
    echo "❌ Failed to create virtual serial port at $VIRTUAL_LINK"
    echo "Checking if socat is running..."
    if kill -0 $SOCAT_PID 2>/dev/null; then
        echo "Socat is running (PID: $SOCAT_PID)"
    else
        echo "Socat process stopped"
        exit 1
    fi
    ls -la /tmp/ttys* 2>/dev/null || echo "No ttys* files in /tmp"
    exit 1
fi

echo "✅ Virtual serial port created: $VIRTUAL_LINK"
echo "   Master port: $VIRTUAL_PORT"

# Show device info
ls -la "$VIRTUAL_LINK" "$VIRTUAL_PORT"

echo ""
echo "📱 Step 2: Starting Bluetooth capture from VW1871"

# Activate virtual environment for Python scripts
if [[ -d ".venv" ]]; then
    echo "Activating Python virtual environment..."
    source .venv/bin/activate
fi

# Start the bluetooth capture and frame extraction pipeline
echo "Starting capture pipeline..."
(
    python3 bluetooth_wmbus_capture.py --device="$VW1871_DEVICE" --uuid="$VW1871_UUID" | \
    python3 vw1871_frame_extractor.py > "$VIRTUAL_PORT"
) &
CAPTURE_PID=$!

echo "✅ Bluetooth capture started (PID: $CAPTURE_PID)"
echo "   Device: $VW1871_DEVICE"
echo "   UUID: $VW1871_UUID"

echo ""
echo "🔄 Bridge Service Running"
echo "========================"
echo "Virtual Serial Port: $VIRTUAL_LINK"
echo "wmbusmeters command: wmbusmeters $VIRTUAL_LINK:38400:c1 FlowIQ2101 flowiq2101 74493770 44E9112D06BD762EC2BFECE57E487C9B"
echo ""
echo "Press Ctrl+C to stop the bridge service"

# Monitor the services
while true; do
    # Check if socat is still running
    if ! kill -0 $SOCAT_PID 2>/dev/null; then
        echo "[$(date '+%H:%M:%S')] ⚠️  Virtual serial port stopped"
        break
    fi
    
    # Check if virtual device still exists
    if [[ ! -e "$VIRTUAL_LINK" ]]; then
        echo "[$(date '+%H:%M:%S')] ⚠️  Device $VIRTUAL_LINK disappeared"
        break
    fi
    
    # Check if capture process is still running
    if ! kill -0 $CAPTURE_PID 2>/dev/null; then
        echo "[$(date '+%H:%M:%S')] ⚠️  Bluetooth capture stopped"
        break
    fi
    
    # Status update every 30 seconds
    echo "[$(date '+%H:%M:%S')] 🟢 Bridge active - $VIRTUAL_LINK ready"
    
    sleep 30
done

echo ""
echo "⚠️  Bridge service stopped"
exit 1
