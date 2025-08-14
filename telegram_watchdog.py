#!/usr/bin/env python3
"""Telegram watchdog filter.
Reads hex frame lines from stdin, writes them unchanged to stdout.
If no line is seen for --timeout seconds, either exits (exit mode) or sends SIGINT to the parent process group (signal mode).
Usage in pipeline (added automatically when WATCHDOG=1 in run_flowiq2101_live.sh):
   ... | telegram_watchdog.py --timeout 120 --mode exit | ...
"""
from __future__ import annotations
import sys, time, argparse, os, signal, threading

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('--timeout', type=int, default=120, help='Seconds of inactivity before action')
    ap.add_argument('--mode', choices=['exit','signal'], default='exit', help='exit: exit with code 124; signal: send SIGINT to parent pgid')
    return ap.parse_args()

def main():
    args = parse_args()
    last = time.time()
    lock = threading.Lock()
    stop = threading.Event()

    def watchdog():
        while not stop.is_set():
            time.sleep(1)
            if time.time() - last > args.timeout:
                sys.stderr.write(f"[watchdog] No frames for {args.timeout}s -> action {args.mode}\n")
                sys.stderr.flush()
                if args.mode == 'exit':
                    os._exit(124)
                else:
                    try:
                        os.killpg(os.getppid(), signal.SIGINT)
                    except Exception as e:
                        sys.stderr.write(f"[watchdog] signal failed: {e}\n")
                    os._exit(124)

    threading.Thread(target=watchdog, daemon=True).start()

    for line in sys.stdin:
        if line.strip():
            with lock:
                last = time.time()
        sys.stdout.write(line)
        sys.stdout.flush()
    stop.set()

if __name__ == '__main__':
    main()
