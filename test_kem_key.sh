#!/bin/bash

echo "=== Testing FlowIQ2101 with Correct KEM Key ==="
echo "Meter ID: 74493770"
echo "Key from KEM: 44E9112D06BD762EC2BFECE57E487C9B"
echo "Telegram: |25442D2C703749741F168D20BA811F0221524DA1F8A047E5A339E601D542248ED15C2E76C0F26D9F|"
echo ""

# Test with flowiq2101 driver
echo "Testing with flowiq2101 driver..."
echo "telegram=|25442D2C703749741F168D20BA811F0221524DA1F8A047E5A339E601D542248ED15C2E76C0F26D9F|" > temp_telegram.txt
./build/wmbusmeters --oneshot --format=json temp_telegram.txt FlowIQ2101_test flowiq2101 74493770 44E9112D06BD762EC2BFECE57E487C9B || echo "flowiq2101 driver failed"

echo ""
echo "Testing with multical21 driver..."
echo "telegram=|25442D2C703749741F168D20BA811F0221524DA1F8A047E5A339E601D542248ED15C2E76C0F26D9F|" > temp_telegram.txt
./build/wmbusmeters --oneshot --format=json temp_telegram.txt FlowIQ2101_test multical21 74493770 44E9112D06BD762EC2BFECE57E487C9B || echo "multical21 driver failed"

rm -f temp_telegram.txt
echo "Test complete!"
