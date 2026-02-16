# Changelog v1.5.0 - Entity Unification & Bug Fixes

## Breaking Changes (Modbus Users Only)

### Entity Unique ID Format Changed
**Impact:** Existing Modbus users will see entity IDs change

**Before:** `{entry_id}_kronoterm_modbus_{address}`  
**After:** `{entry_id}_kronoterm_{entity_name}`

**Why:** Unifies unique_id format between Cloud API and Modbus modes, preventing duplicate entities during reconfiguration.

### Entity Names Unified with Cloud API
**Impact:** 14 entity names changed to match Cloud API

| Old Name (Modbus) | New Name (Unified) |
|-------------------|-------------------|
| error_status | error_warning |
| operation_mode | operation_regime |
| operating_hours_heating | operating_hours_compressor_heating |
| operating_hours_dhw | operating_hours_compressor_dhw |
| operating_hours_heater_1 | operating_hours_additional_source_1 |
| return_temperature | hp_inlet_temperature |
| outdoor_temperature | temperature_outside |
| supply_temperature | hp_outlet_temperature |
| evaporation_temperature | temperature_compressor_inlet |
| compressor_temperature | temperature_compressor_outlet |
| current_power_consumption | current_heating_cooling_capacity |
| system_pressure_setting | heating_system_pressure |
| cop | cop_value |
| scop | scop_value |

---

## Bug Fixes

### 1. ✅ Duplicate Entities Eliminated
**Problem:** Reconfiguring Cloud ↔ Modbus created 20+ duplicate entities

**Fix:**
- Changed Modbus unique_id format to match Cloud API
- Sensors: `{entry}_kronoterm_{name}` instead of `{entry}_kronoterm_modbus_{address}`
- Switches: Same format change

**Result:** Reconfigure now preserves entities, no duplicates!

### 2. ✅ DHW Circulation Switch Now Available in Modbus
**Problem:** `switch.kronoterm_dhw_circulation` unavailable in Modbus mode

**Fix:** Added register 2328 (`dhw_circulation_pump`) to `kronoterm.json`

**Result:** Switch now works in both Cloud and Modbus modes

### 3. ✅ Energy Sensor Names Unified
**Problem:** Energy sensors had different names in Cloud vs Modbus
- Cloud: `electrical_energy_heating_dhw`, `heating_energy_heating_dhw`
- Modbus: `electrical_energy_total`, `thermal_energy_total`

**Fix:** Renamed in `kronoterm.json` to match Cloud API

**Result:** Energy sensors now work identically in both modes

### 4. ✅ Defrost Status Sensor Enabled
**Problem:** Defrost status unavailable in Modbus mode

**Fix:** Removed `"disabled": true` from register 2011

**Result:** `sensor.kronoterm_defrost_status` now available

---

## New Features

### Seamless Reconfiguration
- Switch between Cloud API ↔ Modbus TCP without losing entities
- History preserved (same entity = same history)
- No manual cleanup required

### Complete Modbus Feature Parity
All switches now available in Modbus mode:
- ✅ Heat Pump On/Off
- ✅ Fast Water Heating
- ✅ Additional Source
- ✅ Reserve Source
- ✅ Anti-Legionella
- ✅ DHW Circulation ← **NEW!**

---

## Migration Guide

### For Existing Modbus Users

**Before updating:**
1. Note your current dashboard/automation entity IDs
2. Take screenshots of important graphs

**After updating to v1.5.0:**
1. Old entities become "unavailable"
2. New entities appear with correct unique_ids
3. Update dashboards to use new entity IDs
4. Clean up old unavailable entities:
   - Settings → Devices & Services → Entities
   - Filter by "kronoterm"
   - Delete unavailable entities

**History:** ❌ Not migrated (different unique_ids)

---

## Testing Checklist

- [ ] Switches all work (6 switches including DHW circulation)
- [ ] Energy sensors show correct values
- [ ] Climate entities show correct temperatures (20-50°C range)
- [ ] Defrost sensor appears
- [ ] Reconfigure Cloud → Modbus: zero duplicates
- [ ] Reconfigure Modbus → Cloud: zero duplicates

---

## Files Modified

1. `custom_components/kronoterm/kronoterm.json`
   - Added register 2328 (DHW circulation)
   - Renamed 14 registers to match Cloud API
   - Renamed 2 energy registers
   - Removed `disabled` flag from register 2011

2. `custom_components/kronoterm/sensor.py`
   - Changed `KronotermModbusRegSensor` unique_id format
   - Changed `KronotermEnumSensor` unique_id format

3. `custom_components/kronoterm/switch.py`
   - Changed `KronotermModbusSwitch` unique_id format
   - Added DHW circulation switch (register 2328)

---

## Known Issues

### Loop Temperature Sensors Unavailable
**Expected behavior:** `sensor.kronoterm_loop_1_temperature` and `sensor.kronoterm_loop_2_temperature` are intentionally unavailable to avoid duplication with climate entities.

**Workaround:** Use climate entity `current_temperature` attribute instead, or request re-enablement if separate sensors are needed.

---

## Version Info

**Version:** 1.5.0  
**Release Date:** 2026-02-16  
**Breaking:** Yes (Modbus users only)  
**Tested:** ✅ Modbus TCP, ✅ Cloud API

---

**Upgrade recommended for:** All Modbus users experiencing duplicate entities
