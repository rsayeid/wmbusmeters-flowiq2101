# VW1871 Wrapper Analysis Results

## Fragment Decoding Results

### FBFBFBF01101
- **Start marker**: `FBFBFBF0` (VW1871 frame delimiter)
- **Header bytes**: `1101`
  - Byte 0: `0x11` = Standard frame type
  - Byte 1: `0x01` = Sequence/control byte (value 1)

### 9FEFE0E0F
- **Data byte**: `9F` (0x9F = 159 decimal) - last payload byte
- **End marker**: `FEFE0E0F` (VW1871 frame terminator)

## Log Analysis Summary

Analyzed 29 VW1871 frames from the BLE capture:

### Key Findings
- **Consistent header**: All frames use `1101` header (type 0x11, sequence 0x01)
- **Frame sizes**: Mostly 49-62 bytes of WM-Bus payload per frame
- **No sequence variation**: All frames show sequence byte = 1 (likely single session)
- **6 incomplete frames**: Missing end markers (transmission cutoffs)

### Header Structure Interpretation
```
FBFBFBF0 | 11 | 01 | <wmbus_payload> | FEFE0E0F
   ↑       ↑    ↑         ↑              ↑
 Start   Type Seq     WM-Bus data      End
```

- **Type 0x11**: Standard WM-Bus frame wrapper
- **Sequence 0x01**: Session or frame counter (static in this capture)
- **Payload**: Actual encrypted FlowIQ2101 telegrams (truncated to ~48-62 bytes)

### Usage
```bash
# Decode specific fragments
.venv/bin/python vw1871_wrapper_parser.py --decode FBFBFBF01101 9FEFE0E0F

# Analyze full log file
.venv/bin/python vw1871_wrapper_parser.py simple_ble_service/logs/ble_session_20250814T002911.jsonl

# Parse hex string directly
.venv/bin/python vw1871_wrapper_parser.py --hex "FBFBFBF01101250825..."
```

The wrapper adds 6 bytes overhead (4-byte start + 2-byte header) plus 4-byte end marker per frame.
