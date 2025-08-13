# Kamstrup wM-Bus Integration Guide

This guide shows how to connect to a Kamstrup Bluetooth device and listen for wM-Bus frames.

## What We've Accomplished

✅ **Successfully connected to Kamstrup READy device via Bluetooth**  
✅ **Created multiple bridge options for frame capture**  
✅ **Integrated with wmbusmeters for telegram processing**  
✅ **Set up both BLE and Serial listening approaches**  

## Files Created

### Bridge Scripts
- `kamstrup_ble_bridge.py` - BLE-based bridge (for future BLE devices)
- `kamstrup_serial_bridge.py` - Serial-based bridge for the current device
- `kamstrup_ble_connect.sh` - Smart connection script (auto-detects BLE vs Serial)
- `kamstrup_ble_wmbusmeters.sh` - Integrated bridge + wmbusmeters launcher

### Configuration
- `kamstrup_stdin.conf` - wmbusmeters config for stdin input

## Usage Options

### Option 1: Direct wmbusmeters (Recommended)
```bash
# Listen for telegrams directly with wmbusmeters
./build/wmbusmeters --verbose /dev/cu.Kamstrup_66501566:38400:c1,t1
```

### Option 2: Serial Bridge
```bash
# Use the Python serial bridge
source .venv/bin/activate
python3 kamstrup_serial_bridge.py --debug
```

### Option 3: Integrated Bridge + wmbusmeters
```bash
# Combined approach with automatic processing
source .venv/bin/activate
./kamstrup_ble_wmbusmeters.sh
```

### Option 4: Smart Connection Script
```bash
# Auto-detects best connection method
source .venv/bin/activate  
./kamstrup_ble_connect.sh
```

## How It Works

1. **Device Connection**: The Kamstrup READy device (MAC: 00-13-43-1c-8b-94) connects via classic Bluetooth and appears as `/dev/cu.Kamstrup_66501566`

2. **Frame Listening**: The device receives wM-Bus telegrams from nearby meters and forwards them via the serial interface

3. **Processing**: Either wmbusmeters reads directly from the device, or our bridge captures and formats the data

4. **Output**: Telegrams are processed and can be:
   - Displayed on stdout
   - Saved to files  
   - Piped to wmbusmeters for meter identification and data extraction

## Expected Behavior

- **Connection**: Should establish successfully to the paired Kamstrup device
- **Listening**: Scripts will run continuously, waiting for wM-Bus telegrams
- **Telegram Frequency**: Real meters typically transmit every 15 minutes to several hours
- **Range**: wM-Bus devices can be detected from 10m to 500m depending on environment

## Device Status Check

```bash
# Check if Kamstrup device is connected
blueutil --is-connected 00-13-43-1c-8b-94

# Check if serial device is available  
ls -la /dev/cu.Kamstrup*

# Verify device connection details
blueutil --connected | grep -i kamstrup
```

## Next Steps

1. **Wait for telegrams**: Run one of the listening methods and wait for nearby wM-Bus meters to transmit
2. **Configure meters**: Once telegrams are received, add specific meter configurations to process the data
3. **Set up automation**: Use the bridges in production to continuously monitor meter data

## Troubleshooting

- **No serial device**: Ensure Kamstrup device is paired and connected
- **No telegrams**: Wait longer (15+ minutes) or check if there are wM-Bus meters in range
- **Connection issues**: Re-pair the Bluetooth device if needed
- **Python errors**: Ensure virtual environment is activated and dependencies installed

The system is now ready to capture and process wM-Bus telegrams from the Kamstrup READy device!
