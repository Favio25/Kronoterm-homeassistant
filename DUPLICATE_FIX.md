# Duplicate Entity Fix - v1.5.0

## Problem

When reconfiguring from Cloud API → Modbus (or vice versa), many entities appeared twice because unique_id formats didn't match:

- **Cloud API:** `{entry_id}_kronoterm_{entity_key}`
- **Modbus (old):** `{entry_id}_kronoterm_modbus_{address}`

Example:
- Cloud: `xxx_kronoterm_heating_system_pressure`
- Modbus: `xxx_kronoterm_modbus_2325`

→ Home Assistant saw these as different entities → duplicates!

## Affected Entities

The following entity types were creating duplicates:

1. **Switches** (all 5-6 switches)
   - heatpump_switch
   - fast_heating_switch
   - additional_source_switch
   - reserve_source_switch
   - antilegionella_switch

2. **Sensors** (all Modbus sensors)
   - heating_energy_heating_dhw
   - heating_system_pressure
   - temperature_outside
   - hp_inlet_temperature
   - hp_outlet_temperature
   - operating_hours_*
   - COP/SCOP
   - All temperature sensors

3. **Climate entities** ✅ Already correct (no fix needed)

## Solution Applied

Changed Modbus unique_id format to match Cloud API:

### Before (Modbus):
```python
# Sensors
self._unique_id = f"{entry_id}_kronoterm_modbus_{address}"  # e.g., xxx_kronoterm_modbus_2325

# Switches  
self._unique_id = f"{entry_id}_kronoterm_modbus_{address}"  # e.g., xxx_kronoterm_modbus_2012
```

### After (Modbus):
```python
# Sensors
self._unique_id = f"{entry_id}_kronoterm_{name_en}"  # e.g., xxx_kronoterm_heating_system_pressure

# Switches
self._unique_id = f"{entry_id}_kronoterm_{translation_key}"  # e.g., xxx_kronoterm_heatpump_switch
```

## Testing Required

**You MUST test a full reconfigure cycle:**

1. **Backup your HA config** (just in case)

2. **Current state:** Integration running in Modbus mode

3. **Reconfigure to Cloud:**
   - Settings → Devices & Services → Kronoterm
   - Click **Reconfigure**
   - Select **Cloud API** mode
   - Enter credentials

4. **Check for duplicates:** Look for entities like:
   - ❌ `switch.kronoterm_heatpump_switch` (2 copies?)
   - ❌ `sensor.kronoterm_heating_system_pressure` (2 copies?)
   - ❌ `sensor.kronoterm_operating_hours_compressor_heating` (2 copies?)

5. **Reconfigure back to Modbus:**
   - Repeat reconfigure process
   - Select **Modbus TCP** mode
   - Enter Modbus settings

6. **Final check:** All entities should exist **only once**

## Expected Results

✅ **After fix:**
- Cloud → Modbus reconfigure: NO duplicates
- Modbus → Cloud reconfigure: NO duplicates
- Entity IDs remain the same across modes
- History preserved (same entity = same history)

❌ **Before fix:**
- Cloud → Modbus: 20+ duplicate entities
- User had to manually delete old entities
- Lost history on reconfigure

## Breaking Change Notice

**For existing Modbus users:**

Your entity unique_ids **WILL CHANGE** after updating to v1.5.0. This means:

- ❌ Old entities become "unavailable"
- ✅ New entities appear with correct unique_ids
- ❌ Dashboards/automations need updating
- ❌ History NOT migrated (separate entity IDs)

**Mitigation:**
- This is a **one-time** breaking change
- After v1.5.0, reconfigure will work seamlessly
- Document in BREAKING_CHANGES.md

## Files Modified

1. `custom_components/kronoterm/sensor.py`
   - Changed `KronotermModbusRegSensor` unique_id format
   - Changed `KronotermEnumSensor` unique_id format

2. `custom_components/kronoterm/switch.py`
   - Changed `KronotermModbusSwitch` unique_id format

3. `custom_components/kronoterm/kronoterm.json`
   - Register name unification (already done)

## Verification Commands

Check unique_id format in HA:

```bash
# Via HA API
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8123/api/states | grep kronoterm | head -10

# Via entity registry
cat ~/.homeassistant/.storage/core.entity_registry | grep kronoterm | head -10
```

Expected format: `xxx_kronoterm_heating_system_pressure` (not `xxx_kronoterm_modbus_2325`)

---

**Status:** ✅ Code fixed, pending user testing
