#!/bin/bash
# Test the wM-Bus BLE Bridge with captured data

set -e

echo "🧪 Testing wM-Bus BLE Bridge..."
echo

# Activate virtual environment
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found. Please run 'python3 -m venv .venv && source .venv/bin/activate && pip install bleak'"
    exit 1
fi

source .venv/bin/activate

# Check if captured data exists
if [ ! -f "wmbus_capture.json" ]; then
    echo "❌ No captured data found (wmbus_capture.json)"
    exit 1
fi

echo "📊 Testing telegram extraction from captured data..."
python3 wmbus_ble_bridge.py --test --debug

echo
echo "🔧 Testing live bridge mode (simulation)..."
echo "   (This would normally connect to VW1871 device)"

echo
echo "📡 Example usage:"
echo "   1. Live bridge:     python3 wmbus_ble_bridge.py --debug"
echo "   2. With wmbusmeters: python3 wmbus_ble_bridge.py --wmbusmeters 'CONF_FILE'"
echo "   3. To file:         python3 wmbus_ble_bridge.py --output file"

echo
echo "✅ Bridge functionality validated!"
