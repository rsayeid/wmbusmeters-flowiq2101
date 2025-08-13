#!/bin/bash

# Test script to process FlowIQ 2101 telegrams from VW1871-250111 Bluetooth bridge

echo "=== FlowIQ 2101 Telegram Processing via VW1871-250111 Bridge ==="
echo

# Test telegrams from Bluetooth capture (trimmed to proper wM-Bus format)
TELEGRAMS=(
    "25442D2C703749741F168D20B4231B02216F07DDD3EFA318553DDFEE5134DB3985C5DB84A7E6E8CB"
    "30442D2C703749741F168D20B5301B0221E679C6FDC8605D397EFA6BF5AF269131BB436557C2B9645DD291F6E57B300DF746B"
    "25442D2C703749741F168D20B6311B022162D85C936A66E35516B05EC37DCB43F93F276F3170AE31"
    "25442D2C703749741F168D20B7321B022135E97E096BCC3E69D1B313BED5956FDFD9738B27B3E57C"
)

echo "Testing ${#TELEGRAMS[@]} captured telegrams..."
echo "Bluetooth Bridge: VW1871-250111"
echo "Water Meter: Kamstrup FlowIQ 2101"
echo "Device ID: 74493770"
echo

for i in "${!TELEGRAMS[@]}"; do
    telegram="${TELEGRAMS[$i]}"
    echo "--- Telegram $((i+1)) ---"
    echo "Hex: ${telegram}"
    echo
    
    # Test with iperl (FlowIQ driver)
    echo "Testing with iperl driver (FlowIQ 2101):"
    echo "$telegram" | ./build/wmbusmeters --silent --format=json stdin FlowIQ2101_${i} iperl 74493770 ""
    echo
    
    # Test with multical21 for comparison
    echo "Testing with multical21 driver (for comparison):"
    echo "$telegram" | ./build/wmbusmeters --silent --format=json stdin FlowIQ2101_${i} multical21 74493770 ""
    echo
    
    echo "----------------------------------------"
    echo
done

echo "=== Analysis Complete ==="
echo
echo "Configuration Summary:"
echo "- Bluetooth Bridge: VW1871-250111 (MAC: 60:6e:41:e3:18:5f)"
echo "- Water Meter Model: Kamstrup FlowIQ 2101"
echo "- Device ID: 74493770" 
echo "- Manufacturer: Kamstrup (442D2C)"
echo "- Media: Cold water"
echo "- Driver: iperl (recommended for FlowIQ 2101)"
echo "- Encryption: AES_CTR (encryption key required for full data decoding)"
echo
echo "Next Steps:"
echo "1. Obtain encryption key from meter installation/configuration"
echo "2. Update config with proper encryption key"
echo "3. Set up continuous Bluetooth bridge for live monitoring"
