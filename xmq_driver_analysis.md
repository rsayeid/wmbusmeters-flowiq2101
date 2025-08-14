# XMQ Driver Analysis - FlowIQ2101 and Comparison Meters
# Generated: 2025-08-14
# Purpose: Compare FlowIQ2101 driver structure with other detailed water meter drivers

================================================================================
1. CURRENT FLOWIQ2101 DRIVER (Custom)
================================================================================

LOCATION: /Volumes/dev/space/wmblatest/wmbusmeters/drivers/src/flowiq2101.xmq

DETECTION PROBLEM:
- Current detect: mvt = KAM,16,25 (version 25)
- Actual meter: mvt = KAM,16,1f (version 31 = 0x1f)
- Result: Detection fails, falls back to "unknown" driver

KEY FEATURES:
- Manufacturer: KAM (Kamstrup)
- Type: WaterMeter 
- Very detailed field definitions with status lookups
- Advanced error flag mapping (DRY, REVERSE, LEAK, BURST)
- Time-based status fields (time_dry, time_reversed, etc.)
- Temperature monitoring (flow + external)
- Fallback raw_hex field for debugging

CURRENT CODE:
```xmq
driver {
    name           = flowiq2101
    meter_type     = WaterMeter
    manufacturer   = KAM
    model          = flowiq2101
    detect {
        mvt = KAM,16,25  ← PROBLEM: Should be 1f for our meter
        mvt = KAM,07,25
    }
    # ... extensive field definitions ...
}
```

================================================================================
2. KAMPRESS DRIVER (Reference - Same manufacturer)
================================================================================

DETECTION:
- mvt = KAM,01,18 (Kamstrup, pressure sensor, version 24)
- Single version detection (simpler)

STRUCTURE:
- PressureSensor type
- Focused on pressure measurements
- Error flag mapping with descriptive names
- Clean test cases with multiple scenarios
- Unknown fields (alfa, beta) handled gracefully

KEY PATTERN:
```xmq
detect {
    mvt = KAM,01,18  ← Single, specific version
}
fields {
    field {
        name     = status
        quantity = Text
        match {
            measurement_type = Instantaneous
            vif_range        = ErrorFlags
        }
        lookup {
            name            = ERROR_FLAGS
            map_type        = BitToString
            # Detailed error mappings...
        }
    }
}
```

================================================================================
3. IPERL DRIVER (Multi-version water meter)
================================================================================

DETECTION:
- mvt = SEN,68,06
- mvt = SEN,68,07  ← Multiple versions supported!
- mvt = SEN,7c,07

STRUCTURE:
- WaterMeter type (same as FlowIQ2101)
- Simple field set (total, max_flow)
- Multiple version detection patterns
- Encrypted/unencrypted telegram support

KEY PATTERN:
```xmq
detect {
    mvt = SEN,68,06
    mvt = SEN,68,07  ← Supports multiple versions
    mvt = SEN,7c,07
}
```

================================================================================
4. AQUASTREAM DRIVER (Detailed water meter)
================================================================================

DETECTION:
- mvt = IMT,01,07 (single version)

STRUCTURE:
- WaterMeter type
- Library usage for common fields
- Detailed status error mappings
- Battery monitoring
- Tariff support

KEY PATTERN:
```xmq
library {
    use = total_m3,meter_datetime,target_m3,target_date  ← Uses library fields
}
```

================================================================================
5. ANALYSIS & RECOMMENDATIONS
================================================================================

PROBLEM WITH CURRENT FLOWIQ2101:
1. Version mismatch: expects 25, actual meter uses 1f (31)
2. May have too many complex field definitions for initial testing
3. Detection might be too restrictive

SOLUTIONS (in order of preference):

A) FIX VERSION DETECTION (Recommended):
```xmq
detect {
    mvt = KAM,16,1f  ← Fix to match actual meter version
    mvt = KAM,16,25  ← Keep original if other meters use it
    mvt = KAM,07,1f  ← Add if needed
}
```

B) SIMPLIFY FOR TESTING:
- Start with basic total_m3 field only
- Add complexity gradually
- Follow iperl pattern for multi-version support

C) USE BUILT-IN DRIVER:
- Delete custom driver entirely
- Test with built-in flowiq2101 driver
- Check if built-in supports version 1f

IMMEDIATE ACTION:
Fix the version detection in the custom driver:
- Change mvt = KAM,16,25 to mvt = KAM,16,1f
- Test with actual captured frame
- Verify decryption works with correct key

================================================================================
6. FRAME ANALYSIS REFERENCE
================================================================================

YOUR ACTUAL FRAME: 25442D2C703749741F168D20FAA0600221274D02133A410EC22EEBA44BAB7B4E7D1C377D358A

DECODED STRUCTURE:
- Length: 23 (35 bytes)
- Manufacturer: 2D2C (KAM - Kamstrup) ✓
- ID: 70374974 (74493770) ✓  
- Version: 1F (31 decimal) ← Key issue!
- Type: 16 (Cold water meter) ✓
- Encryption: AES_CTR ✓
- Status: Decryption failed (wrong key or access number)

NEXT STEPS:
1. Fix version detection: 25 → 1f
2. Rebuild wmbusmeters
3. Test decryption with frame
4. Verify field extraction works
5. Test with live capture pipeline

================================================================================
7. MULTICAL21 DRIVER (C++ Implementation)
================================================================================

STATUS: Available as C++ driver only (not XMQ)
- Driver name: multical21
- Type: WaterMeter c++
- Location: /Volumes/dev/space/wmblatest/wmbusmeters/src/driver_multical21.cc

NOTES:
- No XMQ version exists for multical21
- Implemented in C++ for performance/complexity reasons
- This is common for well-established drivers
- FlowIQ2101 could potentially follow the same pattern

XMQ vs C++ PATTERN:
- XMQ: Newer, declarative format (flowiq2101, kampress, iperl, aquastream)
- C++: Older, procedural format (multical21, many established drivers)
- Both approaches work equally well with wmbusmeters

IMPLICATIONS FOR FLOWIQ2101:
- Current custom XMQ approach is valid
- Could be converted to C++ if needed
- XMQ is actually more maintainable for field definitions
- Recommendation: Fix XMQ version detection first

================================================================================
