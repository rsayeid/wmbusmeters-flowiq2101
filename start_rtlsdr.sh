#!/bin/bash

# RTL-SDR wM-Bus Reception Script
# Usage: ./start_rtlsdr.sh [mode]
# Modes: c1, t1, s1, all (default)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WMBUSMETERS_DIR="/Volumes/dev/space/wmblatest/wmbusmeters"

echo "=== RTL-SDR wM-Bus Reception ==="
echo

# Check if RTL-SDR is connected
if ! rtl_test -t 2>/dev/null | grep -q "Found.*device"; then
    echo "⚠️  No RTL-SDR device detected!"
    echo
    echo "To use RTL-SDR with wmbusmeters, you need:"
    echo "1. 📻 RTL-SDR USB dongle (RTL2832U-based)"
    echo "2. 🔌 Connect to USB port"
    echo "3. 📡 Place near wM-Bus transmitting meters"
    echo
    echo "🛒 Recommended devices:"
    echo "   • RTL-SDR Blog v3 (~$25)"
    echo "   • NooElec NESDR Smart (~$30)"
    echo "   • Generic RTL2832U dongles (~$15)"
    echo
    echo "Once connected, run this script again."
    exit 1
fi

echo "✓ RTL-SDR device detected!"

# Change to wmbusmeters directory
cd "$WMBUSMETERS_DIR" || {
    echo "✗ Cannot find wmbusmeters directory: $WMBUSMETERS_DIR"
    exit 1
}

# Create output directory
mkdir -p /tmp/wmbusmeters

# Determine mode
MODE="${1:-all}"

echo "Starting RTL-SDR wM-Bus reception..."
echo "Mode: $MODE"
echo "Output: /tmp/wmbusmeters/"
echo "Log: /tmp/wmbusmeters.log"
echo
echo "Press Ctrl+C to stop reception"
echo "=" | tr '=' '-' | head -c 50; echo

case "$MODE" in
    "c1")
        echo "🎯 Mode C1 - 868.95 MHz (Most common in EU)"
        ./build/wmbusmeters --config="$HOME/.config/wmbusmeters/rtlsdr.conf" rtlwmbus:c1
        ;;
    "t1")
        echo "🎯 Mode T1 - 868.3 MHz"
        ./build/wmbusmeters --config="$HOME/.config/wmbusmeters/rtlsdr.conf" rtlwmbus:t1
        ;;
    "s1")
        echo "🎯 Mode S1 - 868.3 MHz"
        ./build/wmbusmeters --config="$HOME/.config/wmbusmeters/rtlsdr.conf" rtlwmbus:s1
        ;;
    "all"|*)
        echo "🎯 All Modes - C1, T1, S1"
        ./build/wmbusmeters --config="$HOME/.config/wmbusmeters/rtlsdr.conf" rtlwmbus:c1,t1,s1
        ;;
esac
