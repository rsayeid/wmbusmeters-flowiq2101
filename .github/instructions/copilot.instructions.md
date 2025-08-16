---
applyTo: '**'
---
# 🚨 HIGH PRIORITY COPILOT INSTRUCTIONS 🚨

## ⚠️ CRITICAL PROJECT GUIDELINES - MUST FOLLOW

These instructions have **HIGH PRIORITY** and must be followed for all FlowIQ2101 wmbusmeters project work.

---

## 📋 1. FOLLOW README.md PROCESS

### ✅ **ALWAYS Reference README.md First**
- **Primary Guide**: `/README.md` contains the main wmbusmeters workflow
- **Secondary Guide**: `/README_FLOWIQ2101.md` for FlowIQ2101-specific integration
- **Process Flow**: Follow the exact steps outlined in documentation
- **Commands**: Use the recommended command formats from README.md

### 📖 **Key README.md Sections to Follow**
```bash
# Example from README.md - ALWAYS use these patterns:
wmbusmeters --logtelegrams auto:t1  # (macOS: use specific device)
wmbusmeters --analyze simulation_file.txt
wmbusmeters --format=json [device] [meter_name] [driver] [meter_id] [key]
```

---

## 🔍 2. CHECK EXISTING SCRIPTS BEFORE CREATING NEW

### ⚠️ **MANDATORY SCRIPT AUDIT**
Before creating ANY new script, you MUST:

1. **Search for existing scripts**:
   ```bash
   ls -la *.sh *.py *.java
   find . -name "*script_topic*" -type f
   grep -r "similar_function" *.sh *.py
   ```

2. **Check these common script types**:
   - `*_bridge.sh` / `*_bridge.py` - Bluetooth/serial bridge scripts
   - `*_capture.py` / `*_capture.sh` - Data capture scripts  
   - `*_analysis.sh` / `*_analysis.py` - Analysis and pattern scripts
   - `*_test.sh` / `*_test.py` - Testing and validation scripts
   - `*_extractor.py` - Frame extraction and preprocessing scripts
   - `simulation_*.txt` - Simulation data files
   - `test_*.conf` - Configuration files

3. **Prioritize modification over creation**:
   - ✅ **MODIFY** existing script if similar functionality exists
   - ✅ **UPGRADE** existing script with new features
   - ✅ **EXTEND** existing script rather than duplicate
   - ❌ **AVOID** creating duplicate functionality

### 📝 **Example Existing Scripts to Check**
- `bluetooth_to_serial_bridge.py` - Main bridge service
- `bluetooth_wmbus_capture.py` - Bluetooth capture
- `flowiq_pattern_analysis.sh` - Pattern analysis
- `validate_flowiq_pattern.sh` - Pattern validation
- `vw1871_bridge.sh` - Native bridge alternative
- `vw1871_frame_extractor.py` - **PRIMARY** frame extraction tool
- `test_flowiq2101_integration.sh` - Integration testing

---

## 🛑 3. CLEANUP ALL SERVICES AFTER USE

### ⚠️ **MANDATORY SERVICE CLEANUP**
After ANY operation involving bluetooth, wmbusmeters, or daemons:

#### 🧹 **Standard Cleanup Commands**
```bash
# Stop all bluetooth processes
pkill -f "bluetooth_to_serial_bridge"
pkill -f "bluetooth_wmbus_capture" 
pkill -f "python.*bluetooth"

# Stop all wmbusmeters processes
pkill -f "wmbusmeters"
killall -9 wmbusmeters
killall -9 wmbusmetersd

# Verify cleanup
ps aux | grep -E "(bluetooth|wmbus)" | grep -v grep | grep -v bluetoothd | grep -v bluetoothuserd
```

#### 🔧 **Service-Specific Cleanup**
- **Virtual Serial Ports**: Automatically cleaned when bridge stops
- **Python Processes**: Use `pkill -f "python.*bluetooth"`
- **Background Jobs**: Use `jobs` and `kill %1` etc.
- **Daemon Processes**: Check for `wmbusmetersd` specifically

#### ✅ **Cleanup Verification**
Always verify cleanup with:
```bash
ps aux | grep -E "(bluetooth.*capture|wmbus|python.*bridge)" | grep -v grep
# Should return empty (exit code 1) when clean
```

---

## 🎯 PROJECT-SPECIFIC PRIORITIES

### 🔐 **FlowIQ2101 Development Setup**
- **Test Meter ID**: 74493770 (sample for development/testing only)
- **Manufacturer**: Kamstrup (2D2C pattern in frames)
- **Test Key**: 44E9112D06BD762EC2BFECE57E487C9B (for development meter only)
- **Bluetooth Device**: VW1871-250111 concentrator (test setup)
- **Frame Extraction**: `vw1871_frame_extractor.py` (PRIMARY tool)
- **Production Scope**: System designed to read thousands of FlowIQ2101 meters

### 📊 **Pattern Analysis Focus**
- **Transmission Pattern**: 7 compact + 1 full frame (FlowIQ2101 standard)
- **Compact Frames**: 37 bytes (25442D2C pattern, 76 hex digits)
- **Full Frames**: 77+ bytes (30442D2C pattern, 98 hex digits)
- **Access Number Cycle**: Modulo 8 pattern (universal FlowIQ2101 behavior)
- **Frame Extraction Rules**: Based on notification byte length (59/70/96/244 bytes)
- **Scalability**: Framework supports multiple meters with different IDs/keys

### 🔧 **Technical Constraints**
- **macOS**: Cannot use `auto:t1` - must specify device
- **Virtual Environment**: Always use `.venv` for Python scripts
- **C1 Mode**: Use for raw hex telegram capture
- **T1 Mode**: Use for processed telegram data
- **Frame Processing**: VW1871 → vw1871_frame_extractor.py → wmbusmeters
- **Production Ready**: Framework designed for thousands of FlowIQ2101 meters

---

## ⚡ WORKFLOW ENFORCEMENT

### ✅ **Before Starting Any Task**
1. Read relevant README.md sections
2. Search for existing similar scripts/tools
3. Check current running processes
4. Activate virtual environment if using Python

### ✅ **During Task Execution**
1. Follow README.md command patterns
2. Modify existing scripts rather than create new ones
3. Use established naming conventions
4. Document any new functionality

### ✅ **After Task Completion**
1. Stop ALL bluetooth/wmbus services
2. Verify cleanup with process check
3. Update relevant documentation
4. Commit changes with descriptive messages

---

## 🚨 CRITICAL REMINDERS

- **README.md is LAW** - Always follow its processes
- **REUSE > CREATE** - Modify existing scripts first
- **CLEANUP IS MANDATORY** - Never leave services running
- **VIRTUAL ENV** - Always use `.venv` for Python
- **macOS SPECIFIC** - No auto-detection, specify devices
- **PATTERN FOCUS** - FlowIQ2101 7+1 frame transmission cycle

---

**These instructions have HIGH PRIORITY and override general coding practices when working on this FlowIQ2101 integration project.**