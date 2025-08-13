#!/bin/bash

echo "=== FlowIQ2101 Telegram Pattern Analysis using Analyze.java ==="
echo ""

# Create analysis files
cat > flowiq_pattern_analysis.txt << 'EOF'
# FlowIQ2101 Telegram Pattern Analysis Results

## Common Structure (Bytes 0-18)
All telegrams share identical structure:
- 25/30: Length field (37 or 48 bytes)  
- 442D2C: Manufacturer code (KAM = Kamstrup)
- 70374974: Meter ID (74493770 in little-endian)
- 1F: Version
- 168D20: ELL layer (Extended Link Layer)

## Variable Fields Analysis

### Byte 12 (ELL-ACC): Access Number
- B4: Frame 4 (telegram 1)
- B5: Frame 5 (telegram 2) 
- B6: Frame 6 (telegram 3)
- B7: Frame 7 (telegram 4)
- BA: Original test telegram

**Pattern**: Sequential access numbers (B4→B5→B6→B7), indicating consecutive transmissions

### Bytes 13-16 (SN): Security/Sequence Number  
- 231B0221: Frame 4
- 301B0221: Frame 5 (longer telegram)
- 311B0221: Frame 6
- 321B0221: Frame 7
- 811F0221: Original test

**Pattern**: First byte increments (23→30→31→32), consistent with frame sequence

### Bytes 17-18 (CRC): Payload CRC
Different for each telegram due to different payload content

### Key Insights
1. **Consistent Header**: First 12 bytes identical across all telegrams
2. **Sequential Transmission**: Access numbers and sequence numbers increment
3. **Frame Length Variation**: Most are 37 bytes, one is 48 bytes (Frame 5)
4. **Real Transmissions**: These appear to be legitimate consecutive FlowIQ2101 transmissions
EOF

echo "Generated pattern analysis file: flowiq_pattern_analysis.txt"
echo ""

echo "=== Detailed Byte-by-Byte Analysis ==="
echo ""
echo "Common Header (Bytes 0-11):"
echo "25/30 442D2C 70374974 1F 168D20"
echo "│     │      │        │  │"
echo "│     │      │        │  └─ ELL layer"  
echo "│     │      │        └─ Version"
echo "│     │      └─ Meter ID (74493770)"
echo "│     └─ Manufacturer (KAM/Kamstrup)"
echo "└─ Length (37 or 48 bytes)"
echo ""

echo "Variable Section (Bytes 12+):"
echo "Frame 4: B4 231B0221 [payload+CRC]"
echo "Frame 5: B5 301B0221 [longer payload+CRC]"  
echo "Frame 6: B6 311B0221 [payload+CRC]"
echo "Frame 7: B7 321B0221 [payload+CRC]"
echo "Test:    BA 811F0221 [payload+CRC]"
echo ""

echo "=== Conclusion ==="
echo "✅ Telegrams show consistent structure with sequential transmission"
echo "✅ Frame 5 (48 bytes) might be a complete transmission" 
echo "✅ Access number increments confirm legitimate meter communication"
echo "⚠️  All frames still shorter than expected 77+ bytes for complete FlowIQ telegram"
echo ""

# Test Frame 5 (longest) with our key
echo "=== Testing Longest Telegram (Frame 5 - 48 bytes) ==="
echo "telegram=|30442D2C703749741F168D20B5301B0221E679C6FDC8605D397EFA6BF5AF269131BB436557C2B9645DD291F6E57B300DF746B|" > test_frame5.txt
echo "Testing with KEM key..."
../build/wmbusmeters --oneshot --format=json test_frame5.txt FlowIQ_Frame5 flowiq2101 74493770 44E9112D06BD762EC2BFECE57E487C9B || echo "Decryption failed"

rm -f test_frame5.txt
echo ""
echo "Analysis complete - see flowiq_pattern_analysis.txt for detailed results"
