#!/bin/bash

echo "=== Testing Different Telegram Formats with KEM Key ==="
echo ""

# The correct key from KEM file
KEY="44E9112D06BD762EC2BFECE57E487C9B"

# Test different telegram variations from our capture
echo "1. Testing with original captured telegram (might have length issues):"
echo "telegram=|25442D2C703749741F168D20BA811F0221524DA1F8A047E5A339E601D542248ED15C2E76C0F26D9F|" > test_telegram_1.txt
./build/wmbusmeters --oneshot --format=json test_telegram_1.txt FlowIQ_test flowiq2101 74493770 $KEY 2>/dev/null || echo "Failed"

echo ""
echo "2. Testing with captured frame 4 (extracted wM-Bus part):"
# Extract just the wM-Bus part from: 25442D2C703749741F168D20B4231B02216F07DDD3EFA318553DDFEE5134DB3985C5DB84A7E6E8CB
echo "telegram=|25442D2C703749741F168D20B4231B02216F07DDD3EFA318553DDFEE5134DB3985C5DB84A7E6E8CB|" > test_telegram_2.txt
./build/wmbusmeters --oneshot --format=json test_telegram_2.txt FlowIQ_test flowiq2101 74493770 $KEY 2>/dev/null || echo "Failed"

echo ""
echo "3. Testing with captured frame 5 (longer telegram):"
# Extract from: 30442D2C703749741F168D20B5301B0221E679C6FDC8605D397EFA6BF5AF269131BB436557C2B9645DD291F6E57B300DF746B
echo "telegram=|30442D2C703749741F168D20B5301B0221E679C6FDC8605D397EFA6BF5AF269131BB436557C2B9645DD291F6E57B300DF746B|" > test_telegram_3.txt
./build/wmbusmeters --oneshot --format=json test_telegram_3.txt FlowIQ_test flowiq2101 74493770 $KEY 2>/dev/null || echo "Failed"

echo ""
echo "4. Testing with multical21 driver instead of flowiq2101:"
echo "telegram=|25442D2C703749741F168D20B4231B02216F07DDD3EFA318553DDFEE5134DB3985C5DB84A7E6E8CB|" > test_telegram_4.txt
./build/wmbusmeters --oneshot --format=json test_telegram_4.txt FlowIQ_test multical21 74493770 $KEY 2>/dev/null || echo "Failed"

echo ""
echo "5. Manual analysis with analyze flag:"
./build/wmbusmeters --analyze=flowiq2101:$KEY 25442D2C703749741F168D20B4231B02216F07DDD3EFA318553DDFEE5134DB3985C5DB84A7E6E8CB

# Cleanup
rm -f test_telegram_*.txt

echo ""
echo "=== Testing Complete ==="
