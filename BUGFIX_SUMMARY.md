# Bug Fix Summary - v1.5.0

## Issues Fixed

### Issue #1: Climate Entities Showing 500°C ❌→✅

**Root Cause:** Missing `scale` fields in `kronoterm.json`

**What Was Broken:**
- Climate entity target temperature showed 500°C instead of 50.0°C
- All temperature sensors showed values 10x too high (255°C instead of 25.5°C)
- Register 2191 (`loop_1_room_current_setpoint`) had special scale 0.01 but field was missing

**Fix Applied:**
- Added `"scale": 0.1` to 61 temperature/pressure registers
- Added `"scale": 0.01` to 1 special register (2191)
- Coordinator now correctly applies scaling from JSON

**Example:**
```json
Before:
{
  "address": 2191,
  "unit": "x 0.01°C",
  // Missing: "scale": 0.01
}
Raw value: 5000 → Displayed: 5000°C ❌

After:
{
  "address": 2191,
  "unit": "x 0.01°C",
  "scale": 0.01  ← Added
}
Raw value: 5000 → Scaled: 50.0°C ✅
```

**Affected Registers:**
- 2023, 2024: DHW setpoints
- 2101-2112: All temperature sensors
- 2128, 2130: Loop 1 temperatures
- 2160-2163: Thermostat temperatures
- 2187-2191: Loop setpoints
- 2325-2326: System pressure
- And 40+ more...

**Test Case:**
```python
# Before fix
climate.loop_1.target_temperature → 500.0°C  ❌
sensor.outdoor_temperature → 255.0°C  ❌

# After fix
climate.loop_1.target_temperature → 50.0°C  ✅
sensor.outdoor_temperature → 25.5°C  ✅
```

---

### Issue #2: Duplicate Entities After Reconfigure ❌→✅

**Root Cause:** Naming mismatch between Cloud API and Modbus mode

**What Was Broken:**
- Reconfiguring from Cloud → Modbus created 14 duplicate entities
- Different entity_ids for same register (e.g., `error_status` vs `error_warning`)
- Users had to manually delete old entities

**Fix Applied:**
- Unified all entity names to match Cloud API naming scheme
- 14 register names in `kronoterm.json` updated

**Changed Names:**
| Address | Old (Modbus) | New (Unified) |
|---------|--------------|---------------|
| 2006 | `error_status` | `error_warning` |
| 2007 | `operation_mode` | `operation_regime` |
| 2090 | `operating_hours_heating` | `operating_hours_compressor_heating` |
| 2091 | `operating_hours_dhw` | `operating_hours_compressor_dhw` |
| 2095 | `operating_hours_heater_1` | `operating_hours_additional_source_1` |
| 2101 | `return_temperature` | `hp_inlet_temperature` |
| 2103 | `outdoor_temperature` | `temperature_outside` |
| 2104 | `supply_temperature` | `hp_outlet_temperature` |
| 2105 | `evaporation_temperature` | `temperature_compressor_inlet` |
| 2106 | `compressor_temperature` | `temperature_compressor_outlet` |
| 2129 | `current_power_consumption` | `current_heating_cooling_capacity` |
| 2325 | `system_pressure_setting` | `heating_system_pressure` |
| 2371 | `cop` | `cop_value` |
| 2372 | `scop` | `scop_value` |

**Impact:**
- ✅ Reconfigure now preserves entities (same entity_id)
- ❌ Existing Modbus users will see entity_id changes (breaking)
- ✅ Long-term: cleaner, more maintainable codebase

---

### Issue #3: Missing Sensors in Modbus Mode ❌→✅

**Root Cause:** Register 2011 (`defrost_status`) had `"disabled": true`

**What Was Broken:**
- Defrost status sensor not available in Modbus mode
- Cloud API users had it, Modbus users didn't

**Fix Applied:**
- Removed `"disabled": true` from register 2011
- Sensor now appears as `sensor.kronoterm_defrost_status`

**Before:**
```json
{
  "address": 2011,
  "name_en": "defrost_status",
  "disabled": true  ← Prevented entity creation
}
```

**After:**
```json
{
  "address": 2011,
  "name_en": "defrost_status"
  // disabled flag removed
}
```

---

## Files Changed

1. **custom_components/kronoterm/kronoterm.json**
   - Added 62 `scale` fields for temperature/pressure registers
   - Renamed 14 registers to match Cloud API
   - Removed `disabled` flag from register 2011

2. **BREAKING_CHANGES.md** (new)
   - Migration guide for existing Modbus users
   - Entity ID change table
   - Upgrade instructions

3. **BUGFIX_SUMMARY.md** (this file)
   - Detailed technical explanation of all fixes

---

## Testing Recommendations

1. **Temperature Readings:**
   - Verify climate entities show ~20-50°C range (not 200-500°C)
   - Check outdoor temp sensor shows realistic values
   - Confirm DHW target temp is 45-60°C range

2. **Entity Naming:**
   - Cloud → Modbus reconfigure should NOT create duplicates
   - Existing Modbus users: entity_ids will change (expected)

3. **New Sensor:**
   - Verify `sensor.kronoterm_defrost_status` appears
   - Should show "No defrost" / "Defrosting in progress"

---

## Version History

- **v1.4.x**: Modbus mode had broken temperature scaling (500°C bug)
- **v1.5.0**: All temperature issues fixed, entity names unified

---

**Severity:** Critical (temperatures completely wrong in Modbus mode)  
**Affected Users:** All Modbus TCP users (Cloud API unaffected)  
**Recommended Action:** Update immediately if using Modbus mode
