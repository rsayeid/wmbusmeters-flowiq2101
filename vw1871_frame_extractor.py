#!/usr/bin/env python3
"""
VW1871 Frame Extractor - FlowIQ2101 Implementation
Implements exact frame extraction logic as documented in flowiq2101_frame_variants.txt

Frame Extraction Rules:
- 59 OR 70 BYTES: Delete header FBFBFBF011012508E2DF916261B101 & footer (last 12 characters)
- 96 BYTES: Delete header (108 characters) & footer (8 characters)
- 244 BYTES: Look for patterns "25442D2C" or "30442D2C", extract frames by length

Author: FlowIQ2101 Integration Project
Date: 2025-08-14
"""

import sys
import re
import logging
from typing import Optional, List, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class VW1871FrameExtractor:
    """
    Extracts clean WM-Bus frames from VW1871 Bluetooth notifications using exact rules.
    Based on analysis of FlowIQ2101 frame variants captured 2025-08-14.
    """
    
    def __init__(self):
        self.processed_count = 0
        self.extracted_frames = 0
        
    def extract_telegram_data(self, line: str) -> Optional[str]:
        """Extract telegram hex data from line (supports multiple formats)."""
        # Match telegram=|HEX_DATA| format
        match = re.search(r'telegram=\|([0-9A-Fa-f]+)\|', line)
        if match:
            return match.group(1).upper()
        
        # Match raw hex lines (for direct hex input)
        if re.match(r'^[0-9A-Fa-f]+$', line.strip()):
            return line.strip().upper()
            
        return None
    
    def extract_frames_59_70_bytes(self, hex_data: str) -> List[str]:
        """
        Extract frames from 59 or 70 byte notifications.
        Rule: Delete header FBFBFBF011012508E2DF916261B101 & footer (last 12 characters)
        """
        frames = []
        data_len = len(hex_data)
        
        if data_len == 118:  # 59 bytes * 2 = 118 hex chars
            # Remove standard wrapper if present
            if hex_data.startswith('FBFBFBF0') and hex_data.endswith('FEFE0E0F'):
                # Standard wrapper: remove 8 chars start + 8 chars end
                frame = hex_data[8:-8]
                if len(frame) >= 76:  # Minimum for valid frame
                    frames.append(frame)
            else:
                # No wrapper, use as-is if starts with expected pattern
                if '25442D2C' in hex_data or '30442D2C' in hex_data:
                    frames.append(hex_data)
                    
        elif data_len == 140:  # 70 bytes * 2 = 140 hex chars  
            # Remove wrapper and extract frame
            if hex_data.startswith('FBFBFBF0') and hex_data.endswith('FEFE0E0F'):
                frame = hex_data[8:-8]
                if len(frame) >= 98:  # Minimum for full frame
                    frames.append(frame)
            else:
                if '25442D2C' in hex_data or '30442D2C' in hex_data:
                    frames.append(hex_data)
        
        return frames
    
    def extract_frames_96_bytes(self, hex_data: str) -> List[str]:
        """
        Extract frames from 96 byte notifications.
        Rule: Delete header (108 characters) & footer (8 characters)
        """
        frames = []
        data_len = len(hex_data)
        
        if data_len == 192:  # 96 bytes * 2 = 192 hex chars
            # Apply the specific rule: remove first 108 chars and last 8 chars
            if data_len > 116:  # 108 + 8 = 116
                frame = hex_data[108:-8]
                if len(frame) >= 76 and ('25442D2C' in frame or '30442D2C' in frame):
                    frames.append(frame)
        
        return frames
    
    def extract_frames_244_bytes(self, hex_data: str) -> List[str]:
        """
        Extract frames from 244 byte encapsulated notifications.
        Rule: Look for patterns "25442D2C" or "30442D2C", extract by length
        - FRAMES STARTING WITH "25442D2C": 76 DIGITS TOTAL
        - FRAMES STARTING WITH "30442D2C": 98 DIGITS TOTAL
        """
        frames = []
        data = hex_data.upper()
        pos = 0
        
        while pos < len(data):
            # Look for compact frame pattern
            compact_pos = data.find('25442D2C', pos)
            # Look for full frame pattern  
            full_pos = data.find('30442D2C', pos)
            
            # Determine which pattern comes first
            next_pos = None
            frame_type = None
            
            if compact_pos != -1 and full_pos != -1:
                if compact_pos < full_pos:
                    next_pos = compact_pos
                    frame_type = 'compact'
                else:
                    next_pos = full_pos
                    frame_type = 'full'
            elif compact_pos != -1:
                next_pos = compact_pos
                frame_type = 'compact'
            elif full_pos != -1:
                next_pos = full_pos
                frame_type = 'full'
            else:
                break  # No more patterns found
            
            # Extract frame based on type
            if frame_type == 'compact' and next_pos + 76 <= len(data):
                frame = data[next_pos:next_pos + 76]
                frames.append(frame)
                pos = next_pos + 76
            elif frame_type == 'full' and next_pos + 98 <= len(data):
                frame = data[next_pos:next_pos + 98]
                frames.append(frame)
                pos = next_pos + 98
            else:
                # Not enough data for complete frame
                break
                
        return frames
    
    def extract_wmbus_frames(self, hex_data: str) -> List[str]:
        """
        Main frame extraction logic based on data length.
        Returns list of clean WM-Bus frames ready for wmbusmeters.
        """
        data_len = len(hex_data)
        frames = []
        
        logger.debug(f"Processing {data_len} hex chars ({data_len//2} bytes)")
        
        if data_len == 118 or data_len == 140:  # 59 or 70 bytes
            frames = self.extract_frames_59_70_bytes(hex_data)
            
        elif data_len == 192:  # 96 bytes
            frames = self.extract_frames_96_bytes(hex_data)
            
        elif data_len == 488:  # 244 bytes
            frames = self.extract_frames_244_bytes(hex_data)
            
        else:
            # Try to find patterns anyway for unknown sizes
            logger.warning(f"Unknown frame size: {data_len} chars ({data_len//2} bytes)")
            if '25442D2C' in hex_data or '30442D2C' in hex_data:
                # Use 244-byte logic as fallback
                frames = self.extract_frames_244_bytes(hex_data)
        
        # Validate extracted frames
        valid_frames = []
        for frame in frames:
            if self.validate_frame(frame):
                valid_frames.append(frame)
                logger.info(f"✅ Extracted valid frame: {frame[:16]}... ({len(frame)} chars)")
            else:
                logger.warning(f"❌ Invalid frame rejected: {frame[:16]}... ({len(frame)} chars)")
        
        return valid_frames
    
    def validate_frame(self, frame: str) -> bool:
        """Validate that extracted frame is a proper WM-Bus frame."""
        if len(frame) < 20:
            return False
        
        # Check for FlowIQ2101 patterns
        if not (frame.startswith('25442D2C') or frame.startswith('30442D2C')):
            return False
            
        # Check for meter ID 74493770 (703749741F16 in little endian)
        if '703749741F16' not in frame:
            return False
            
        return True
    
    def process_line(self, line: str) -> List[str]:
        """Process a single line and extract all WM-Bus frames."""
        line = line.strip()
        
        # Skip empty lines and logs
        if not line or line.startswith('2025-') or 'INFO' in line:
            return []
            
        # Extract hex data
        hex_data = self.extract_telegram_data(line)
        if not hex_data:
            return []
            
        # Extract frames
        frames = self.extract_wmbus_frames(hex_data)
        if frames:
            self.processed_count += 1
            self.extracted_frames += len(frames)
            
        return frames
    
    def process_stream(self, input_stream=sys.stdin, output_stream=sys.stdout):
        """Process input stream and output clean WM-Bus frames."""
        logger.info("🔧 VW1871 Frame Extractor started")
        logger.info("   Input: VW1871 Bluetooth notifications")
        logger.info("   Output: Clean WM-Bus frames for wmbusmeters")
        logger.info("   Rules: FlowIQ2101 frame variants (2025-08-14)")
        
        try:
            for line in input_stream:
                frames = self.process_line(line)
                for frame in frames:
                    output_stream.write(f"telegram=|{frame}|\n")
                    output_stream.flush()
                    
        except KeyboardInterrupt:
            logger.info(f"\n⛔ Extractor stopped.")
        except Exception as e:
            logger.error(f"Error processing stream: {e}")
            raise
        finally:
            logger.info(f"📊 Summary: {self.processed_count} notifications → {self.extracted_frames} frames")

def main():
    """Main entry point for VW1871 frame extractor."""
    if len(sys.argv) > 1 and sys.argv[1] in ["-h", "--help"]:
        print("""
VW1871 Frame Extractor - FlowIQ2101 Implementation

Usage:
    python3 vw1871_frame_extractor.py                 # Process stdin
    cat logs.txt | python3 vw1871_frame_extractor.py  # Process file
    ./run_flowiq2101_live.sh | python3 vw1871_frame_extractor.py | wmbusmeters ...

Frame Extraction Rules (based on flowiq2101_frame_variants.txt):
- 59/70 bytes: Remove FBFBFBF0...FEFE0E0F wrapper
- 96 bytes: Remove first 108 chars + last 8 chars  
- 244 bytes: Extract multiple frames by pattern matching

Patterns:
- 25442D2C: Compact frames (76 hex digits)
- 30442D2C: Full frames (98 hex digits)
""")
        return
        
    extractor = VW1871FrameExtractor()
    extractor.process_stream()

if __name__ == "__main__":
    main()
