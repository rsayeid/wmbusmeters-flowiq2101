#!/bin/bash

# 🚨 COPILOT QUICK REFERENCE - HIGH PRIORITY 🚨
# Use this script as a quick reminder of mandatory procedures

echo "🚨 HIGH PRIORITY COPILOT INSTRUCTIONS REMINDER 🚨"
echo "=================================================="
echo
echo "📋 1. FOLLOW README.md PROCESS"
echo "   ✅ Check /README.md for main wmbusmeters workflow"
echo "   ✅ Check /README_FLOWIQ2101.md for project specifics"
echo "   ✅ Use recommended command patterns"
echo
echo "🔍 2. CHECK EXISTING SCRIPTS FIRST"
echo "   ⚠️  MANDATORY: Search before creating new scripts"
echo "   ✅ Modify existing scripts instead of duplicating"
echo "   📁 Key scripts to check:"
echo "      - bluetooth_to_serial_bridge.py"
echo "      - bluetooth_wmbus_capture.py" 
echo "      - flowiq_pattern_analysis.sh"
echo "      - validate_flowiq_pattern.sh"
echo "      - vw1871_bridge.sh"
echo
echo "🛑 3. CLEANUP ALL SERVICES AFTER USE"
echo "   ⚠️  MANDATORY: Stop all bluetooth/wmbus processes"
echo
echo "🧹 Quick Cleanup Commands:"
echo "   pkill -f \"bluetooth_to_serial_bridge\""
echo "   pkill -f \"bluetooth_wmbus_capture\""
echo "   pkill -f \"wmbusmeters\""
echo "   killall -9 wmbusmeters wmbusmetersd"
echo
echo "✅ Verify Cleanup:"
echo "   ps aux | grep -E \"(bluetooth|wmbus)\" | grep -v grep | grep -v bluetoothd"
echo
echo "🎯 FlowIQ2101 Key Info:"
echo "   Meter ID: 74493770"
echo "   Key: 44E9112D06BD762EC2BFECE57E487C9B"
echo "   Device: VW1871-250111"
echo "   Pattern: 7 compact + 1 full frame"
echo
echo "📖 Read full instructions: cat COPILOT_INSTRUCTIONS.md"
echo "=================================================="
