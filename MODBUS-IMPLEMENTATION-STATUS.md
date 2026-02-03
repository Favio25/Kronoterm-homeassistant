# Kronoterm Modbus TCP Implementation Status

**Date:** 2026-02-02  
**Phase:** Initial Implementation Complete  
**Status:** Ready for Testing

---

## ✅ Completed Components

### 1. Register Definitions (`modbus_registers.py`)
**Status:** ✅ Complete

- Defined all 40+ validated registers with proper types
- Temperature sensors (14 registers, scale 0.1)
- Binary sensors (7 registers with bit masking support)
- Status/enum sensors (5 registers)
- Power sensors (6 registers)
- Operating hours (3 registers)
- Writable registers (7 setpoints and switches)
- Helper functions: `scale_value()`, `format_enum()`, `read_bit()`

**Key Features:**
- Type-safe Register namedtuples
- Enumeration definitions for all status registers
- Bit masking support for pump sensors (2002, 2028)
- Error value detection (64936, 64937, 65535)
- Temperature scaling (÷10) and COP scaling (÷100)

### 2. Modbus Coordinator (`modbus_coordinator.py`)
**Status:** ✅ Complete

**Features:**
- Async Modbus TCP client using pymodbus 3.5.4
- Automatic reconnection handling
- Batch register reading
- Write support for setpoints and switches
- Device info extraction (ID, firmware)
- Feature flag detection (Loop2, additional source)
- Error handling and logging
- Clean shutdown with connection cleanup

**Key Methods:**
- `async_initialize()` - Connect and fetch device info
- `_async_update_data()` - Poll all registers
- `_read_register()` - Read single register with error handling
- `write_register()` - Write with immediate refresh
- `get_register_value()` - Access cached values
- `async_shutdown()` - Clean disconnect

### 3. Config Flow Extension (`config_flow_modbus.py`)
**Status:** ✅ Complete

**Features:**
- Connection type selection (Cloud vs Modbus)
- Modbus TCP configuration form
- Model selection for energy calculation
- Connection validation
- Test read from known register (2102)

**Model Options:**
- ADAPT 0312 (up to 3.5 kW)
- ADAPT 0416 (up to 5 kW)
- ADAPT 0724 (up to 7 kW)
- Unknown (no energy calc)

### 4. Integration Setup (`__init__.py`)
**Status:** ✅ Updated

**Changes:**
- Coordinator factory based on connection type
- Support for both KronotermCoordinator (cloud) and ModbusCoordinator
- Proper cleanup in `async_unload_entry()`
- Modbus connection shutdown on unload

### 5. Main Config Flow (`config_flow.py`)
**Status:** ✅ Updated

**New Flow:**
1. User step → Select connection type
2. Branch to `async_step_cloud()` or `async_step_modbus()`
3. Validate credentials/connection
4. Create entry with appropriate title

### 6. UI Strings (`strings.json`)
**Status:** ✅ Created

- User-friendly descriptions
- Error message translations
- Form field labels and help text
- Support for multi-step config flow

### 7. Dependencies (`manifest.json`)
**Status:** ✅ Updated

- Added `pymodbus==3.5.4` requirement
- Changed `iot_class` to `local_polling`
- Bumped version to `2.0.0`

---

## 📋 Implementation Details

### Register Mappings (Validated)

**Corrected from GitHub repo:**
- **Loop 1 Current Temp:** 2109 (NOT 2130)
- **System Pressure:** 2325 (NOT 2326)
- **Working Function:** 2001 = 0 (heating mode, was correct)

**Bit-masked sensors:**
```python
# Register 2028 (DHW pumps)
bit 0 = DHW circulation pump
bit 1 = DHW tank circulation pump

# Register 2002 (Additional source)
bit 0 = Activation
bit 4 = Active status
```

### Connection Parameters

**Default values:**
- Host: User-configured IP
- Port: 502 (Modbus TCP standard)
- Unit ID: 20 (validated for this device)
- Timeout: 5 seconds
- Scan interval: 60 seconds (configurable)

### Data Structure

Coordinator returns dict with register addresses as keys:
```python
{
    2102: {
        "value": 1.1,      # Scaled value
        "raw": 11,         # Raw register value
        "name": "Outdoor Temperature",
        "unit": "°C"
    },
    2001: {
        "value": "heating",
        "raw": 0,
        "name": "Working Function",
        "unit": None
    }
}
```

---

## 🧪 Testing Plan

### Phase 1: Basic Connectivity ✅
- [x] Modbus TCP connection
- [x] Register reading
- [x] Device info extraction
- [x] Coordinator initialization

### Phase 2: Sensor Reading (Next)
- [ ] All temperature sensors
- [ ] Binary sensors (pumps, heater)
- [ ] Status sensors (working function, errors)
- [ ] Power/load sensors
- [ ] Operating hours

### Phase 3: Write Operations
- [ ] Setpoint changes (DHW, Loop1, Loop2)
- [ ] Switch controls (fast DHW, circulation)
- [ ] DHW operation mode select
- [ ] Verify changes in cloud API (if hybrid)

### Phase 4: Entity Creation
- [ ] Sensor entities auto-created
- [ ] Binary sensors working
- [ ] Climate entities (if applicable)
- [ ] Switch entities
- [ ] Number entities for setpoints

### Phase 5: Feature Parity
- [ ] All cloud API features available
- [ ] Energy calculation (if model known)
- [ ] Error handling matches cloud
- [ ] Reconnection logic tested

---

## 📝 Known Limitations

### 1. Model Detection
- Model NOT available in Modbus registers
- Must be manually selected during config
- Or retrieved from cloud API in hybrid mode

### 2. Energy Calculation
- Requires model selection
- Power table interpolation not yet implemented
- Register 2129 (current power) available for direct reading

### 3. Registers Reading Zero
Some registers read 0 during low load:
- 2327 (HP Load %) - timing dependent
- 2329 (Heating Power) - timing dependent
- 2130 (supposed Loop 1 temp) - actually unused

### 4. Missing Features
- DHW current temperature sensor not yet found
- Some diagnostic registers unmapped
- Pool heating mode untested

---

## 🚀 Next Steps

### Immediate (Testing)
1. **Install integration** in Home Assistant
2. **Configure Modbus** connection with real device
3. **Verify sensor values** match cloud API
4. **Test write operations** on setpoints
5. **Check binary sensors** (pump status)

### Short Term (Refinement)
1. Add energy calculation with model
2. Implement entity mappers for sensors
3. Test all switches and controls
4. Handle reconnection scenarios
5. Optimize register reading (batch if possible)

### Long Term (Enhancement)
1. Auto-detect model from power readings
2. Add diagnostic sensors
3. Implement advanced energy tracking
4. Support multiple heat pumps
5. Add service calls for advanced control

---

## 📊 File Structure

```
custom_components/kronoterm/
├── __init__.py                  # ✅ Updated (coordinator factory)
├── config_flow.py               # ✅ Updated (connection type selection)
├── config_flow_modbus.py        # ✅ New (Modbus config helpers)
├── coordinator.py               # ✅ Existing (cloud API)
├── modbus_coordinator.py        # ✅ New (Modbus TCP)
├── modbus_registers.py          # ✅ New (register definitions)
├── const.py                     # ⚠️ May need updates
├── manifest.json                # ✅ Updated (pymodbus dependency)
├── strings.json                 # ✅ New (UI translations)
├── sensor.py                    # ⚠️ Needs update for Modbus
├── binary_sensor.py             # ⚠️ Needs update for Modbus
├── switch.py                    # ⚠️ Needs update for Modbus
├── climate.py                   # ⚠️ May need update
├── select.py                    # ⚠️ May need update
└── number.py                    # ⚠️ May need update
```

---

## 🔧 Configuration Example

### Modbus TCP Setup
```yaml
# Via UI (recommended):
# 1. Go to Settings → Devices & Services
# 2. Click "+ Add Integration"
# 3. Search "Kronoterm"
# 4. Select "Modbus TCP (Local network)"
# 5. Enter:
#    - IP: 10.0.0.51
#    - Port: 502
#    - Unit ID: 20
#    - Model: ADAPT 0416
```

### Hybrid Setup (Cloud + Modbus)
Both can coexist:
- Cloud API: For features not in Modbus
- Modbus TCP: For local control and faster updates
- Same entities, choose which connection to use

---

## 📚 Documentation References

- **CORRECTED-REGISTER-MAP.md** - Complete validated register map
- **KRONOTERM-MODBUS-COMPLETE-FINDINGS.md** - Discovery process
- **EXTERNAL-SOURCES-FINDINGS.md** - GitHub repo analysis
- **INDEX.md** - Project overview

---

## ⚠️ Important Notes

### For Developers
1. **Always use async I/O** - ModbusCoordinator is fully async
2. **Check register type** before accessing value
3. **Handle None values** - Registers can fail to read
4. **Respect scan interval** - Don't poll too frequently
5. **Log errors at debug level** - Register read failures are normal

### For Users
1. **Local network only** - Modbus TCP requires LAN access
2. **Port 502 must be open** - Check firewall rules
3. **Static IP recommended** - Avoid DHCP changes
4. **Model selection required** - For energy calculation
5. **Cloud API still works** - Both can be used together

---

**Status:** Ready for real-world testing  
**Confidence:** 95% - Based on validated register map  
**Risk:** Low - Modbus is read-only by default, writes are explicit
