#!/usr/bin/env bash
# Live FlowIQ2101 capture pipeline (macOS)
# Produces cleaned hex frames on stdout for piping into native wmbusmeters.
# Example usage:
#   ./run_flowiq2101_live.sh | \
#     ./build/wmbusmeters --format=json --silent stdin:hex FlowIQ2101_74493770 flowiq2101 74493770 44E9112D06BD762EC2BFECE57E487C9B
# Integrated Bluetooth capture + preprocessing only (no internal wmbusmeters invoke).
# Interactive options:
#   Prompts at start (if TTY) to send frames to stdout or a FIFO (named pipe).
# Non-interactive overrides / flags:
#   --no-prompt          Skip prompt (for automation)
#   --fifo               Force FIFO mode
#   --stdout             Force stdout mode (default)
#   --fifo-path=/path    Set custom FIFO path (default /tmp/wmbus_frames.pipe)
#   QUIET_FRAMES=1       Suppress stdout frames when in FIFO mode
# Meter ID: 74493770  Key: 44E9112D06BD762EC2BFECE57E487C9B
# Guidelines: reuse existing tooling, ensure cleanup.

set -euo pipefail
MAIN_PGID=$$

############################################
# Configuration
############################################
METER_ID=74493770
METER_NAME=FlowIQ2101_$METER_ID
KEY=44E9112D06BD762EC2BFECE57E487C9B

CAPTURE_SCRIPT=bluetooth_wmbus_capture.py          # Bluetooth capture script
PREPROC=vw1871_frame_extractor.py                  # Extract frames from VW1871 notifications (2025-08-14)

LOGDIR=live_logs
mkdir -p "$LOGDIR"
SESSION_TS=$(date -u +%Y%m%dT%H%M%SZ)
RAW_LOG="$LOGDIR/raw_${SESSION_TS}.log"
CLEAN_LOG="$LOGDIR/clean_${SESSION_TS}.log"
FRAMES_LOG="$LOGDIR/frames_${SESSION_TS}.hex"
PREPROC_ERR="$LOGDIR/extractor_${SESSION_TS}.err"
FRAME_META_LOG="$LOGDIR/frame_meta_${SESSION_TS}.log"

# Capture options (adjust as needed)
SCAN_TIME=${SCAN_TIME:-10}
DURATION=${DURATION:-0}  # seconds for capture script (0 = infinite)
DEVICE_HINT="--name-contains VW1871"
EXTRA_CAPTURE_OPTS="--auto-connect --debug --bridge-mode --print-all"

# Auto stop after N minutes (0 = no limit)
STOP_AFTER_MINUTES=5

# Output mode defaults (interactive prompt will override if TTY):
#   stdout  - hex frames to stdout (pipe into wmbusmeters)
#   fifo    - write frames into named pipe AND still tee to stdout (unless QUIET_FRAMES=1)
OUTPUT_MODE="stdout"
FIFO_PATH="/tmp/wmbus_frames.pipe"
QUIET_FRAMES=${QUIET_FRAMES:-0}
NO_PROMPT=0
IGNORE_CONFLICTS=${IGNORE_CONFLICTS:-0}
KILL_CONFLICTS=${KILL_CONFLICTS:-0}
HEARTBEAT=${HEARTBEAT:-0}
HEARTBEAT_INTERVAL=${HEARTBEAT_INTERVAL:-30}
DEBUG_SCRIPT=${DEBUG_SCRIPT:-0}
WATCHDOG=${WATCHDOG:-0}
WATCHDOG_TIMEOUT=${WATCHDOG_TIMEOUT:-120}
WATCHDOG_MODE=${WATCHDOG_MODE:-exit} # exit|signal
SPLIT_MULTI_FRAMES=${SPLIT_MULTI_FRAMES:-1}
MIN_HEX_LEN=${MIN_HEX_LEN:-30} # default lowered to include compact frames
COMPACT=${COMPACT:-0} # legacy shortcut (now redundant; keeps compatibility)
LOG_FRAMES=${LOG_FRAMES:-0}
for arg in "$@"; do
  case "$arg" in
    --no-prompt) NO_PROMPT=1 ; shift ;;
  --fifo) OUTPUT_MODE=fifo ; NO_PROMPT=1 ; shift ;;
  --stdout) OUTPUT_MODE=stdout ; NO_PROMPT=1 ; shift ;;
    --fifo-path=*) FIFO_PATH="${arg#*=}" ; shift ;;
  --duration=*) DURATION="${arg#*=}" ; shift ;;
  --heartbeat) HEARTBEAT=1 ; shift ;;
  --heartbeat-interval=*) HEARTBEAT_INTERVAL="${arg#*=}" ; shift ;;
  --debug-script) DEBUG_SCRIPT=1 ; shift ;;
  --ignore-conflicts) IGNORE_CONFLICTS=1 ; shift ;;
  --kill-conflicts) KILL_CONFLICTS=1 ; shift ;;
  --watchdog) WATCHDOG=1 ; shift ;;
  --watchdog-timeout=*) WATCHDOG_TIMEOUT="${arg#*=}" ; shift ;;
  --watchdog-mode=*) WATCHDOG_MODE="${arg#*=}" ; shift ;;
  --no-splitter) SPLIT_MULTI_FRAMES=0 ; shift ;;
  --min-len=*|--min-hex-len=*) MIN_HEX_LEN="${arg#*=}" ; shift ;;
  --compact) COMPACT=1 ; shift ;;
  --log-frames) LOG_FRAMES=1 ; shift ;;
  esac
done

# Compact mode convenience: if user explicitly wants larger (classic) threshold they can set MIN_HEX_LEN=40
if [ "$COMPACT" = 1 ] && [ "${MIN_HEX_LEN}" -gt 30 ]; then
  MIN_HEX_LEN=30
fi

prompt_output_mode() {
  [ -t 0 ] || return 0  # non-interactive stdin
  [ "$NO_PROMPT" = 1 ] && return 0
  echo "Select output target for cleaned hex frames:" >&2
  echo "  1) Stdout (pipe to wmbusmeters) [default]" >&2
  echo "  2) Named pipe (FIFO) -> $FIFO_PATH" >&2
  read -r -p "Choice (1/2) : " choice || return 0
  case "$choice" in
    2)
      OUTPUT_MODE=fifo
      read -r -p "Enter FIFO path [$FIFO_PATH]: " inp || true
      [ -n "$inp" ] && FIFO_PATH="$inp"
      ;;
    *) OUTPUT_MODE=stdout ;;
  esac
}

############################################
# Functions
############################################
activate_venv() {
  if [ -z "${VIRTUAL_ENV:-}" ]; then
    if [ -d ".venv" ]; then
      echo "Activating virtual environment (.venv)" >&2
      # shellcheck disable=SC1091
      source .venv/bin/activate || echo "Warning: failed to activate .venv" >&2
    fi
  fi
}

check_requirements() {
  command -v python3 >/dev/null || { echo "python3 not found" >&2; exit 1; }
  [ -f "$CAPTURE_SCRIPT" ] || { echo "Capture script not found: $CAPTURE_SCRIPT" >&2; exit 1; }
  [ -f "$PREPROC" ] || { echo "Preprocessor not found: $PREPROC" >&2; exit 1; }
}

warn_conflicts() {
  # Robust process conflict check that won't abort script under pipefail when no matches
  local listing pc
  listing=$(ps aux | grep -E "(bluetooth_wmbus_capture|wmbusmeters)" | grep -v grep || true)
  pc=$(printf "%s\n" "$listing" | sed '/^$/d' | wc -l | tr -d ' ')
  [ "$pc" -eq 0 ] && return 0
  echo "Detected $pc potentially conflicting processes:" >&2
  printf "%s\n" "$listing" >&2
  if [ "$KILL_CONFLICTS" = 1 ]; then
    echo "--kill-conflicts active: terminating listed processes" >&2
    # Extract PIDs (second column) and kill
    echo "$listing" | awk '{print $2}' | xargs -r kill -INT 2>/dev/null || true
    sleep 1
    return 0
  fi
  if [ "$IGNORE_CONFLICTS" = 1 ]; then
    echo "--ignore-conflicts active: proceeding immediately" >&2
    return 0
  fi
  echo "Press Ctrl+C now to abort or continuing in 5s..." >&2
  sleep 5
}

portable_timeout_prefix() {
  # Echo a command array usable with eval for timeout if available.
  # If neither timeout nor gtimeout exists and STOP_AFTER_MINUTES>0, use background killer.
  if [ "$STOP_AFTER_MINUTES" -le 0 ]; then
    return 0
  fi
  if command -v timeout >/dev/null 2>&1; then
    echo "timeout ${STOP_AFTER_MINUTES}m"
  elif command -v gtimeout >/dev/null 2>&1; then
    echo "gtimeout ${STOP_AFTER_MINUTES}m"
  else
    # Fallback now defered to schedule_auto_stop after capture launch
    return 0
  fi
}

schedule_auto_stop() {
  if [ "$STOP_AFTER_MINUTES" -le 0 ]; then
    return 0
  fi
  if command -v timeout >/dev/null 2>&1 || command -v gtimeout >/dev/null 2>&1; then
    return 0  # handled inline via TIME_PREFIX
  fi
  ( sleep "$((STOP_AFTER_MINUTES*60))"; echo "Auto-stop reached ($STOP_AFTER_MINUTES m)" >&2; kill -INT -$MAIN_PGID ) &
  AUTO_STOP_PID=$!
  echo "[debug] Scheduled fallback auto-stop (PID $AUTO_STOP_PID) in ${STOP_AFTER_MINUTES}m" >&2
}

cleanup() {
  trap - EXIT INT TERM
  echo "Cleaning up (graceful shutdown)..." >&2
  if [ -n "${HEARTBEAT_PID:-}" ]; then
    kill "$HEARTBEAT_PID" 2>/dev/null || true
  fi
  pkill -f "$CAPTURE_SCRIPT" 2>/dev/null || true
  pkill -f 'python.*bluetooth' 2>/dev/null || true
  pkill -f wmbusmeters 2>/dev/null || true  # In case external user started it
  pkill -f wmbusmetersd 2>/dev/null || true
  echo "Cleanup complete" >&2
}
on_sigint() { echo "Interrupt received (Ctrl+C) -> initiating cleanup" >&2; cleanup; exit 130; }
trap on_sigint INT
trap cleanup EXIT TERM

############################################
# Start
############################################
echo "Starting FlowIQ2101 live pipeline (Session $SESSION_TS)" >&2
echo "Logs: raw=$RAW_LOG clean=$CLEAN_LOG frames=$FRAMES_LOG" >&2
if [ "$DEBUG_SCRIPT" = 1 ]; then
  echo "[debug] Script tracing enabled" >&2
  set -x
fi

activate_venv
check_requirements
warn_conflicts
prompt_output_mode

if [ "$OUTPUT_MODE" = fifo ]; then
  if [ ! -p "$FIFO_PATH" ]; then
    echo "Creating FIFO: $FIFO_PATH" >&2
    rm -f "$FIFO_PATH" 2>/dev/null || true
    mkfifo "$FIFO_PATH"
  fi
  echo "Frames will be written to FIFO as well: $FIFO_PATH" >&2
fi

TIME_PREFIX=$(portable_timeout_prefix || true)
if [ -n "${TIME_PREFIX:-}" ]; then
  echo "Auto-stop after ${STOP_AFTER_MINUTES} minute(s) via: $TIME_PREFIX" >&2
fi

echo "Launching capture: $CAPTURE_SCRIPT $DEVICE_HINT --scan-time $SCAN_TIME --duration $DURATION $EXTRA_CAPTURE_OPTS" >&2
echo "[debug] About to exec capture (DEBUG_SCRIPT=$DEBUG_SCRIPT)" >&2
echo "Pipeline: capture -> awk(hex normalize + split) -> frame_extractor -> filter -> (watchdog?) -> frames" >&2
echo "Usage: ./run_flowiq2101_live.sh | wmbusmeters --format=json --silent stdin:hex $METER_NAME flowiq2101 $METER_ID $KEY" >&2
echo "Flags: --ignore-conflicts (skip wait)  --kill-conflicts (auto kill)" >&2
echo "Optional: --heartbeat --heartbeat-interval=N  (env HEARTBEAT=1 HEARTBEAT_INTERVAL=30)" >&2
echo "Optional: --watchdog --watchdog-timeout=N --watchdog-mode=exit|signal (env WATCHDOG=1 WATCHDOG_TIMEOUT=120 WATCHDOG_MODE=exit)" >&2
echo "Optional: --no-splitter (disable multi-frame splitting heuristic)" >&2
echo "Optional: --min-len=N (default 30) or set MIN_HEX_LEN to adjust frame length threshold" >&2
echo "Env overrides: MIN_HEX_LEN, COMPACT=1" >&2
echo "Optional: --log-frames (or LOG_FRAMES=1) per-frame metadata to stderr + frame_meta log" >&2

if [ "$HEARTBEAT" = 1 ]; then
  (
    while true; do
      printf '[heartbeat] %s scan_time=%s duration=%s mode=%s pid=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$SCAN_TIME" "$DURATION" "$OUTPUT_MODE" "$$" >&2
      sleep "$HEARTBEAT_INTERVAL" || break
    done
  ) &
  HEARTBEAT_PID=$!
  echo "Heartbeat started (interval ${HEARTBEAT_INTERVAL}s, pid $HEARTBEAT_PID)" >&2
fi

if [ "$SPLIT_MULTI_FRAMES" = 1 ]; then
TELEGRAM_AWK='function ishex(s){return (s ~ /^[0-9A-Fa-f]+$/)}
function status(){ if (c%10==0){ cmd="date -u +%Y-%m-%dT%H:%M:%SZ"; cmd|getline now; close(cmd); printf "STATUS %s: %d telegrams\n", now, c > "/dev/stderr" }}
function emit(hex){ ++c; printf "telegram=|%s|\n", hex; status() }
/./{ print $0; n=split($0,a,/[\|[:space:]]+/); for(i=1;i<=n;i++){ t=toupper(a[i]); if(length(t)>=MIN && ishex(t)){
  # Multi-frame concatenation: look for repeated FBFBFBF0 blocks terminated by FEFE0E0F
  if (index(t, "FBFBFBF0") && gsub(/FBFBFBF0/, "&", t) > 1) {
    t=toupper(a[i]);
    rest=t;
    while (1) {
      s=index(rest, "FBFBFBF0"); if (s==0) break;
      subrest=substr(rest, s);
      e=index(subrest, "FEFE0E0F"); if (e==0) break;
      frame=substr(subrest, 1, e+7);
  if (length(frame)>=MIN) emit(frame);
      rest=substr(subrest, e+8);
    }
  } else { emit(t) }
}}}
END{cmd="date -u +%Y-%m-%dT%H:%M:%SZ"; cmd|getline now; close(cmd); printf "SESSION SUMMARY %s: total %d telegrams\n", now, c > "/dev/stderr"}'
else
TELEGRAM_AWK='function ishex(s){return (s ~ /^[0-9A-Fa-f]+$/)}
function status(){ if (c%10==0){ cmd="date -u +%Y-%m-%dT%H:%M:%SZ"; cmd|getline now; close(cmd); printf "STATUS %s: %d telegrams\n", now, c > "/dev/stderr" }}
function emit(hex){ ++c; printf "telegram=|%s|\n", hex; status() }
/./{ print $0; n=split($0,a,/[\|[:space:]]+/); for(i=1;i<=n;i++){ t=toupper(a[i]); if(length(t)>=MIN && ishex(t)) emit(t) }}
END{cmd="date -u +%Y-%m-%dT%H:%M:%SZ"; cmd|getline now; close(cmd); printf "SESSION SUMMARY %s: total %d telegrams\n", now, c > "/dev/stderr"}'
fi

set +e  # Allow pipeline to finish gracefully on timeout/INT
build_frame_sink() {
  if [ "$OUTPUT_MODE" = fifo ]; then
    if [ "$QUIET_FRAMES" = 1 ]; then
      # Write frames file and FIFO (suppress stdout frames)
      cat > >(tee "$FRAMES_LOG" > "$FIFO_PATH" >/dev/null)
    else
      # Duplicate to frames file, FIFO, and keep on stdout
      tee "$FRAMES_LOG" >(cat > "$FIFO_PATH")
    fi
  else
    tee "$FRAMES_LOG"
  fi
}

schedule_auto_stop

if [ "$LOG_FRAMES" = 1 ]; then
  echo "Per-frame metadata log: $FRAME_META_LOG" >&2
fi

if [ -n "${TIME_PREFIX:-}" ]; then
  echo "[debug] Using timeout wrapper: $TIME_PREFIX" >&2
  eval $TIME_PREFIX python3 "$CAPTURE_SCRIPT" $DEVICE_HINT --scan-time "$SCAN_TIME" --duration "$DURATION" $EXTRA_CAPTURE_OPTS 2>&1 \
  | tee "$RAW_LOG" \
  | awk -v MIN="$MIN_HEX_LEN" "$TELEGRAM_AWK" \
  | python3 "$PREPROC" 2>"$PREPROC_ERR" | tee "$CLEAN_LOG" \
  | tr -d '\r' \
  | sed -n 's/^telegram=|\([0-9A-Fa-f]\+\)|$/\1/p' \
   | awk -v m="$MIN_HEX_LEN" -v LOG="$LOG_FRAMES" -v MF="$FRAME_META_LOG" '{l=length($0); if(l>=m){print $0; if(LOG){ts=strftime("%Y-%m-%dT%H:%M:%SZ", systime()); type=(l<=100?"compact":"full"); printf("FRAME %s len=%d type=%s hex=%s\n", ts,l,type,$0) > MF; printf("FRAME %s len=%d type=%s\n", ts,l,type) > "/dev/stderr"}}}' \
  | { if [ "$WATCHDOG" = 1 ]; then python3 telegram_watchdog.py --timeout "$WATCHDOG_TIMEOUT" --mode "$WATCHDOG_MODE"; else cat; fi; } | build_frame_sink
else
  python3 "$CAPTURE_SCRIPT" $DEVICE_HINT --scan-time "$SCAN_TIME" --duration "$DURATION" $EXTRA_CAPTURE_OPTS 2>&1 \
    | tee "$RAW_LOG" \
  | awk -v MIN="$MIN_HEX_LEN" "$TELEGRAM_AWK" \
    | python3 "$PREPROC" 2>"$PREPROC_ERR" | tee "$CLEAN_LOG" \
    | tr -d '\r' \
  | sed -n 's/^telegram=|\([0-9A-Fa-f]\+\)|$/\1/p' \
  | awk -v m="$MIN_HEX_LEN" -v LOG="$LOG_FRAMES" -v MF="$FRAME_META_LOG" '{l=length($0); if(l>=m){print $0; if(LOG){ts=strftime("%Y-%m-%dT%H:%M:%SZ", systime()); type=(l<=100?"compact":"full"); printf("FRAME %s len=%d type=%s hex=%s\n", ts,l,type,$0) > MF; printf("FRAME %s len=%d type=%s\n", ts,l,type) > "/dev/stderr"}}}' \
  | { if [ "$WATCHDOG" = 1 ]; then python3 telegram_watchdog.py --timeout "$WATCHDOG_TIMEOUT" --mode "$WATCHDOG_MODE"; else cat; fi; } | build_frame_sink
fi
rc=$?
set -e

echo "Session complete (rc=$rc)"
echo "Artifacts:"
echo "  Raw:     $RAW_LOG"
echo "  Clean:   $CLEAN_LOG"
echo "  Frames:  $FRAMES_LOG"
echo "  Extractor errors: $PREPROC_ERR"

echo "Reminder cleanup commands if needed:" >&2
echo "  pkill -f \"$CAPTURE_SCRIPT\" ; pkill -f wmbusmeters ; pkill -f wmbusmetersd" >&2

exit $rc

