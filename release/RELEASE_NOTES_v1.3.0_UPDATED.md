# v1.3.0 - Local Modbus TCP Support (Requires Adapter)

## ⚠️ BREAKING CHANGE - MODBUS USERS READ THIS

**If you're using Modbus TCP mode (v1.2.0), DO NOT update to v1.3.0 yet!**

This version changes entity unique IDs, which will cause:
- ❌ **Loss of all sensor history**
- ❌ All Modbus entities will be recreated with new IDs
- ❌ Dashboards will break (need to reconfigure)
- ❌ Energy statistics will be lost

**We are working on a migration path for v1.3.1. Please wait for the next release if you want to preserve your history.**

**Cloud API users:** You are NOT affected by this issue. Safe to update.

---

## ⚠️ IMPORTANT: This Release is About LOCAL Modbus TCP

This update adds **local Modbus TCP support** for users who want to communicate directly with their heat pump over the local network. 

**Do you need this update?**
- ✅ **YES** - If you have a Modbus TCP adapter and are NEW to this integration
- ⚠️ **WAIT** - If you're already using Modbus TCP v1.2.0 (see breaking change above)
- ℹ️ **SAFE** - Cloud API users: This update includes bug fixes and will work as before

### 🔌 Hardware Requirements for Modbus TCP

To use Modbus TCP features, you need:
1. **Kronoterm heat pump** with Modbus TCP interface/adapter
2. **Network connection** between Home Assistant and heat pump (same local network)
3. **Known IP address** of your heat pump

**If you don't have Modbus TCP hardware:**
- The integration will continue to work via Cloud API (no changes needed)
- You can still benefit from bug fixes included in this release

---

## 🎉 Major New Features (Modbus TCP Mode)

### Local Modbus TCP Connection
- **Direct local network communication** - No internet required
- **Fast polling**: 5-600 seconds configurable (Cloud API is ~60s minimum)
- **Offline operation**: Works even when Kronoterm cloud is down
- **120+ entities**: Full register access via official Kronoterm documentation

### Climate Entities (Modbus Mode Only)
- **4 Climate Controls**: DHW, Heating Loop 1-2, Reservoir
- **Smart Temperature Sensors**: Automatically prefers thermostat temperature over loop outlet temperature
- **Direct Control**: Set target temperatures with instant Modbus register writes
- **Intelligent Mapping**: Loop 2 displays room temperature (23.2°C) from thermostat instead of loop outlet (27.8°C)

### Seamless Mode Switching (New Installs Only)
- **Reconfigure Flow**: Switch between Cloud API and Modbus TCP
- Settings → Devices & Services → Kronoterm → Reconfigure

## 🔧 Improvements (Both Modes)

### Configuration
- **Simplified Setup**: Removed unused model selection from Modbus config
- **Better validation**: Clearer error messages during setup

### Performance (Modbus TCP)
- **Batch Reading**: 133x faster initialization (0.28s instead of 37s)
- **Optimized polling**: Groups consecutive registers to reduce network traffic

### Code Quality
- **JSON-Based**: Data-driven register map from official Kronoterm documentation
- **Comprehensive Documentation**: New guides in docs/ folder
- **Clean Structure**: Organized repository

## 🐛 Bug Fixes (Both Modes)

### Cloud API (SAFE TO UPDATE)
- ✅ Fixed COP/SCOP display (now shows 7.90 instead of 790)
- ✅ Fixed outdoor temperature sensor address
- ✅ Fixed temperature scaling for all sensors
- ✅ Removed unavailable 500-range sensors
- ✅ **No entity ID changes - history preserved**

### Modbus TCP (HAS BREAKING CHANGE)
- ✅ Fixed thermostat temperature filtering
- ✅ Fixed signed value support in register writes
- ✅ Proper handling of 32-bit registers
- ⚠️ **Entity IDs changed - history will be lost**

## 📚 Documentation

- Added [CLIMATE-COMPLETE.md](docs/CLIMATE-COMPLETE.md) - Complete climate entity guide
- Added [CLIMATE-MODBUS-MAPPING.md](docs/CLIMATE-MODBUS-MAPPING.md) - Register mappings
- Updated README with Modbus TCP setup instructions
- Organized all documentation in docs/ folder with index

## 🔄 Migration Notes

### Cloud API Users (SAFE TO UPDATE)
- ✅ **No breaking changes** - Everything works as before
- ✅ **Bug fixes applied**: COP/SCOP and temperature sensors now display correctly
- ✅ **History preserved**: All entity IDs remain the same
- ✅ **No action required** - Update and restart Home Assistant

### Existing Modbus TCP Users (v1.2.0) ⚠️ DO NOT UPDATE
- ❌ **Breaking change**: Entity unique IDs have changed
- ❌ **History will be lost** for all sensors
- ❌ **Dashboards will break** - all entity references need updating
- ⏳ **Wait for v1.3.1** - Migration path coming soon

**Why the change?**
To support running Cloud API and Modbus TCP simultaneously. However, we understand this is disruptive and will provide a migration solution in v1.3.1.

### New Modbus TCP Users (First Time Setup)
1. Update integration via HACS
2. Settings → Devices & Services → Kronoterm → Add Integration
3. Select "Modbus TCP" mode
4. Enter heat pump IP address, port 502, unit ID 20
5. **4 climate entities** will be created automatically

## 📦 Installation

### Via HACS
**Cloud API users:** Safe to update  
**Modbus TCP v1.2.0 users:** Please wait for v1.3.1

1. HACS → Integrations → Kronoterm → ⋮ → Update
2. Restart Home Assistant

### Manual
1. Download `Source code (zip)` below
2. Extract to `custom_components/kronoterm/`
3. Restart Home Assistant

## ⚙️ Connection Mode Comparison

| Feature | Cloud API | Modbus TCP |
|---------|-----------|------------|
| **Hardware Required** | None | Modbus TCP adapter |
| **Network** | Internet | Local only |
| **Speed** | ~60s refresh | 5-600s configurable |
| **Reliability** | Depends on cloud | Direct connection |
| **Climate Entities** | No | Yes (4 entities) |
| **Sensors** | ~80 entities | ~120 entities |
| **Offline Operation** | ❌ No | ✅ Yes |
| **History Preserved (this update)** | ✅ Yes | ❌ No (v1.3.1 will fix) |

## 🔌 Modbus TCP Hardware Information

**Supported heat pumps:**
- Kronoterm heat pumps with built-in Modbus TCP interface
- Kronoterm heat pumps with Modbus TCP adapter installed
- Tested with: Hydro S, Hydro C 2 series

**Connection requirements:**
- Heat pump IP address (find in heat pump menu or router DHCP list)
- Port: 502 (Modbus TCP default)
- Unit ID: 20 (Kronoterm default)
- Local network connectivity

**Don't have Modbus TCP?**
- Continue using Cloud API mode (works great!)
- All bug fixes still apply to you
- No new hardware needed

## 🙏 Credits

Thanks to the Home Assistant community for testing and feedback!

Special thanks to contributors who helped with Modbus TCP implementation and testing.

---

**Full Changelog**: https://github.com/Favio25/Kronoterm-homeassistant/compare/v1.2.0...v1.3.0

**Support**: Open an issue on GitHub if you need help

**Coming in v1.3.1**: Migration script to preserve Modbus sensor history
