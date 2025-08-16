# FlowIQ2101 Project Extraction Summary
## Essential Information for Android App Development

**Date**: August 16, 2025  
**Project**: FlowIQ2101 Meter Management System  
**Migration**: wmbusmeters → AWS Amplify Gen 2 + Android App  

---

## 🎯 **Project Overview**

This document contains EVERYTHING needed to implement a fresh Android app with AWS Amplify Gen 2 for production-scale FlowIQ2101 meter reading across thousands of meters in multiple societies.

---

## 🔧 **Key Management & Parsing Utilities**

### **KEM File Processing (from utils/ folder)**

```python
# utils/kem-import.py - Primary KEM file processor
Key_Extraction_Process:
  input: "Encrypted KEM file from Kamstrup"
  password: "Customer ID or custom password"
  algorithm: "AES-128-CBC with key as IV"
  output: "Meter configurations with encryption keys"
  
Supported_Formats:
  - Single KEM files (.kem)
  - ZIP archives containing KEM files (.kem2)
  - MetersInOrder XML format
  - Devices XML format

Usage_Example:
  command: "python utils/kem-import.py [kem_file] [password]"
  result: "Individual meter config files with keys"
  
FlowIQ2101_Detection:
  meter_name: "FLOWIQ 21XX"
  wmbusmeters_driver: "flowiq2101"
  auto_configuration: "Generates ready-to-use meter configs"
```

### **Shell-based KEM Extraction (utils/kem-extract.sh)**

```bash
# Quick key extraction utility
Usage: "./utils/kem-extract.sh [password] [kem_file]"
Output:
  - meter_id: "Extracted meter serial number"
  - meter_key: "32-character hex encryption key"
  
Key_Formatting:
  - Automatic password padding to 16 bytes
  - Base64 decryption handling
  - Multiple KEM format support
```

### **XML Encryption Utility (utils/XMLExtract.java)**

```java
// W3C XML Encryption standard processor
Encryption_Details:
  cipher: "AES-128-CBC"
  standard: "W3C XML Encryption Recommendation"
  usage: "Direct XML-encrypted content decryption"
  
Compilation: "javac XMLExtract.java"
Usage: "java XMLExtract [password] [encrypted_xml]"
```

---

---

## 📊 **Core Data Models**

### **FlowIQ2101 Meter Specifications**

```yaml
Sample_Meter_Details: # This is our development/testing meter
  manufacturer: "Kamstrup"
  manufacturer_code: "2D2C" 
  model: "FlowIQ2101"
  type: "Water Meter"
  sample_meter_id: "74493770" # Development/testing meter only
  sample_encryption_key: "44E9112D06BD762EC2BFECE57E487C9B" # Test key only
  driver: "flowiq2101"
  protocol: "wM-Bus with AES-CTR encryption"
  link_mode: "C1"

Production_Scope:
  target_deployment: "Thousands of FlowIQ2101 meters across multiple societies"
  unique_properties: "Each meter has unique ID and encryption key"
  key_management: "Keys extracted from KEM files using utils/kem-import.py"
  scalability: "System designed for large-scale deployments"

Physical Properties:
  battery_life: "15+ years"
  temperature_range: "-40°C to +70°C"
  flow_measurement: "Up to 2.5 m³/h"
  accuracy_class: "Class 2"
```

### **Transmission Pattern (7+1 Cycle)**

```yaml
Frame Cycle Pattern:
  pattern: "7 compact + 1 full frame"
  compact_frames:
    count: 7
    size: "37 bytes"
    hex_length: "76 characters"
    access_numbers: [0, 1, 2, 3, 4, 5, 6]
    data_content: "Essential readings (volume, status)"
    
  full_frames:
    count: 1
    size: "77+ bytes"
    hex_length: "154+ characters"
    access_number: 7
    data_content: "Complete diagnostics, flow rates, history"
    vw1871_limitation: "Truncated to ~48 bytes due to buffer limit"

Energy Efficiency:
  compact_transmission: "87.5% of time"
  full_transmission: "12.5% of time"
  power_optimization: "Extends battery life significantly"
```

### **Frame Structure Patterns**

```yaml
Compact Frame Pattern (25442D2C):
  length_byte: "25" # 37 bytes
  control_field: "44"
  manufacturer: "2D2C" # Kamstrup
  meter_id: "703749741F16" # 74493770 little-endian
  version: "16" # Device version
  access_number: "Variable (0-6)"
  data_payload: "Volume, status, essential readings"

Full Frame Pattern (30442D2C):
  length_byte: "30" # 48+ bytes (truncated by VW1871)
  control_field: "44"
  manufacturer: "2D2C" # Kamstrup  
  meter_id: "703749741F16" # 74493770 little-endian
  version: "16" # Device version
  access_number: "7" # Full frame position
  data_payload: "Complete diagnostics, flow history, temperatures"
```

### **VW1871 Frame Extraction Rules**

```typescript
// Based on vw1871_frame_extractor.py logic
interface FrameExtractionRules {
  notification_size_59_bytes: {
    hex_length: 118,
    rule: "Remove FBFBFBF0 header (8 chars) + FEFE0E0F footer (8 chars)",
    result: "Clean 37-byte WM-Bus frame"
  },
  
  notification_size_70_bytes: {
    hex_length: 140,
    rule: "Remove FBFBFBF0 header (8 chars) + FEFE0E0F footer (8 chars)", 
    result: "Clean WM-Bus frame with additional data"
  },
  
  notification_size_96_bytes: {
    hex_length: 192,
    rule: "Remove header (108 chars) + footer (8 chars)",
    result: "Intermediate frame size"
  },
  
  notification_size_244_bytes: {
    hex_length: 488,
    rule: "Extract frames by pattern: 25442D2C (76 chars) or 30442D2C (98 chars)",
    result: "Multiple frames in single notification"
  }
}
```

---

## 🔧 **Technical Implementation Details**

### **Bluetooth Device Configuration**

```yaml
VW1871_Device:
  model: "VW1871-250111"
  uuid: "F0F41E39-111C-1E4B-018D-4363539FF186"
  protocol: "Bluetooth Low Energy (BLE)"
  function: "wM-Bus concentrator"
  capture_limit: "~48 bytes maximum"
  notification_sizes: [59, 70, 96, 244]
  frame_wrapper: "FBFBFBF0...FEFE0E0F"
```

### **Encryption Configuration**

```yaml
Encryption_Setup:
  algorithm: "AES-CTR"
  key_source: "KEM file extraction"
  kem_password: "Pass1234"
  key_format: "32 hex characters"
  test_key: "44E9112D06BD762EC2BFECE57E487C9B"
  validation: "Decrypts to 2F2F check bytes"
```

### **Data Field Mappings**

```typescript
interface FlowIQ2101Data {
  // Essential readings (compact frames)
  total_m3: number;           // Total water consumption
  status: string;             // "OK" | "DRY" | "REVERSE" | "LEAK" | "BURST"
  access_number: number;      // Frame sequence number (0-7)
  meter_datetime: string;     // Meter timestamp
  
  // Extended readings (full frames only)
  target_m3?: number;         // Target consumption
  max_flow_m3h?: number;      // Maximum flow rate
  flow_temperature_c?: number; // Water temperature
  external_temperature_c?: number; // Ambient temperature
  min_flow_temperature_c?: number; // Minimum water temp
  max_flow_temperature_c?: number; // Maximum water temp
  battery_level?: number;     // Battery percentage
  
  // System fields
  meter_id: string;           // "74493770"
  manufacturer: string;       // "KAM" (Kamstrup)
  rssi?: number;             // Signal strength
  timestamp: string;          // Capture timestamp
}
```

---

## 📱 **Android App Data Models**

### **Core Entities for GraphQL Schema**

```typescript
// Society entity
type Society = {
  id: ID!
  name: String!
  address: String
  structure: AWSJSON  // { towers: [{ name: string, flats: string[] }] }
  meters: [Meter!]! @hasMany
  scanSessions: [ScanSession!]! @hasMany
  totalMeters: Int
  activeMeters: Int
  createdAt: AWSDateTime!
  updatedAt: AWSDateTime!
}

// Meter entity  
type Meter = {
  id: ID!
  societyId: ID! @index
  serialNumber: String!      // "74493770"
  manufacturer: String!      // "Kamstrup"
  model: String!            // "FlowIQ2101"
  flatNumber: String!       // "A-101"
  towerName: String!        // "Tower A"
  encryptionKey: String!    // "44E9112D06BD762EC2BFECE57E487C9B"
  location: AWSJSON         // { lat: number, lng: number }
  status: MeterStatus!      // ACTIVE | INACTIVE | MAINTENANCE
  lastReading: AWSDateTime
  readings: [Reading!]! @hasMany
  createdAt: AWSDateTime!
  updatedAt: AWSDateTime!
}

// Scanning session
type ScanSession = {
  id: ID!
  societyId: ID! @index
  userId: ID! @index
  mode: ScanMode!           // FLAT | TOWER | SOCIETY | FREE_ROAM
  targetMeters: [String!]!  // Array of meter IDs
  progress: AWSJSON!        // { completed: number, total: number, percentage: number }
  status: SessionStatus!    // ACTIVE | COMPLETED | FAILED | PAUSED
  startedAt: AWSDateTime!
  completedAt: AWSDateTime
  readings: [Reading!]! @hasMany
  exports: [Export!]! @hasMany
  createdAt: AWSDateTime!
  updatedAt: AWSDateTime!
}

// Individual reading
type Reading = {
  id: ID!
  meterId: ID! @index
  sessionId: ID! @index
  consumption: Float!       // Water consumption in m³
  timestamp: AWSDateTime!   // Reading timestamp
  rawTelegram: String!      // Original hex telegram
  decryptedData: AWSJSON    // Parsed meter data
  quality: ReadingQuality!  // GOOD | FAIR | POOR
  gpsLocation: AWSJSON      // { lat: number, lng: number }
  accessNumber: Int         // Frame sequence (0-7)
  frameType: FrameType!     // COMPACT | FULL
  meterData: AWSJSON        // FlowIQ2101Data structure
  createdAt: AWSDateTime!
}

// Export functionality
type Export = {
  id: ID!
  sessionId: ID! @index
  format: ExportFormat!     // EXCEL | JSON | CSV
  fileName: String!
  filePath: String          // Local device path
  s3Location: String        // Cloud storage location
  size: Int                 // File size in bytes
  status: ExportStatus!     // GENERATING | COMPLETED | FAILED
  downloadUrl: String       // Presigned URL
  expiresAt: AWSDateTime    // URL expiration
  createdAt: AWSDateTime!
}

// Enums
enum MeterStatus { ACTIVE INACTIVE MAINTENANCE }
enum ScanMode { FLAT TOWER SOCIETY FREE_ROAM }
enum SessionStatus { ACTIVE COMPLETED FAILED PAUSED }
enum ReadingQuality { GOOD FAIR POOR }
enum FrameType { COMPACT FULL }
enum ExportFormat { EXCEL JSON CSV }
enum ExportStatus { GENERATING COMPLETED FAILED }
```

---

## 🔍 **Frame Processing Logic**

### **VW1871 Frame Extractor (TypeScript Port)**

```typescript
class VW1871FrameExtractor {
  extractWmbusFrames(hexData: string): string[] {
    const dataLength = hexData.length;
    const frames: string[] = [];
    
    switch (dataLength) {
      case 118: // 59 bytes
      case 140: // 70 bytes
        return this.extractFrames59_70Bytes(hexData);
        
      case 192: // 96 bytes
        return this.extractFrames96Bytes(hexData);
        
      case 488: // 244 bytes
        return this.extractFrames244Bytes(hexData);
        
      default:
        // Fallback: try 244-byte logic
        if (hexData.includes('25442D2C') || hexData.includes('30442D2C')) {
          return this.extractFrames244Bytes(hexData);
        }
        return [];
    }
  }
  
  private extractFrames59_70Bytes(hexData: string): string[] {
    // Remove standard wrapper FBFBFBF0...FEFE0E0F
    if (hexData.startsWith('FBFBFBF0') && hexData.endsWith('FEFE0E0F')) {
      const frame = hexData.substring(8, hexData.length - 8);
      return this.validateFrame(frame) ? [frame] : [];
    }
    
    // Check for meter patterns
    if (hexData.includes('25442D2C') || hexData.includes('30442D2C')) {
      return [hexData];
    }
    
    return [];
  }
  
  private extractFrames244Bytes(hexData: string): string[] {
    const frames: string[] = [];
    let position = 0;
    
    while (position < hexData.length) {
      const compactPos = hexData.indexOf('25442D2C', position);
      const fullPos = hexData.indexOf('30442D2C', position);
      
      let nextPos = -1;
      let frameLength = 0;
      
      if (compactPos !== -1 && (fullPos === -1 || compactPos < fullPos)) {
        nextPos = compactPos;
        frameLength = 76; // 25442D2C frames are 76 hex chars
      } else if (fullPos !== -1) {
        nextPos = fullPos;
        frameLength = 98; // 30442D2C frames are 98 hex chars
      }
      
      if (nextPos === -1) break;
      
      const frame = hexData.substring(nextPos, nextPos + frameLength);
      if (this.validateFrame(frame)) {
        frames.push(frame);
      }
      
      position = nextPos + frameLength;
    }
    
    return frames;
  }
  
  private validateFrame(frame: string): boolean {
    return frame.length >= 20 &&
           (frame.startsWith('25442D2C') || frame.startsWith('30442D2C')) &&
           frame.includes('703749741F16'); // Meter ID validation
  }
}
```

---

## 🌐 **AWS Integration Architecture**

### **Lambda Function for Telegram Processing**

```typescript
// Lambda function to process telegrams
import { VW1871FrameExtractor } from './frameExtractor';
import { TelegramDecryptor } from './telegramDecryptor';

export const processTelegram = async (event: any) => {
  const { hexData, meterId, encryptionKey } = event;
  
  // Extract clean frames
  const extractor = new VW1871FrameExtractor();
  const frames = extractor.extractWmbusFrames(hexData);
  
  // Decrypt and parse each frame
  const decryptor = new TelegramDecryptor();
  const readings = [];
  
  for (const frame of frames) {
    try {
      const decrypted = await decryptor.decrypt(frame, encryptionKey);
      const parsed = await decryptor.parseFlowIQ2101Data(decrypted);
      readings.push({
        meterId,
        rawTelegram: frame,
        decryptedData: parsed,
        timestamp: new Date().toISOString(),
        frameType: frame.startsWith('25442D2C') ? 'COMPACT' : 'FULL'
      });
    } catch (error) {
      console.error('Failed to process frame:', frame, error);
    }
  }
  
  return { success: true, readings };
};
```

---

### **Sample Data Examples (From Real BLE Session)**

### **244-Byte Notification (Multiple Compact Frames)**

```yaml
Raw_Notification: "FBFBFBF01101250880E1916261B10125442D2C703749741F168D2062E1EA0221E91B78118567A43FA97A01FC5F1BBCFD0F8563A8E09736FEFE0E0FFBFBFBF01101250890E1916261B10125442D2C703749741F168D2063E2EA02218AA966CC3EFA007CF1F4E3D80E4D73539D4B0FF4F6B44BFEFE0E0FFBFBFBF011012508A0E1916261B10125442D2C703749741F168D2064E3EA022102163F1B52182E6F1ED471EE92E80F91324C1ECC8FD1CCFEFE0E0FFBFBFBF011012508AFE1916261B10130442D2C703749741F168D2065F0EA02210929A57EDFA1691F38572570266AB98845F2051E3298654DDEB2B260DC0DAD22E3EAFE"

Extracted_Frames:
  - "25442D2C703749741F168D2062E1EA0221E91B78118567A43FA97A01FC5F1BBCFD0F8563A8E09736"
  - "25442D2C703749741F168D2063E2EA02218AA966CC3EFA007CF1F4E3D80E4D73539D4B0FF4F6B44B"
  - "25442D2C703749741F168D2064E3EA022102163F1B52182E6F1ED471EE92E80F91324C1ECC8FD1CC"
  - "30442D2C703749741F168D2065F0EA02210929A57EDFA1691F38572570266AB98845F2051E3298654DDEB2B260DC0DAD22E3EAFE"

Frame_Analysis:
  compact_frames_count: 3
  full_frames_count: 1
  pattern: "25442D2C (compact) and 30442D2C (full)"
  meter_id: "703749741F16" # 74493770 little-endian
  manufacturer: "2D2C" # Kamstrup
```

### **59-Byte Notification (Single Compact Frame)**

```yaml
Raw_Notification: "FBFBFBF01101250876E8916261AC0125442D2C703749741F168D20D3C0EC0221C11BF53E4E71D5C9CB5344931B03AB0A9715D9FE3343BDFEFE0E0F"

Frame_Extraction:
  wrapper_header: "FBFBFBF0"
  wrapper_footer: "FEFE0E0F"
  clean_frame: "25442D2C703749741F168D20D3C0EC0221C11BF53E4E71D5C9CB5344931B03AB0A9715D9FE3343BD"

Frame_Analysis:
  length: "25" # 37 bytes
  control: "44"
  manufacturer: "2D2C" # Kamstrup
  meter_id: "703749741F16" # 74493770
  version: "16"
  access_number: "D3" # Access number for sequence tracking
  frame_type: "COMPACT"
```

### **70-Byte Notification (Single Full Frame)**

```yaml
Raw_Notification: "FBFBFBF01101250896E8916261AB0130442D2C703749741F168D20D5C2EC022132E4B1311357827575401EE9251F4F914B0DBA976E89D01F8DBF5134B241F29FF01CFEFE0E0F"

Frame_Extraction:
  wrapper_header: "FBFBFBF0"
  wrapper_footer: "FEFE0E0F"
  clean_frame: "30442D2C703749741F168D20D5C2EC022132E4B1311357827575401EE9251F4F914B0DBA976E89D01F8DBF5134B241F29FF01C"

Frame_Analysis:
  length: "30" # 48 bytes (truncated from 77+)
  control: "44"
  manufacturer: "2D2C" # Kamstrup
  meter_id: "703749741F16" # 74493770
  version: "16"
  access_number: "D5" # Access number for sequence tracking
  frame_type: "FULL"
  note: "Truncated by VW1871 buffer limitation"
```

### **96-Byte Notification (Intermediate Size)**

```yaml
Raw_Notification: "3749741F168D208262EB02211169741BB3981FE20A27E785AE6262FFCC1809D1F1E950FEFE0E0FFBFBFBF01101250883E3916261AA0125442D2C703749741F168D208363EB0221442B9F27817C58F45A0E3A1EDE7899070BB2C45DEBCCB8FEFE"

Frame_Analysis:
  notification_size: 96
  extraction_rule: "Remove header (108 chars) + footer (8 chars)"
  result: "Contains partial frame data, intermediate processing needed"
  frame_type: "INTERMEDIATE"
```

---

## 🚀 **Next Steps for Android Development**

### **Immediate Actions**

1. **Create AWS Amplify Gen 2 project** with the defined GraphQL schema
2. **Setup Android project** with Jetpack Compose and required dependencies
3. **Implement VW1871FrameExtractor** in TypeScript/Lambda
4. **Create Bluetooth integration** for VW1811 device communication
5. **Develop scanning interfaces** for the four modes (Flat, Tower, Society, Free-roam)

### **Key Integration Points**

```typescript
// Android → AWS integration flow
1. Bluetooth capture → VW1811 device
2. Frame extraction → TypeScript Lambda function  
3. Telegram decryption → Cloud processing
4. Data storage → DynamoDB via GraphQL
5. Real-time updates → AppSync subscriptions
6. Export generation → S3 + Excel processing
```

This extraction summary provides all essential information needed to implement the production-scale Android app while preserving the technical knowledge and business logic from the original wmbusmeters integration project.
