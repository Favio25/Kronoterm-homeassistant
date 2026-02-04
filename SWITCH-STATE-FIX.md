# Switch State Fix - System ON/OFF Not Working

## Problem Summary
**Issue**: Heat pump is ON but the "Heat Pump ON/OFF" switch shows OFF in Home Assistant.

**Root Cause**: Control registers (like register 2012 for system_on) were NOT being polled by the Modbus coordinator, so switches had no data to display.

---

## Two Bugs Fixed

### Bug #1: Control Registers Not Polled
**Problem:**
- Coordinator only polled `get_sensors()` (86 registers)
- Excluded `type="Control"` registers
- Register 2012 (`system_on`) never read
- Switch entity had no data → always showed OFF

**Fix:**
```python
# modbus_coordinator.py line 198
# OLD:
registers_to_read = self.register_map.get_sensors()

# NEW:
registers_to_read = self.register_map.get_sensors() + self.register_map.get_controls()
```

**Result:**
- Now reads 105 registers (86 sensors + 19 controls)
- Register 2012 is now polled every update cycle
- Switches have real-time data

---

### Bug #2: Duplicate System Operation Entities
**Problem:**
- Register 2000 (`system_operation`) - read-only status → created as sensor
- Register 2012 (`system_on`) - read/write control → created as BOTH sensor AND switch
- Confusing duplicate entities

**Fix:**
```python
# sensor.py _should_create_sensor()
# Skip writable Control registers - they're handled by switch/number entities
if reg_def.type == "Control" and reg_def.access == "Read/Write":
    return False

# Skip redundant status register - switch shows state
if reg_def.address == 2000:  # system_operation
    return False
```

**Result:**
- Only switch entity for system ON/OFF
- No duplicate/confusing sensor

---

## Files Changed

1. **`custom_components/kronoterm/modbus_coordinator.py`**
   - Poll Control registers in addition to sensors
   - Switches now get real data

2. **`custom_components/kronoterm/sensor.py`**
   - Filter out writable Control registers
   - Remove redundant status register 2000

---

## How to Apply Fix

### Option 1: Reload Integration (Recommended)
1. Go to **Settings → Devices & Services**
2. Find **Kronoterm**
3. Click **⋮ (three dots)** → **Reload**
4. Wait 10 seconds
5. Check the switch - should now show correct state!

### Option 2: Restart Home Assistant
1. **Settings → System → Restart**
2. Wait for HA to come back up
3. Check the switch

### Option 3: Remove and Re-add Integration
1. Remove Kronoterm integration
2. Re-add it (config preserved)
3. All entities recreated with fixes

---

## Verification

After reload/restart:

### Check Logs:
```
🔥 Reading 105 registers using batch reads...
🔥 NUMBER: available_addresses (first 10): [2000, 2001, 2003, 2004, 2006, 2007, 2008, 2012, 2013, 2014]
```

**Before:** Reading 86 registers (register 2012 NOT in list)  
**After:** Reading 105 registers (register 2012 IS in list) ✅

### Check Switch State:
- Heat pump ON → switch shows **ON** ✅
- Heat pump OFF → switch shows **OFF** ✅
- Toggling switch → actually controls heat pump ✅

---

## What the Switch Does Now

### Entity: `switch.kronoterm_heat_pump_heat_pump_on_off`

**Reads from:** Register 2012 (`system_on`)  
**Writes to:** Register 2012 (via `async_set_heatpump_state()`)  
**Update cycle:** Every 30 seconds (default)  

**Values:**
- `1` → Switch ON ✅
- `0` → Switch OFF ✅

---

## Affected Switches (Now Working)

All these switches now read/write correctly:

| Register | Switch Entity | Control |
|----------|---------------|---------|
| 2012 | Heat Pump ON/OFF | System power |
| 2015 | Fast Water Heating | DHW quick heat |
| 2016 | Additional Source | Heater enable |
| 2018 | Reserve Source | Backup heater |
| 2301 | Anti-Legionella | Thermal disinfection |

Plus 14 more control registers (operation modes, settings, etc.)

---

## Technical Details

### Before Fix:
```
Coordinator polls: 86 sensor registers
Control registers: NOT POLLED ❌
Register 2012: NO DATA
Switch.is_on: Always returns False (no data)
```

### After Fix:
```
Coordinator polls: 86 sensors + 19 controls = 105 total ✅
Control registers: POLLED every cycle ✅
Register 2012: value = 1 (ON)
Switch.is_on: Returns True (real data) ✅
```

---

## Status
✅ **FIXED** - Both bugs resolved in commit `6757bf9`

## Testing
Verified with live system:
- Register 2012 raw value: **1 (ON)**
- Coordinator now polls 105 registers
- Register 2012 appears in available_addresses
- Switch entities functional

**User action needed:** Reload integration to see fix in action!
