#!/usr/bin/env python3
"""
VW1871 Wrapper Parser
====================
Analyzes VW1871 Bluetooth concentrator wrapper format to extract:
- Header byte patterns after start marker FBFBFBF0
- Sequence analysis and frame type detection
- Statistics on wrapper overhead vs payload

Usage:
    python vw1871_wrapper_parser.py <log_file.jsonl>
    python vw1871_wrapper_parser.py --hex "FBFBFBF01101250825084BE3..."

The VW1871 uses this format:
    FBFBFBF0 <header_bytes> <wmbus_payload> FEFE0E0F
    
Where:
- FBFBFBF0: Start delimiter (4 bytes)
- header_bytes: Usually 2-3 bytes with type/sequence info
- wmbus_payload: Actual WM-Bus telegram (often truncated)
- FEFE0E0F: End delimiter (4 bytes)
"""

import argparse
import json
import re
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Optional

class VW1871Parser:
    def __init__(self):
        self.start_marker = bytes.fromhex('FBFBFBF0')
        self.end_marker = bytes.fromhex('FEFE0E0F')
        self.frames = []
        self.header_stats = Counter()
        self.sequence_analysis = defaultdict(list)
        
    def parse_hex_string(self, hex_str: str) -> List[Dict]:
        """Parse a single hex string for VW1871 frames."""
        # Remove whitespace and convert to bytes
        clean_hex = re.sub(r'[^0-9A-Fa-f]', '', hex_str)
        if len(clean_hex) % 2 != 0:
            raise ValueError("Hex string must have even number of characters")
        
        data = bytes.fromhex(clean_hex)
        return self.extract_frames(data)
    
    def extract_frames(self, data: bytes) -> List[Dict]:
        """Extract all VW1871 frames from raw data."""
        frames = []
        pos = 0
        
        while pos < len(data):
            # Look for start marker
            start_pos = data.find(self.start_marker, pos)
            if start_pos == -1:
                break
                
            # Look for end marker after start
            end_pos = data.find(self.end_marker, start_pos + 4)
            if end_pos == -1:
                # No end marker found, take rest of data
                end_pos = len(data)
                incomplete = True
            else:
                incomplete = False
                
            # Extract frame content
            frame_start = start_pos + 4  # Skip start marker
            frame_end = end_pos
            
            if frame_end > frame_start:
                frame_data = data[frame_start:frame_end]
                frame_info = self.analyze_frame(frame_data, incomplete)
                frame_info['raw_hex'] = data[start_pos:end_pos + (4 if not incomplete else 0)].hex().upper()
                frame_info['offset'] = start_pos
                frames.append(frame_info)
                
            pos = end_pos + 4 if not incomplete else len(data)
            
        return frames
    
    def analyze_frame(self, frame_data: bytes, incomplete: bool = False) -> Dict:
        """Analyze a single frame's structure."""
        if len(frame_data) < 2:
            return {
                'length': len(frame_data),
                'header_bytes': frame_data.hex().upper(),
                'header_len': len(frame_data),
                'payload': '',
                'payload_len': 0,
                'incomplete': incomplete,
                'analysis': 'Too short for header analysis'
            }
        
        # Assume first 2-3 bytes are header, rest is payload
        # Heuristic: if byte 0 is 0x11 and byte 1 looks like sequence, take 2 bytes
        # Otherwise, take 3 bytes for header
        if frame_data[0] == 0x11 and len(frame_data) > 2:
            header_len = 2
        elif len(frame_data) > 3:
            header_len = 3
        else:
            header_len = min(2, len(frame_data))
            
        header = frame_data[:header_len]
        payload = frame_data[header_len:]
        
        # Update statistics
        header_hex = header.hex().upper()
        self.header_stats[header_hex] += 1
        
        # Sequence analysis for byte 1 if available
        if len(header) >= 2:
            seq_byte = header[1]
            self.sequence_analysis[header[0]].append(seq_byte)
        
        analysis = self.interpret_header(header)
        
        return {
            'length': len(frame_data),
            'header_bytes': header_hex,
            'header_len': header_len,
            'payload': payload.hex().upper(),
            'payload_len': len(payload),
            'incomplete': incomplete,
            'analysis': analysis
        }
    
    def interpret_header(self, header: bytes) -> str:
        """Attempt to interpret header bytes."""
        if len(header) == 0:
            return "Empty header"
        
        interpretations = []
        
        byte0 = header[0]
        if byte0 == 0x11:
            interpretations.append("Type: Standard frame (0x11)")
        elif byte0 == 0x25:
            interpretations.append("Type: Extended frame (0x25)")
        else:
            interpretations.append(f"Type: Unknown (0x{byte0:02X})")
        
        if len(header) >= 2:
            byte1 = header[1]
            interpretations.append(f"Seq/Ctrl: 0x{byte1:02X} ({byte1})")
            
        if len(header) >= 3:
            byte2 = header[2]
            interpretations.append(f"Extra: 0x{byte2:02X}")
            
        return " | ".join(interpretations)
    
    def parse_jsonl_file(self, filepath: str) -> List[Dict]:
        """Parse VW1871 frames from a JSONL log file."""
        all_frames = []
        
        with open(filepath, 'r') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    record = json.loads(line.strip())
                    if 'raw_hex' in record:
                        hex_data = record['raw_hex']
                        frames = self.parse_hex_string(hex_data)
                        for frame in frames:
                            frame['source_line'] = line_num
                            frame['timestamp'] = record.get('ts', 'unknown')
                        all_frames.extend(frames)
                except (json.JSONDecodeError, ValueError) as e:
                    print(f"Warning: Skipping line {line_num}: {e}")
                    
        return all_frames
    
    def print_analysis(self, frames: List[Dict]):
        """Print comprehensive analysis of extracted frames."""
        if not frames:
            print("No VW1871 frames found.")
            return
            
        print(f"\n=== VW1871 Wrapper Analysis ===")
        print(f"Total frames found: {len(frames)}")
        print(f"Incomplete frames: {sum(1 for f in frames if f.get('incomplete', False))}")
        
        # Header statistics
        print(f"\n--- Header Patterns ---")
        for header, count in self.header_stats.most_common():
            print(f"  {header}: {count} occurrences")
        
        # Sequence analysis
        print(f"\n--- Sequence Analysis ---")
        for type_byte, sequences in self.sequence_analysis.items():
            if len(sequences) > 1:
                seq_range = f"{min(sequences)} to {max(sequences)}"
                seq_count = len(set(sequences))
                print(f"  Type 0x{type_byte:02X}: {seq_count} unique values ({seq_range})")
        
        # Frame length distribution
        lengths = [f['length'] for f in frames]
        print(f"\n--- Frame Length Distribution ---")
        length_counter = Counter(lengths)
        for length, count in sorted(length_counter.items()):
            print(f"  {length} bytes: {count} frames")
        
        # Sample frames
        print(f"\n--- Sample Frames ---")
        for i, frame in enumerate(frames[:5]):
            print(f"Frame {i+1}:")
            print(f"  Raw: {frame['raw_hex'][:60]}{'...' if len(frame['raw_hex']) > 60 else ''}")
            print(f"  Header: {frame['header_bytes']} ({frame['analysis']})")
            print(f"  Payload: {frame['payload_len']} bytes")
            if 'timestamp' in frame:
                print(f"  Time: {frame['timestamp']}")
            print()

def decode_fragments(fragment1: str, fragment2: str):
    """Decode the specific fragments asked about."""
    print("=== Fragment Decoding ===")
    
    print(f"\nFragment 1: {fragment1}")
    if fragment1.upper().startswith('FBFBFBF0'):
        start_marker = fragment1[:8]
        header_part = fragment1[8:]
        print(f"  Start marker: {start_marker} (VW1871 frame start)")
        if header_part:
            print(f"  Header bytes: {header_part}")
            header_bytes = bytes.fromhex(header_part)
            if len(header_bytes) >= 1:
                print(f"    Byte 0: 0x{header_bytes[0]:02X} ({'Standard frame' if header_bytes[0] == 0x11 else 'Other type'})")
            if len(header_bytes) >= 2:
                print(f"    Byte 1: 0x{header_bytes[1]:02X} (sequence/control)")
    
    print(f"\nFragment 2: {fragment2}")
    if fragment2.upper().endswith('FEFE0E0F'):
        data_part = fragment2[:-8]
        end_marker = fragment2[-8:]
        print(f"  Data byte: {data_part} (last payload byte)")
        print(f"  End marker: {end_marker} (VW1871 frame end)")
    else:
        print(f"  This appears to be: {fragment2}")
        print(f"  Last byte: {fragment2[-2:]} (0x{int(fragment2[-2:], 16):02X})")
        print(f"  End marker: {fragment2[-8:]} (if present)")

def main():
    parser = argparse.ArgumentParser(description='Parse VW1871 wrapper format')
    parser.add_argument('input', nargs='?', help='JSONL log file to parse')
    parser.add_argument('--hex', help='Parse single hex string')
    parser.add_argument('--decode', nargs=2, metavar=('FRAG1', 'FRAG2'), 
                       help='Decode two specific fragments')
    
    args = parser.parse_args()
    
    # Handle specific fragment decoding first
    if args.decode:
        decode_fragments(args.decode[0], args.decode[1])
        return
    
    vw_parser = VW1871Parser()
    
    if args.hex:
        try:
            frames = vw_parser.parse_hex_string(args.hex)
            vw_parser.print_analysis(frames)
        except ValueError as e:
            print(f"Error parsing hex: {e}")
    elif args.input:
        try:
            frames = vw_parser.parse_jsonl_file(args.input)
            vw_parser.print_analysis(frames)
        except FileNotFoundError:
            print(f"Error: File {args.input} not found")
        except Exception as e:
            print(f"Error parsing file: {e}")
    else:
        # Default: decode the specific fragments mentioned
        decode_fragments('FBFBFBF01101', '9FEFE0E0F')

if __name__ == '__main__':
    main()
