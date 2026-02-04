# Multi-Instance Support Implementation

**Date:** 2026-02-03 12:22  
**Status:** ✅ IMPLEMENTED - Both Cloud and Modbus can now run simultaneously  
**Commit:** 5d9eda4

## What Was Wrong

The integration stored all coordinators in a single dictionary slot:
```python
hass.data[DOMAIN]["coordinator"] = coordinator  # ❌ Single slot
```

When both Cloud and Modbus were enabled:
1. Cloud loaded first → stored coordinator
2. Modbus loaded second → **overwrote** Cloud coordinator
3. Entity platforms only saw the last-loaded coordinator
4. Result: Unpredictable behavior, entities from one integration accessing data from another

## The Fix

Changed to use **unique keys per integration instance**:

```python
# Store coordinator using entry_id as unique key
hass.data[DOMAIN][entry.entry_id] = coordinator  # ✅ Multiple slots

# Retrieve coordinator for this specific entry
coordinator = hass.data[DOMAIN].get(entry.entry_id)
```

## Files Modified

1. **`__init__.py`** - Store/retrieve using entry_id
2. **`sensor.py`** - Look up by entry_id
3. **`binary_sensor.py`** - Look up by entry_id
4. **`number.py`** - Look up by entry_id
5. **`switch.py`** - Look up by entry_id
6. **`select.py`** - Look up by entry_id
7. **`climate.py`** - Look up by entry_id

## Expected Behavior After Fix

### ✅ Both Integrations Active
- Cloud API integration: Uses its own KronotermCoordinator
- Modbus TCP integration: Uses its own ModbusCoordinator
- No conflicts, no overwrites

### ✅ Separate Entity Sets
Each integration creates its own entities:
- `sensor.kronoterm_outdoor_temperature` (Cloud)
- `sensor.kronoterm_outdoor_temperature_2` (Modbus)

Or with distinct names based on integration title:
- `sensor.kronoterm_heat_pump_cloud_outdoor_temperature`
- `sensor.kronoterm_adapt_0416_modbus_outdoor_temperature`

### ✅ Independent Operation
- Cloud entities update from Cloud API
- Modbus entities update from Modbus TCP
- Control entities work for the coordinator they belong to
- No cross-contamination of data

## Benefits

1. **Comparison:** Compare Cloud vs Modbus values side-by-side
2. **Redundancy:** If one connection fails, the other continues working
3. **Testing:** Validate Modbus register mappings against Cloud API
4. **Migration:** Gradually migrate from Cloud to Modbus without downtime
5. **Flexibility:** Choose which source to use for automations

## Verification Steps

After HA restart, check:

1. **Developer Tools → States:**
   - Filter: `kronoterm`
   - Should see entities from BOTH integrations
   - Check entity attributes for `entry_id` or integration source

2. **Settings → Devices & Services:**
   - Should see 2 Kronoterm integrations
   - Each should show its own device/entities

3. **Logs (check for debug messages):**
   ```
   🔥 NUMBER PLATFORM SETUP - Coordinator type: KronotermCoordinator, Entry: <cloud_entry_id>
   🔥 NUMBER PLATFORM SETUP - Coordinator type: ModbusCoordinator, Entry: <modbus_entry_id>
   ```

4. **Test Control Entities:**
   - Try changing a setpoint on Modbus integration
   - Try changing a setpoint on Cloud integration
   - Both should work independently

## Current Status

- ✅ Code updated and committed
- ⏳ Home Assistant restarting (50 seconds)
- 📋 Next: Verify both integrations load successfully
- 📋 Check logs for platform setup messages
- 📋 Test control entity operations

## Potential Issues to Watch For

1. **Entity Name Conflicts:** If HA assigns the same entity_id to both, one will get a `_2` suffix
2. **Unique ID Conflicts:** Should be avoided since unique_ids include entry_id
3. **Control Entity Data Structure:** Modbus coordinator might still have issues with Cloud-specific entity classes (like Main Temp Offset)

If control entities still don't work for Modbus, the next step is to make entity setup logic conditional on coordinator type.

---

**Waiting for HA restart to complete...**
