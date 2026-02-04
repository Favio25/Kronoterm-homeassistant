# v1.3.0 - Local Modbus TCP Support (Requires Adapter)

## ⚠️ IMPORTANT: Switching Connection Modes = History Loss

**If you switch from Cloud API to Modbus TCP (or vice versa), you WILL lose sensor history.**

### Why?
Cloud API and Modbus TCP are completely different data sources:
- **Different entity unique IDs**
- **Different sensor sets** (Modbus has 120+ entities, Cloud has ~80)
- **Different update mechanisms**

### What This Means:

**Scenario 1: Update v1.2.0 → v1.3.0, STAY on Cloud API**
- ✅ **History preserved** - all entity IDs remain the same
- ✅ **Safe to update** - just bug fixes applied
- ✅ **No action needed**

**Scenario 2: Update v1.2.0 → v1.3.0, SWITCH to Modbus TCP**
- ❌ **History lost** - Cloud API entities deleted, Modbus entities created
- ❌ **Dashboards break** - need to update all entity references
- ❌ **Energy statistics lost** - need to reconfigure energy dashboard
- ⚠️ **This is expected behavior** when switching data sources

**Scenario 3: New installation with Modbus TCP**
- ✅ **No problem** - fresh start with Modbus entities

### Recommendation:

**Don't switch modes unless you're prepared to lose history and reconfigure dashboards.**

If you want local Modbus control:
- Consider running BOTH integrations simultaneously (Cloud for history, Modbus for control)
- Or accept that switching = fresh start

---

## ⚠️ This Release is About LOCAL Modbus TCP

This update adds **local Modbus TCP support** for users who want to communicate directly with their heat pump over the local network. 

**Do you need this update?**
- ✅ **YES** - If you have a Modbus TCP adapter and want local control
- ✅ **YES** - Cloud API users get bug fixes (safe to update, stay on Cloud API)
- ℹ️ **THINK TWICE** - Before switching modes (see warning above)

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

### Seamless Mode Switching (⚠️ With Caveats)
- **Reconfigure Flow**: Switch between Cloud API and Modbus TCP
- Settings → Devices & Services → Kronoterm → Reconfigure
- **Warning**: Switching modes = new entities = history loss (see top)

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
- ✅ **Entity IDs unchanged** - history preserved if you stay on Cloud API

### Modbus TCP
- ✅ Fixed thermostat temperature filtering
- ✅ Fixed signed value support in register writes
- ✅ Proper handling of 32-bit registers

## 📚 Documentation

- Added [CLIMATE-COMPLETE.md](docs/CLIMATE-COMPLETE.md) - Complete climate entity guide
- Added [CLIMATE-MODBUS-MAPPING.md](docs/CLIMATE-MODBUS-MAPPING.md) - Register mappings
- Updated README with Modbus TCP setup instructions
- Organized all documentation in docs/ folder with index

## 🔄 Migration Scenarios

### ✅ Scenario A: Cloud API → Stay Cloud API
**What to do:**
1. Update via HACS
2. Restart Home Assistant
3. Done!

**What happens:**
- ✅ All entity IDs preserved
- ✅ History intact
- ✅ Bug fixes applied
- ✅ Dashboards work as before

---

### ⚠️ Scenario B: Cloud API → Switch to Modbus TCP
**What to do:**
1. **BACKUP FIRST** - Export dashboards, note energy sensors
2. Update via HACS
3. Settings → Devices & Services → Kronoterm → Reconfigure
4. Select Modbus TCP, enter IP/port
5. **Reconfigure dashboards** - all entity references changed
6. **Reconfigure energy dashboard** - entities recreated

**What happens:**
- ❌ Old Cloud API entities deleted
- ✅ New Modbus entities created
- ❌ All history lost (fresh start)
- ❌ Dashboards break (need entity ID updates)
- ❌ Energy statistics lost

**Why this happens:**
- Different coordinators = different unique IDs
- Cloud entity: `sensor.outdoor_temperature` (from cloud)
- Modbus entity: `sensor.outdoor_temperature` (from modbus) 
- They look similar but Home Assistant sees them as completely different entities

---

### ✅ Scenario C: New Modbus TCP Installation
**What to do:**
1. Install via HACS
2. Add Integration → Select Modbus TCP
3. Configure and enjoy!

**What happens:**
- ✅ Fresh Modbus entities
- ✅ No conflicts
- ✅ No history concerns

---

### 💡 Scenario D: Run Both Simultaneously (Advanced)
**What to do:**
1. Keep existing Cloud API integration (for history)
2. Add NEW Kronoterm integration (Modbus TCP)
3. Both run side-by-side

**Benefits:**
- ✅ Cloud API history preserved
- ✅ Modbus TCP fast control + climate entities
- ✅ Compare both data sources
- ⚠️ Double the entities (can be confusing)

## 📦 Installation

### Via HACS (Recommended)
1. HACS → Integrations → Kronoterm → ⋮ → Update
2. Restart Home Assistant
3. (Optional) Reconfigure if switching to Modbus TCP ⚠️ History loss!

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
| **History Preserved (when switching)** | ❌ No | ❌ No |
| **History Preserved (staying same mode)** | ✅ Yes | N/A |

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
- Stay on Cloud API mode (works great!)
- All bug fixes still apply to you
- No new hardware needed

## 🙏 Credits

Thanks to the Home Assistant community for testing and feedback!

Special thanks to contributors who helped with Modbus TCP implementation and testing.

---

**Full Changelog**: https://github.com/Favio25/Kronoterm-homeassistant/compare/v1.2.0...v1.3.0

**Support**: Open an issue on GitHub if you need help

**Pro Tip**: Want Modbus control but keep Cloud history? Run both integrations simultaneously!
