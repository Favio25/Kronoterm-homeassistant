# v1.3.0 - Local Modbus TCP Support & Climate Entities

## ⚠️ IMPORTANT: This Release is About LOCAL Modbus TCP

This update adds **local Modbus TCP support** for users who want to communicate directly with their heat pump over the local network. 

**Do you need this update?**
- ✅ **YES** - If you have a Modbus TCP adapter installed on your heat pump
- ✅ **YES** - If you want faster local polling and offline operation
- ℹ️ **OPTIONAL** - Cloud API users: This update also includes bug fixes and will work as before

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

### Seamless Mode Switching
- **Reconfigure Flow**: Switch between Cloud API and Modbus TCP without losing entity history
- **Keep your dashboards**: Entity IDs remain the same when switching modes
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

### Cloud API
- ✅ Fixed COP/SCOP display (now shows 7.90 instead of 790)
- ✅ Fixed outdoor temperature sensor address
- ✅ Fixed temperature scaling for all sensors
- ✅ Removed unavailable 500-range sensors

### Modbus TCP
- ✅ Fixed thermostat temperature filtering
- ✅ Fixed signed value support in register writes
- ✅ Proper handling of 32-bit registers

## 📚 Documentation

- Added [CLIMATE-COMPLETE.md](docs/CLIMATE-COMPLETE.md) - Complete climate entity guide
- Added [CLIMATE-MODBUS-MAPPING.md](docs/CLIMATE-MODBUS-MAPPING.md) - Register mappings
- Updated README with Modbus TCP setup instructions
- Organized all documentation in docs/ folder with index

## 🔄 Migration Notes

### Cloud API Users (No Hardware Change)
- ✅ **No breaking changes** - Everything works as before
- ✅ **Bug fixes applied**: COP/SCOP and temperature sensors now display correctly
- ✅ **No action required** - Update and restart Home Assistant

### New Modbus TCP Users (Have Modbus Adapter)
1. Update integration via HACS
2. Settings → Devices & Services → Kronoterm → Reconfigure
3. Select "Modbus TCP" mode
4. Enter heat pump IP address, port 502, unit ID 20
5. **4 new climate entities** will be created automatically
6. Some duplicate sensors removed (now in climate entities)

### Switching from Cloud API to Modbus TCP
- Entity IDs preserved (no dashboard reconfiguration needed)
- History retained
- Additional entities will appear (climate controls, more sensors)

## 📦 Installation

### Via HACS (Recommended)
1. HACS → Integrations → Kronoterm → ⋮ → Update
2. Restart Home Assistant
3. (Optional) Reconfigure to enable Modbus TCP mode

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
| **Setup Complexity** | Easy | Requires IP address |

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
