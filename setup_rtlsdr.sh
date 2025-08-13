#!/bin/bash

# RTL-SDR Setup and Testing Script for wmbusmeters
# Complete setup guide for RTL-SDR wM-Bus reception

echo "=== RTL-SDR Setup and Testing for wmbusmeters ==="
echo

# Function to check RTL-SDR device
check_rtl_device() {
    echo "=== Checking for RTL-SDR Device ==="
    
    # Test if RTL-SDR device is connected
    if rtl_test -t 2>&1 | grep -q "Found.*device"; then
        echo "✓ RTL-SDR device detected!"
        rtl_test -t 2>&1 | head -5
        return 0
    else
        echo "✗ No RTL-SDR device found"
        echo
        echo "📋 RTL-SDR Device Requirements:"
        echo "   • RTL2832U-based USB dongle"
        echo "   • Common models: RTL-SDR v3, NooElec NESDR"
        echo "   • Frequency range: 500kHz - 1.7GHz"
        echo "   • Cost: $20-40 USD"
        echo
        echo "🛒 Where to buy:"
        echo "   • Amazon: 'RTL-SDR v3' or 'NooElec NESDR'"
        echo "   • AliExpress: 'RTL2832U R820T2'"
        echo "   • Local electronics stores"
        echo
        return 1
    fi
}

# Function to test RTL-SDR software
test_rtl_software() {
    echo "=== Testing RTL-SDR Software ==="
    
    # Check rtl-sdr tools
    if command -v rtl_test >/dev/null 2>&1; then
        echo "✓ rtl-sdr tools installed"
    else
        echo "✗ rtl-sdr tools not found"
        echo "Installing via Homebrew..."
        brew install rtl-sdr
    fi
    
    # Check rtl_wmbus
    if [ -f "./build/rtl_wmbus" ]; then
        echo "✓ rtl_wmbus compiled"
        ls -la ./build/rtl_wmbus
    else
        echo "✗ rtl_wmbus not found"
        echo "Building rtl_wmbus..."
        
        # Download and build rtl_wmbus
        cd /tmp
        if [ ! -d "rtl-wmbus" ]; then
            git clone https://github.com/xaelsouth/rtl-wmbus.git
        fi
        cd rtl-wmbus
        make clean && make
        
        # Copy to wmbusmeters
        cp rtl_wmbus /Volumes/dev/space/wmblatest/wmbusmeters/build/
        cd /Volumes/dev/space/wmblatest/wmbusmeters
        
        if [ -f "./build/rtl_wmbus" ]; then
            echo "✓ rtl_wmbus built successfully"
        else
            echo "✗ Failed to build rtl_wmbus"
            return 1
        fi
    fi
    
    return 0
}

# Function to test wM-Bus reception
test_wmbus_reception() {
    echo "=== Testing wM-Bus Reception ==="
    
    if ! check_rtl_device; then
        echo "⚠️  Cannot test reception without RTL-SDR device"
        return 1
    fi
    
    echo "Testing different wM-Bus modes..."
    
    # Test Mode C1 (868.95 MHz)
    echo "--- Testing Mode C1 (868.95 MHz) ---"
    echo "Command: ./build/wmbusmeters --debug --verbose --exitafter=30 rtlwmbus"
    timeout 30s ./build/wmbusmeters --debug --verbose --exitafter=30 rtlwmbus 2>&1 | head -20
    
    echo
    
    # Test Mode T1 (868.3 MHz)
    echo "--- Testing Mode T1 (868.3 MHz) ---"
    echo "Command: ./build/wmbusmeters --debug --verbose --exitafter=30 rtlwmbus:t1"
    timeout 30s ./build/wmbusmeters --debug --verbose --exitafter=30 rtlwmbus:t1 2>&1 | head -20
    
    echo
    
    # Test Mode S1 (868.3 MHz)
    echo "--- Testing Mode S1 (868.3 MHz) ---"
    echo "Command: ./build/wmbusmeters --debug --verbose --exitafter=30 rtlwmbus:s1"
    timeout 30s ./build/wmbusmeters --debug --verbose --exitafter=30 rtlwmbus:s1 2>&1 | head -20
}

# Function to show frequency scanning
test_frequency_scan() {
    echo "=== Frequency Scanning ==="
    
    if ! check_rtl_device; then
        echo "⚠️  Cannot scan without RTL-SDR device"
        return 1
    fi
    
    echo "Scanning wM-Bus frequencies for signals..."
    
    # Scan 868 MHz band
    frequencies=(
        "868300000"  # T1/S1 mode
        "868950000"  # C1 mode
        "869525000"  # Alternative frequency
    )
    
    for freq in "${frequencies[@]}"; do
        echo "Scanning ${freq} Hz..."
        timeout 10s rtl_power -f "${freq}" -i 10 2>/dev/null | tail -5 || echo "Scan failed"
    done
}

# Function to create RTL-SDR configuration
create_rtl_config() {
    echo "=== Creating RTL-SDR Configuration ==="
    
    # Create config directory
    mkdir -p "$HOME/.config/wmbusmeters"
    
    # Create RTL-SDR specific config
    cat > "$HOME/.config/wmbusmeters/rtlsdr.conf" << 'EOF'
# RTL-SDR Configuration for wmbusmeters
# Optimized settings for wM-Bus reception

# Device settings
device=rtlwmbus
frequency=868950000  # C1 mode frequency
gain=automatic
sample_rate=1600000

# Protocol settings
format=json
meterfiles=/tmp/wmbusmeters/meter_readings
meterfilesaction=append
meterfilesnaming=name-id
meterfilestimestamp=day

# Logging
logtelegrams=true
debug=true
verbose=true
EOF

    echo "✓ Created RTL-SDR config: $HOME/.config/wmbusmeters/rtlsdr.conf"
    
    # Create startup script
    cat > "$HOME/.config/wmbusmeters/start_rtlsdr.sh" << 'EOF'
#!/bin/bash
# RTL-SDR wM-Bus Reception Startup Script

cd /Volumes/dev/space/wmblatest/wmbusmeters

echo "Starting RTL-SDR wM-Bus reception..."
echo "Press Ctrl+C to stop"

# Create output directory
mkdir -p /tmp/wmbusmeters

# Start with all modes
./build/wmbusmeters --config=/Users/$USER/.config/wmbusmeters/rtlsdr.conf rtlwmbus:c1,t1,s1
EOF

    chmod +x "$HOME/.config/wmbusmeters/start_rtlsdr.sh"
    echo "✓ Created startup script: $HOME/.config/wmbusmeters/start_rtlsdr.sh"
}

# Main execution
main() {
    echo "Starting RTL-SDR setup for wmbusmeters..."
    echo
    
    check_rtl_device
    device_available=$?
    
    test_rtl_software
    software_ok=$?
    
    if [ $software_ok -eq 0 ]; then
        echo "✓ Software setup complete"
    else
        echo "✗ Software setup failed"
        exit 1
    fi
    
    create_rtl_config
    
    if [ $device_available -eq 0 ]; then
        echo
        echo "🎉 RTL-SDR setup complete and device detected!"
        echo
        echo "Next steps:"
        echo "1. Run: $HOME/.config/wmbusmeters/start_rtlsdr.sh"
        echo "2. Or manually: ./build/wmbusmeters rtlwmbus"
        echo "3. Monitor /tmp/wmbusmeters/ for meter readings"
        echo
        
        read -p "Would you like to test wM-Bus reception now? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            test_wmbus_reception
        fi
    else
        echo
        echo "⚠️  Software ready, but no RTL-SDR device detected"
        echo
        echo "📋 To complete setup:"
        echo "1. Purchase an RTL-SDR dongle (RTL2832U-based)"
        echo "2. Connect it to USB port"
        echo "3. Run this script again"
        echo "4. Start reception with: $HOME/.config/wmbusmeters/start_rtlsdr.sh"
    fi
    
    echo
    echo "=== RTL-SDR Setup Summary ==="
    echo "• Software: $([ $software_ok -eq 0 ] && echo "✓ Ready" || echo "✗ Failed")"
    echo "• Hardware: $([ $device_available -eq 0 ] && echo "✓ Connected" || echo "✗ Not detected")"
    echo "• Config: ✓ Created"
    echo "• Ready to receive: $([ $device_available -eq 0 ] && [ $software_ok -eq 0 ] && echo "✓ Yes" || echo "✗ Need hardware")"
}

# Run main function
main "$@"
