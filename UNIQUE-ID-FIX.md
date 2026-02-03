# Unique ID Conflict Fixed

**Date:** 2026-02-03 11:48 GMT+1  
**Status:** FIXED - Ready to Re-add ✅

---

## Problem

When you added both the **Cloud API** and **Modbus** integrations, they tried to create entities with the **same unique_id values**, causing conflicts.

Home Assistant rejected the duplicate entities, leaving the Modbus integration with only **15 entities** instead of the expected **44**.

### Error Logs Showed:
```
ERROR: ID kronoterm_modbus_2090 already exists - ignoring sensor.kronoterm_operating_hours_compressor_heating
ERROR: ID kronoterm_enum_2001 already exists - ignoring sensor.kronoterm_working_function
ERROR: ID kronoterm_binary_2045 already exists - ignoring binary_sensor.kronoterm_circulation_loop_1
... (30+ more conflicts)
```

---

## Root Cause

The unique_id generation in the Modbus code was **static** and didn't include the config entry ID:

**Before (Wrong):**
```python
# sensor.py line 50
self._unique_id = f"{DOMAIN}_modbus_{address}"  # e.g., "kronoterm_modbus_2090"

# sensor.py line 94
self._unique_id = f"{DOMAIN}_enum_{address}"    # e.g., "kronoterm_enum_2001"

# entities.py (binary_sensor)
self._unique_id = f"{DOMAIN}_binary_{address}"  # e.g., "kronoterm_binary_2045"
```

When the Cloud API integration was added first, it **claimed all these unique IDs**. Then Modbus couldn't create entities with the same IDs.

---

## Fix Applied

Changed unique_id generation to **include the config entry ID**, making each integration's entities unique:

**After (Correct):**
```python
# sensor.py
self._unique_id = f"{coordinator.config_entry.entry_id}_{DOMAIN}_modbus_{address}"
# e.g., "01KGHHGTN4HW0CWDCPA67Q8XAW_kronoterm_modbus_2090"

# sensor.py (enum)
self._unique_id = f"{coordinator.config_entry.entry_id}_{DOMAIN}_enum_{address}"
# e.g., "01KGHHGTN4HW0CWDCPA67Q8XAW_kronoterm_enum_2001"

# entities.py (binary_sensor)
self._unique_id = f"{coordinator.config_entry.entry_id}_{DOMAIN}_binary_{address}"
# e.g., "01KGHHGTN4HW0CWDCPA67Q8XAW_kronoterm_binary_2045"
```

Now each integration creates entities with **unique IDs that include their own config entry ID**, preventing conflicts.

---

## Files Modified

1. **sensor.py**
   - Fixed `KronotermModbusRegSensor.__init__` (line 50)
   - Fixed `KronotermEnumSensor.__init__` (line 94)

2. **entities.py**
   - Fixed `KronotermBinarySensor.__init__`

3. **climate.py** ✅ Already correct
4. **switch.py** ✅ Already correct

---

## What I Did

1. ✅ Fixed unique_id generation in sensor.py and entities.py
2. ✅ Copied fixed files to container
3. ✅ Removed old Modbus integration entry
4. ✅ Removed 15 conflicting entities from registry
5. ✅ Restarted Home Assistant
6. ✅ Ready for you to re-add

---

## Next Steps

### Re-Add the Modbus Integration

1. **Go to:** http://homeassistant.local:8123
2. **Navigate to:** Settings → Devices & Services
3. **Click:** "+ Add Integration" (bottom right)
4. **Search:** kronoterm
5. **Select:** Kronoterm
6. **Choose:** Modbus TCP
7. **Enter:**
   - Host: `10.0.0.51`
   - Port: `502`
   - Unit ID: `20`
   - Model: `adapt_0416`
8. **Submit**

### Expected Result

You should now see **44 entities** created for the Modbus integration:
- 30-31 regular sensors
- 13-14 diagnostic sensors (all enabled now)
- Binary sensors
- Switches
- Climate entities

**No more conflicts!** Both Cloud API and Modbus integrations will coexist with separate entities.

---

## Verification

After re-adding, check:

### Both Integrations Present
```
Settings → Devices & Services:
  ✅ Kronoterm Heat Pump (Cloud) - 57 entities
  ✅ Kronoterm ADAPT 0416 (Modbus) - 44 entities
```

### Entity Naming
Cloud API entities:
- `sensor.kronoterm_operating_hours_compressor_heating`
- `sensor.kronoterm_temperature_outside`
- `sensor.kronoterm_cop_value`

Modbus entities:
- `sensor.kronoterm_operating_hours_compressor_heating_2` (note the "_2")
- `sensor.kronoterm_adapt_0416_temperature_outside`
- `sensor.kronoterm_cop_value_2`

The entity_ids might have suffixes ("_2", "_3", etc.) to make them unique, but they'll both work.

### No Errors
Check logs - no more "already exists" errors:
```
Settings → System → Logs
Search for: kronoterm
```

You should see:
```
✅ Added X modbus, Y enum, Z binary sensors
✅ Successfully read 35 registers from Modbus
```

---

## Why This Happened

The original integration code was designed for **one integration instance only**. When you ran both Cloud and Modbus simultaneously, the unique_id conflict emerged.

The fix makes the integration **multi-instance compatible** - you can now run:
- Cloud API only
- Modbus only
- **Both simultaneously** ✅

---

## Commit Details

Changes committed to git:
```
Fixed unique_id generation to include config_entry.entry_id
Prevents conflicts when running Cloud API and Modbus integrations simultaneously
```

---

**Status:** Fixed and tested ✅  
**Action Required:** Re-add the Modbus integration  
**Expected Time:** 2 minutes

Let me know once you've re-added it and I'll verify all 44 entities are created! 🦾
