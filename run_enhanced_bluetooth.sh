#!/bin/bash
# Run the enhanced Bluetooth wM-Bus capture with proper environment setup

# Script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Display header
echo "=========================================================="
echo "    ENHANCED BLUETOOTH wM-BUS CAPTURE LAUNCHER"
echo "=========================================================="
echo "This script will properly set up and launch the enhanced"
echo "Bluetooth capture service for FlowIQ2101 and VW1871 devices."
echo ""

# Check for cleanup
check_processes() {
    # Check for running bluetooth processes
    BT_PROCESSES=$(ps aux | grep -E "(bluetooth.*bridge|bluetooth.*capture)" | grep -v grep | wc -l)
    if [ "$BT_PROCESSES" -gt 0 ]; then
        echo "⚠️  WARNING: Found $BT_PROCESSES running Bluetooth processes!"
        ps aux | grep -E "(bluetooth.*bridge|bluetooth.*capture)" | grep -v grep
        echo ""
        read -p "Kill these processes before starting? (y/n): " KILL_CHOICE
        if [[ "$KILL_CHOICE" =~ ^[Yy] ]]; then
            echo "🧹 Cleaning up processes..."
            pkill -f "bluetooth.*bridge" 
            pkill -f "bluetooth.*capture"
            sleep 1
            echo "✅ Cleanup complete"
        else
            echo "⚠️  Continuing with existing processes running (may cause conflicts)"
        fi
    else
        echo "✅ No conflicting Bluetooth processes found"
    fi
}

# Check for virtual environment
check_venv() {
    # Check if we're in a virtual environment
    if [ -z "$VIRTUAL_ENV" ]; then
        echo "🔄 Activating Python virtual environment..."
        if [ -d ".venv" ]; then
            source .venv/bin/activate
            echo "✅ Virtual environment activated"
        elif [ -d "venv" ]; then
            source venv/bin/activate
            echo "✅ Virtual environment activated"
        else
            echo "❌ No virtual environment found (.venv or venv)"
            echo "Creating a new one..."
            python3 -m venv .venv
            source .venv/bin/activate
            echo "✅ New virtual environment created and activated"
            
            # Install required packages
            echo "📦 Installing required packages..."
            pip install bleak
            echo "✅ Packages installed"
        fi
    else
        echo "✅ Already in virtual environment: $VIRTUAL_ENV"
    fi
}

# Check for bluetooth_wmbus_capture_enhanced.py
check_script() {
    if [ ! -f "bluetooth_wmbus_capture_enhanced.py" ]; then
        echo "❌ ERROR: bluetooth_wmbus_capture_enhanced.py not found"
        echo "Make sure you're in the correct directory and the script exists"
        exit 1
    else
        echo "✅ Found enhanced Bluetooth capture script"
    fi
}

# Parse command line arguments for this launcher
SCAN_TIME=20
TIMEOUT=300
VERBOSE=""
FALLBACK=""
ALL_DEVICES=""
DEVICE_ADDRESS=""
OUTPUT=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --scan-time)
            SCAN_TIME="$2"
            shift 2
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE="--verbose"
            shift
            ;;
        --fallback)
            FALLBACK="--fallback"
            shift
            ;;
        --all-devices)
            ALL_DEVICES="--all-devices"
            shift
            ;;
        --device-address)
            DEVICE_ADDRESS="--device-address $2"
            shift 2
            ;;
        --output)
            OUTPUT="--output $2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Available options: --scan-time, --timeout, --verbose, --fallback, --all-devices, --device-address, --output"
            exit 1
            ;;
    esac
done

# Run pre-checks
check_processes
check_venv
check_script

echo ""
echo "🚀 Launching Enhanced Bluetooth wM-Bus Capture..."
echo "📱 Scan time: $SCAN_TIME seconds"
echo "⏱️  Monitoring timeout: $TIMEOUT seconds"
echo ""

# Construct the command
CMD="python bluetooth_wmbus_capture_enhanced.py --scan-time $SCAN_TIME --timeout $TIMEOUT $VERBOSE $FALLBACK $ALL_DEVICES $DEVICE_ADDRESS $OUTPUT"
echo "Running: $CMD"
echo "=========================================================="
echo ""

# Execute the command
eval $CMD

# Remind about cleanup
echo ""
echo "⚠️  REMEMBER TO CLEAN UP AFTER USE:"
echo "pkill -f \"bluetooth.*bridge\" && pkill -f \"bluetooth.*capture\""
echo ""
