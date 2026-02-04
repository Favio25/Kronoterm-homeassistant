# v1.3.0 - Modbus Climate Entities & Major Improvements

## 🎉 Major Features

### Climate Entities (Modbus Mode)
- **4 Climate Controls**: DHW, Heating Loop 1-2, Reservoir
- **Smart Temperature Sensors**: Automatically prefers thermostat temperature over loop outlet temperature
- **Direct Control**: Set target temperatures with instant Modbus register writes
- **Intelligent Mapping**: Loop 2 displays room temperature (23.2°C) from thermostat instead of loop outlet (27.8°C)

### Improved Sensor Support
- **120+ Entities**: Full register coverage via JSON-based register map
- **Proper Scaling**: Fixed COP/SCOP display (7.90 instead of 790)
- **Removed Duplicates**: Clean entity list without redundant sensors
- **Cloud API Fixes**: Correct temperature scaling for raw register values

## 🔧 Improvements

### Configuration
- **Simplified Setup**: Removed unused model selection from Modbus config
- **Reconfigure Flow**: Switch between Cloud API and Modbus without losing entity history

### Performance
- **Batch Reading**: 133x faster Modbus initialization (0.28s instead of 37s)
- **Smart Polling**: Configurable update interval (5-600 seconds)
- **Writable Registers**: Number entities for adjustable parameters

### Code Quality
- **JSON-Based**: Data-driven register map from official Kronoterm documentation
- **Documentation**: Comprehensive guides in docs/ folder
- **Clean Structure**: Organized repository with proper documentation

## 🐛 Bug Fixes

- Fixed double-scaling issue for Cloud API sensors
- Fixed outdoor temperature sensor address (2102 → 2103)
- Fixed thermostat temperature filtering (ignore 0.0 values)
- Removed unavailable 500-range sensors from Cloud API
- Fixed signed value support in register writes
- Proper handling of 32-bit registers in batch reads

## 📚 Documentation

- Added [CLIMATE-COMPLETE.md](docs/CLIMATE-COMPLETE.md) - Complete climate entity guide
- Added [CLIMATE-MODBUS-MAPPING.md](docs/CLIMATE-MODBUS-MAPPING.md) - Register mappings
- Updated README with comprehensive feature documentation
- Organized all documentation in docs/ folder with index

## 🔄 Migration Notes

### From v1.2.0
- **No breaking changes** - All existing entities preserved
- **New entities** will appear if using Modbus mode
- **Reconfigure** to enable climate entities (Settings → Devices & Services → Kronoterm → Reconfigure)

### Cloud API Users
- All sensors now display correct values (fixed scaling)
- No action required - update will apply automatically

### Modbus Users
- **4 new climate entities** will be created automatically
- Some duplicate sensors removed (e.g., Loop 1 Temperature - now in climate entity)
- Update interval can now be configured in seconds (was fixed before)

## 📦 Installation

### Via HACS
1. HACS → Integrations → ⋮ → Check for Updates
2. Update Kronoterm integration
3. Restart Home Assistant

### Manual
1. Download `Source code (zip)` below
2. Extract to `custom_components/kronoterm/`
3. Restart Home Assistant

## ⚙️ Technical Details

**Supported Platforms:**
- Home Assistant 2023.1.0+
- Python 3.11+

**Connection Modes:**
- Cloud API (Internet-based)
- Modbus TCP (Local network)

**Tested With:**
- Hydro S + Adapt 0416-K3 HT / HK 3F
- Hydro C 2 + Adapt 0312-K3 HT / HK 1F

## 🙏 Credits

Thanks to the Home Assistant community for testing and feedback!

---

**Full Changelog**: https://github.com/Favio25/Kronoterm-homeassistant/compare/v1.2.0...v1.3.0
