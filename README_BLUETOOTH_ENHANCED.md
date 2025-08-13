# Enhanced Bluetooth wM-Bus Telegram Capture

This script provides advanced monitoring capabilities for capturing wM-Bus telegrams via Bluetooth, specifically designed for FlowIQ2101 meters and VW1871 concentrators.

## Features

- **Interactive Timeout**: Allows user to specify monitoring duration
- **Enhanced Data Display**: Shows all received data with detailed formatting
- **Comprehensive Logging**: Records everything the service goes through
- **Telegram Analysis**: Attempts to identify specific wM-Bus telegram formats
- **Progress Feedback**: Live updates during scanning and monitoring
- **Fallback Mode**: Connect to any nearby devices if no targets found
- **Specific Device Connection**: Connect to a particular device by address
- **Enhanced Device Discovery**: Better detection of compatible devices

## Requirements

- Python 3.7+
- Bleak library (`pip install bleak`)
- Active Python virtual environment (`.venv`)
- Bluetooth-enabled system
- Compatible Bluetooth wM-Bus devices (FlowIQ2101, VW1871, etc.)

## Usage

```bash
# Activate virtual environment first
source .venv/bin/activate

# Basic usage (interactive)
python bluetooth_wmbus_capture_enhanced.py

# Connect to all nearby devices (not just target patterns)
python bluetooth_wmbus_capture_enhanced.py --all-devices

# Specify a longer scan time
python bluetooth_wmbus_capture_enhanced.py --scan-time 30

# Connect to a specific device by address
python bluetooth_wmbus_capture_enhanced.py --device-address 00:11:22:33:44:55

# Fallback mode (try any nearby devices if no targets found)
python bluetooth_wmbus_capture_enhanced.py --fallback

# Specify monitoring duration
python bluetooth_wmbus_capture_enhanced.py --timeout 600

# Custom output file
python bluetooth_wmbus_capture_enhanced.py --output my_capture.json

# Bridge mode (output raw hex for pipe to other tools)
python bluetooth_wmbus_capture_enhanced.py --bridge-mode
```

## Command Line Arguments

| Argument | Description |
|----------|-------------|
| `--timeout SECONDS` | Monitoring duration in seconds (default: 300) |
| `--scan-time SECONDS` | Device scanning time in seconds (default: 20) |
| `--verbose` | Enable verbose output |
| `--bridge-mode` | Output raw hex data for piping to other tools |
| `--output FILENAME` | Specify output file (default: wmbus_capture_enhanced.json) |
| `--all-devices` | Connect to all discovered Bluetooth devices |
| `--device-address ADDRESS` | Connect to a specific device by address |
| `--fallback` | Try any nearby devices if no target devices found |

## Target Device Detection

The script looks for devices matching these patterns:

- Names containing: FlowIQ, FIQ, Kamstrup, Multical, MC21, VW
- Device IDs containing: 66501566, 250111
- Addresses containing specific patterns for Kamstrup and VW1871 devices
- Devices advertising specific wM-Bus related service UUIDs

## Troubleshooting

If no devices are found:

1. Ensure your Bluetooth is enabled
2. Check that target devices are powered on and nearby
3. Try increasing scan time with `--scan-time 60`
4. Use `--fallback` mode to connect to any nearby devices
5. Try specifying a device address directly with `--device-address`
6. Run with elevated permissions if needed (`sudo` on macOS/Linux)
7. Check the log file for detailed debugging information

## Output Files

- **JSON Data**: `wmbus_capture_enhanced.json` (or specified output file)
- **Log File**: `bluetooth_wmbus_capture_enhanced.log`

## Next Steps

After capturing data, you can analyze it with wmbusmeters:

```bash
wmbusmeters --analyze wmbus_capture_enhanced.json
```

## Cleanup

Always remember to clean up after use:

```bash
# Stop all bluetooth and wmbus processes
pkill -f "bluetooth.*bridge" && pkill -f "bluetooth.*capture" && pkill -f "wmbusmeters"
```

## Transmission Pattern

This tool is designed to detect the FlowIQ2101 transmission pattern:

- 7 compact frames (37 bytes) + 1 full frame (77+ bytes)
- VW1871 may truncate full frames to ~48 bytes

## Example Output

```
🚀 Starting Enhanced wM-Bus Bluetooth Capture
==================================================
⏱️  Enter monitoring duration in seconds [300]: 120

🔍 Scanning for Bluetooth devices for 20.0 seconds...
✅ Discovered 8 Bluetooth devices

📱 Found 8 Bluetooth devices
   1. Unknown (C8:FD:19:A2:B0:32)
   2. VW1871-250111 (78:DB:2F:B1:22:70) 🎯
   3. Unknown (38:0B:3C:AA:E3:F3)
   4. FlowIQ2101 (C1:7B:8A:FE:0D:25) 🎯
   5. Unknown (15:97:D2:0C:11:6B)
   6. Unknown (42:6F:F8:8D:A9:C1)
   7. KAMSTRUP-66501566 (A5:BC:23:EE:D9:F8) 🎯
   8. Unknown (90:21:55:F3:BB:10)

🎯 Will connect to 3 devices:
   1. VW1871-250111 (78:DB:2F:B1:22:70)
   2. FlowIQ2101 (C1:7B:8A:FE:0D:25)
   3. KAMSTRUP-66501566 (A5:BC:23:EE:D9:F8)

🔗 Connecting to devices...
🔗 Connecting to: VW1871-250111 (78:DB:2F:B1:22:70)...
✅ Connected to VW1871-250111
🔍 Discovering services for VW1871-250111...
  Found 3 services, 8 characteristics
  Listening on 2 notification-enabled characteristics
✅ Connected to 3 devices

📡 Monitoring for wM-Bus telegrams...
⏱️  Will monitor for 120 seconds (press Ctrl+C to stop early)

📡 11:23:45 - Data from VW1871-250111
  Size: 37 bytes
  Hex: FB FB FB F0 74 49 37 70 2D 2C 00 00 28 20 55 71 06 55 00 FF 58 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00

🎯 POTENTIAL wM-Bus TELEGRAM! (37 bytes)
  ------------------------------------------------------------
  | FB FB FB F0 74 49 37 70 2D 2C 00 00 28 20 55 71 06 55 
  | 00 FF 58 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 
  | 00
  ------------------------------------------------------------
  📊 Manufacturer: Kamstrup (2D2C)
  📊 Possible Meter ID: 74493770
  📊 VW1871 Concentrator frame detected
  📊 Appears to be a compact frame
```
