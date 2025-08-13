# RTL-SDR Setup for wmbusmeters - Complete Guide

## 🎉 Setup Status: COMPLETE ✅

Your RTL-SDR environment is fully configured and ready to use!

### ✅ What's Ready

- **RTL-SDR Tools**: Installed via Homebrew (`rtl_test`, `rtl_sdr`, etc.)
- **rtl_wmbus**: Compiled and integrated with wmbusmeters
- **wmbusmeters**: RTL-SDR support enabled and tested
- **Configuration**: Auto-generated config files
- **Scripts**: Ready-to-use startup scripts

### 📁 Created Files

```
~/.config/wmbusmeters/rtlsdr.conf    # RTL-SDR configuration
./start_rtlsdr.sh                    # Quick start script
./setup_rtlsdr.sh                    # Full setup script
./build/rtl_wmbus                    # RTL-SDR to wM-Bus bridge
```

### 🛒 Hardware Required

You need an **RTL-SDR USB dongle** to receive wM-Bus signals:

#### Recommended Models:
- **RTL-SDR Blog v3** (~$25) - Best performance
- **NooElec NESDR Smart** (~$30) - Good build quality  
- **Generic RTL2832U** (~$15) - Budget option

#### Where to Buy:
- **Amazon**: Search "RTL-SDR v3" or "NooElec NESDR"
- **AliExpress**: Search "RTL2832U R820T2" 
- **Adafruit**: RTL-SDR dongles
- **Local electronics stores**

#### Technical Specs:
- **Chipset**: RTL2832U + R820T2 tuner
- **Frequency**: 500kHz - 1.7GHz (covers 868MHz wM-Bus)
- **USB**: 2.0/3.0 compatible
- **Antenna**: Included telescopic antenna works fine

### 🚀 Quick Start (Once You Have Hardware)

1. **Connect RTL-SDR** to USB port
2. **Start Reception**:
   ```bash
   cd /Volumes/dev/space/wmblatest/wmbusmeters
   ./start_rtlsdr.sh
   ```
3. **Monitor Output**: Check `/tmp/wmbusmeters/` for meter readings

### 📡 Usage Examples

```bash
# Listen to all wM-Bus modes
./start_rtlsdr.sh all

# Listen to specific mode
./start_rtlsdr.sh c1    # Most common in EU
./start_rtlsdr.sh t1    # Alternative mode
./start_rtlsdr.sh s1    # Short telegrams

# Manual operation
./build/wmbusmeters rtlwmbus:c1,t1,s1
```

### 🔧 Configuration

Your RTL-SDR config (`~/.config/wmbusmeters/rtlsdr.conf`):
- **Device**: `rtlwmbus` (automatic RTL-SDR detection)
- **Modes**: C1 (868.95MHz), T1/S1 (868.3MHz)
- **Output**: JSON format to `/tmp/wmbusmeters/`
- **Logging**: Enabled with debug info

### 📊 What You'll See

When wM-Bus meters are detected:
```json
{
  "media": "water",
  "meter": "kamstrup",
  "name": "MyWaterMeter",
  "id": "12345678",
  "total_m3": 123.456,
  "timestamp": "2025-08-13T04:30:00Z"
}
```

### 🐛 Troubleshooting

#### No Device Found
```bash
rtl_test -t  # Should show "Found 1 device(s)"
```

#### No Telegrams Received
- Check if wM-Bus meters exist in your area
- Try different frequencies: EU (868MHz), US (915MHz)
- Move closer to smart meters
- Check antenna connection

#### Permission Issues
```bash
# Add user to dialout group (Linux) or use sudo
sudo ./start_rtlsdr.sh
```

### 🆚 RTL-SDR vs Bluetooth Devices

| Method | Cost | Range | Compatibility | Setup |
|--------|------|--------|---------------|--------|
| **RTL-SDR** | $15-35 | 100m+ | Universal | Easy |
| **Bluetooth** | $50-150 | 10m | Device-specific | Complex |

**RTL-SDR Advantages:**
- ✅ Works with any wM-Bus transmitter
- ✅ No pairing required  
- ✅ Long range reception
- ✅ Multiple meters simultaneously
- ✅ Inexpensive

### 🔮 Next Steps

1. **Order RTL-SDR dongle** (if you haven't already)
2. **Test in different locations** to find optimal signal
3. **Set up automated logging** for continuous monitoring
4. **Configure specific meters** once detected

### 📞 Support

If you encounter issues:
1. Run `./setup_rtlsdr.sh` to re-check setup
2. Check RTL-SDR connection with `rtl_test -t`
3. Verify wM-Bus activity in your area
4. Try different antenna positions

---

**Your RTL-SDR environment is ready! 🎯**  
Just connect the hardware and start receiving wM-Bus data!
