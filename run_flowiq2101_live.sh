#!/usr/bin/env bash
# Live FlowIQ2101 capture pipeline (macOS)
# Uses bluetooth_to_serial_bridge.py -> vw1871_preprocessor.py -> wmbusmeters
# Meter ID: 74493770  Key: 44E9112D06BD762EC2BFECE57E487C9B
# Wrapper stripping & length alignment handled by preprocessor.
# Cleanup: run pkill -f 'bluetooth_to_serial_bridge' and kill pipeline or press Ctrl-C.

set -euo pipefail

METER_ID=74493770
METER_NAME=FlowIQ2101_$METER_ID
KEY=44E9112D06BD762EC2BFECE57E487C9B
BRIDGE_SCRIPT=bluetooth_to_serial_bridge.py
PREPROC=vw1871_preprocessor.py
WMBUS=./build/wmbusmeters
LOGDIR=live_logs
mkdir -p "$LOGDIR"
SESSION_TS=$(date -u +%Y%m%dT%H%M%SZ)
RAW_LOG="$LOGDIR/raw_${SESSION_TS}.log"
CLEAN_LOG="$LOGDIR/clean_${SESSION_TS}.log"
JSON_LOG="$LOGDIR/json_${SESSION_TS}.log"

# Device hint (adjust as needed): e.g. --target-address AA:BB:CC:DD:EE:FF or --name-contains VW1871
BRIDGE_OPTS="--name-contains VW1871 --auto-connect --debug"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found" >&2; exit 1
fi
if [ ! -x "$WMBUS" ]; then
  echo "wmbusmeters binary missing (run make)" >&2; exit 1
fi

# Trap cleanup (robust Ctrl-C handling)
# - When pressing Ctrl-C (SIGINT), some pipeline elements (sed/awk/tee) or python
#   processes may continue if only the first process got the signal. We kill the
#   entire process group to ensure a clean shutdown.
cleanup() {
  # Prevent recursive trap invocation
  trap - EXIT INT TERM
  echo "Cleaning up..." >&2
  # Target known processes explicitly
  pkill -f "$BRIDGE_SCRIPT" 2>/dev/null || true
  pkill -f 'python.*bluetooth' 2>/dev/null || true
  pkill -f wmbusmeters 2>/dev/null || true
  pkill -f wmbusmetersd 2>/dev/null || true
  # Kill every remaining child in our process group (ignore errors)
  kill -- -$$ 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting FlowIQ2101 live pipeline (Session $SESSION_TS)" >&2

echo "Bridge opts: $BRIDGE_OPTS" >&2
echo "Logs: raw=$RAW_LOG clean=$CLEAN_LOG json=$JSON_LOG" >&2

# 1. Bridge -> Preprocessor -> Extract pure hex -> sanity filter -> wmbusmeters
#    Preprocessor emits lines like: telegram=|HEX| ; we sed out the HEX.
python3 "$BRIDGE_SCRIPT" $BRIDGE_OPTS 2>&1 | tee "$RAW_LOG" \
  | python3 "$PREPROC" 2>"$LOGDIR/preproc_${SESSION_TS}.err" | tee "$CLEAN_LOG" \
  | sed -n 's/^telegram=|\([0-9A-Fa-f]\+\)|$/\1/p' \
  | awk 'length($0)>=40' | tee "$LOGDIR/frames_${SESSION_TS}.hex" \
  | $WMBUS --format=json --silent stdin:hex "$METER_NAME" flowiq2101 $METER_ID $KEY | tee "$JSON_LOG"

# Heartbeat: if you want periodic status, run (in another terminal):
#   tail -f $JSON_LOG | jq -r '.timestamp+" total="+(.total_m3|tostring)' 2>/dev/null

# Cleanup reminder (project guideline):
# pkill -f "$BRIDGE_SCRIPT" ; pkill -f 'python.*bluetooth' ; pkill -f wmbusmeters ; pkill -f wmbusmetersd

