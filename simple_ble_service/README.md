# Interactive BLE Passive Logger

A minimal interactive Bluetooth Low Energy exploration & passive data logging tool using the macOS built‑in adapter and the `bleak` Python library.

## Features

- Scan for nearby BLE devices and select one interactively
- Optional direct targeting by address or name fragment
- Connect and enumerate all services & characteristics
- Subscribe to every characteristic supporting `notify` or `indicate`
- Print each incoming notification in a structured, readable format
- Log raw, unmodified payloads (hex + ASCII) to JSONL (enabled by default in `simple_ble_service/logs/`)
- Graceful Ctrl+C handling with automatic disconnect
- Read‑only: never writes or mutates device data

## New Discovery Flags

```bash
--target-address  AA:BB:CC:DD:EE:FF   # Attempt repeated scans until this exact BLE address is seen
--name-contains   fragment             # First device whose name contains fragment (case-insensitive)
--scan-attempts   8                    # (default 5) number of repeated attempts for filtered search
--scan-timeout    10                   # (default 8) seconds per attempt for filtered search
--debug                                  # Show every raw device per attempt
```

If either `--target-address` or `--name-contains` is supplied, the tool skips the interactive list and auto-connects to the first matching device.

## Quick Start

```bash
python simple_ble_service/interactive_ble_service.py --timeout 15
```

Direct target by address:

```bash
python simple_ble_service/interactive_ble_service.py --target-address 00-13-43-1c-8b-94 --scan-attempts 10 --scan-timeout 10 --debug
```

Target by name fragment:

```bash
python simple_ble_service/interactive_ble_service.py --name-contains kamstrup --debug
```

## Troubleshooting Missing Device (e.g. 00-13-43-1c-8b-94)

1. Classic vs BLE: The address you see in macOS Bluetooth UI may belong to a Classic Bluetooth (BR/EDR) device. `bleak` (CoreBluetooth) only discovers BLE (GATT) peripherals.
2. macOS Address Randomization: CoreBluetooth sometimes presents a different (random) address than the hardware MAC; the public MAC may never appear in scans. Rely on name matching (`--name-contains`) if address fails.
3. Ensure Advertising: Some devices stop advertising once already connected by macOS or after a timeout. Disconnect other apps and power-cycle the device.
4. Increase Attempts: Use `--scan-attempts 12 --scan-timeout 12 --debug` for slower or intermittent advertisers.
5. Permissions: Confirm the terminal / IDE has Bluetooth permission (System Settings → Privacy & Security → Bluetooth).
6. Proximity & Interference: Move closer, reduce 2.4GHz congestion, and retry.
7. BLE Only Mode: If device only supports Classic (SPP), it won't appear via BLE APIs.

## Output Example

```text
[2025-08-13T12:34:56.789Z] NOTIF #3 handle=42 len=20
   HEX   4F574E444154415041434B4554...
   ASCII OWNADATA.PACKET
```

## Log Format (JSONL)

Each line resembles:

```json
{
  "ts": "2025-08-13T12:34:56.789012",
  "sender_handle": 42,
  "length": 20,
  "raw_hex": "4F574E...",
  "raw_ascii": "OWNADATA.PACKET"
}
```

All payloads are recorded exactly as received (no parsing, filtering, or mutation).

## Cleanup

No background daemons are started. Exiting the program disconnects the device. To double‑check no related processes remain:

```bash
ps aux | grep -i bluetooth | grep -v grep
```

## Notes

- macOS may require Bluetooth permissions for the terminal application.
- If you encounter permission issues, open System Settings → Privacy & Security → Bluetooth.
- This utility is intentionally simple and does not attempt protocol decoding.

## License

Same as repository license.
