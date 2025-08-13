#!/usr/bin/env python3
"""
VW1871 wM-Bus Telegram Preprocessor
High Priority: Converts VW1871 BLE Bridge output to wmbusmeters-compatible format

This preprocessor takes VW1871 telegram output and converts it to standard wM-Bus format
that can be processed by wmbusmeters with FlowIQ2101 driver.

Author: GitHub Copilot Assistant
Date: 2025-08-13
"""

import sys
import re
import logging
from typing import Optional, List, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class VW1871Preprocessor:
    """
    Preprocesses VW1871 BLE bridge telegrams for wmbusmeters compatibility.
    
    VW1871 telegrams come in format:
    telegram=|331101250808EC916261A50125442D2C703749741F168D208E320502213A4A3B74FA49CEF847D54C4FB74C4175ED60D3E8D9BCFD|
    
    Standard wM-Bus telegrams expected by wmbusmeters have different structure.
    """
    
    def __init__(self):
        self.processed_count = 0
        
    def extract_telegram_data(self, line: str) -> Optional[str]:
        """Extract telegram hex data from VW1871 bridge output line."""
        # Match telegram=|HEX_DATA| format
        match = re.search(r'telegram=\|([0-9A-Fa-f]+)\|', line)
        if match:
            return match.group(1).upper()
        return None
    
    def analyze_telegram_structure(self, hex_data: str) -> dict:
        """Analyze VW1871 telegram structure."""
        if len(hex_data) < 20:
            return {"valid": False, "error": "Telegram too short"}
            
        try:
            # Parse VW1871 telegram structure
            # Based on observation: 331101250808EC916261A50125442D2C703749741F168D208E320502213A4A...
            length = hex_data[0:2]
            c_field = hex_data[2:4]
            m_field = hex_data[4:8]
            a_field = hex_data[8:20]  # 6 bytes = 12 hex chars (meter ID)
            ci_field = hex_data[20:22] if len(hex_data) > 20 else ""
            payload = hex_data[22:] if len(hex_data) > 22 else ""
            
            return {
                "valid": True,
                "length": length,
                "c_field": c_field,
                "m_field": m_field,
                "a_field": a_field,
                "ci_field": ci_field,
                "payload": payload,
                "total_length": len(hex_data) // 2
            }
        except Exception as e:
            return {"valid": False, "error": str(e)}
    
    def _strip_wrapper(self, hex_data: str) -> Tuple[str, str]:
        """Strip known VW1871 wrapper preamble/trailer if present.

        Wrapper pattern observed: FBFBFBF0 <core> FEFE0E0F
        Returns (core, reason)
        """
        hd = hex_data.lower()
        if hd.startswith('fbfbfbf0') and hd.endswith('fefe0e0f') and len(hd) > 16:
            core = hd[8:-8]
            return core.upper(), 'wrapper-stripped'
        return hex_data.upper(), 'no-wrapper'

    def _locate_real_frame(self, core: str) -> Optional[str]:
        """Locate actual wM-Bus frame inside core by finding length byte 0x30 directly before C-field 0x44 and manufacturer 2D2C.

        Heuristic: look for pattern 30 44 2D 2C 70 37 49 74 (ID little-endian) 1F 16.
        Then use first byte (0x30) as L (total bytes incl length = 49).
        Validate that we have at least L+1 bytes from that point.
        Return the extracted frame (exactly L+1 bytes) as hex string or None.
        """
        pattern = '30442d2c703749741f16'
        idx = core.lower().find(pattern)
        if idx == -1:
            return None
        L = int(core[idx:idx+2], 16)
        needed = (L + 1) * 2
        if len(core) - idx < needed:
            # Not enough bytes; truncated capture
            return None
        frame = core[idx:idx+needed]
        return frame.upper()

    def convert_to_wmbus_format(self, hex_data: str) -> Optional[str]:
        """Convert raw VW1871-captured hex (possibly wrapped) into clean wM-Bus frame suitable for wmbusmeters.

        Steps:
          1. Strip BLE/VW1871 wrapper (FBFBFBF0 ... FEFE0E0F) if present.
          2. Locate real frame start via heuristic (length 0x30 before C=0x44, mfct=2D2C, id=70374974, ver=1F, type=16).
          3. Extract exact L+1 bytes.
          4. Output only that frame hex.
        If heuristic fails, fall back to original (so user can inspect manually).
        """
        core, reason = self._strip_wrapper(hex_data)
        frame = self._locate_real_frame(core)
        if frame:
            logger.info(f"Extracted wM-Bus frame (L=0x{frame[0:2]}): {frame}")
            return frame
        else:
            logger.warning("Heuristic failed to locate inner frame; passing through unmodified")
            return core  # better than dropping; user can post-process
    
    def process_line(self, line: str) -> Optional[str]:
        """Process a single line from VW1871 bridge output."""
        line = line.strip()
        
        # Skip non-telegram lines
        if not line or "telegram=" not in line:
            return None
            
        # Extract telegram data
        hex_data = self.extract_telegram_data(line)
        if not hex_data:
            logger.warning(f"Could not extract telegram from line: {line[:100]}...")
            return None
            
        # Convert to wmbusmeters format
        converted = self.convert_to_wmbus_format(hex_data)
        if converted:
            self.processed_count += 1
            return f"telegram=|{converted}|"
            
        return None
    
    def process_stream(self, input_stream=sys.stdin, output_stream=sys.stdout):
        """Process VW1871 output stream and convert to wmbusmeters format."""
        logger.info("🔧 VW1871 Preprocessor started - converting telegrams for wmbusmeters")
        logger.info("   Input: VW1871 BLE bridge format")
        logger.info("   Output: wmbusmeters-compatible format")
        
        try:
            for line in input_stream:
                processed = self.process_line(line)
                if processed:
                    output_stream.write(processed + "\n")
                    output_stream.flush()
                    logger.info(f"📡 Processed telegram #{self.processed_count}")
                else:
                    # Pass through non-telegram lines as-is
                    if line.strip() and not line.startswith("2025-"):  # Skip timestamp logs
                        output_stream.write(line)
                        
        except KeyboardInterrupt:
            logger.info(f"\n⛔ Preprocessor stopped. Processed {self.processed_count} telegrams.")
        except Exception as e:
            logger.error(f"Error processing stream: {e}")
            raise

def main():
    """Main entry point for VW1871 preprocessor."""
    if len(sys.argv) > 1 and sys.argv[1] in ["-h", "--help"]:
        print("""
VW1871 wM-Bus Telegram Preprocessor

Usage:
    python3 vw1871_preprocessor.py                    # Process stdin
    python3 wmbus_ble_bridge.py | python3 vw1871_preprocessor.py | wmbusmeters ...

This tool converts VW1871 BLE bridge output to wmbusmeters-compatible format.
Designed for high-priority preprocessing of FlowIQ2101 water meter telegrams.
""")
        return
        
    preprocessor = VW1871Preprocessor()
    preprocessor.process_stream()

if __name__ == "__main__":
    main()
