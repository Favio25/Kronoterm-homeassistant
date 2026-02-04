# ROOT CAUSE IDENTIFIED

**Date:** 2026-02-03 12:18  
**Status:** 🎯 FOUND - Dual Integration Conflict

## The Problem

**You have BOTH Kronoterm integrations running simultaneously:**

1. **Cloud API** - Enabled, active
2. **Modbus TCP** - Enabled, active

Home Assistant is loading BOTH coordinators, but:
- Only ONE coordinator can be stored in `hass.data[DOMAIN]["coordinator"]`
- The LAST one to load wins (overwrites the first)
- Entity platforms check this single coordinator slot
- This causes unpredictable behavior

## Evidence

```python
# From core.config_entries:
Entry 0: "Kronoterm Heat Pump (Cloud)", disabled=None
Entry 1: "Kronoterm ADAPT 0416 (Modbus)", disabled=None
```

Both are active!

## Why Control Entities Don't Work

1. **Modbus coordinator loads second** (overwrites Cloud in hass.data)
2. **Sensor platforms work** because they create entities from Modbus data
3. **Control platforms fail** because:
   - They were designed for Cloud API data structure
   - They expect `main_settings`, `shortcuts` keys
   - Modbus only provides `main.ModbusReg`
   - Setup silently fails when data structure doesn't match

## The Fix

**DISABLE the Cloud API integration** so only Modbus runs:

1. Go to Settings → Devices & Services
2. Find "Kronoterm Heat Pump (Cloud)"  
3. Click the 3 dots → Disable
4. Keep only "Kronoterm ADAPT 0416 (Modbus)" enabled

OR programmatically:

```python
# Update core.config_entries to set disabled_by="user" for Cloud entry
```

## Why This Happened

When testing the Modbus integration, you added it as a NEW integration instead of:
- Removing the old Cloud integration first, OR
- Modifying the existing integration to switch modes

Home Assistant allowed both to run simultaneously, creating a conflict.

## Expected After Fix

Once Cloud integration is disabled:
- ✅ Only Modbus coordinator active
- ✅ Sensors continue to work
- ✅ Control entities should appear (if their data checks pass)
- ✅ Write methods will work

## Additional Issue to Address

Even after disabling Cloud, control entity platforms might still fail because they're checking for Cloud API data structure. May need to:

1. **Modify entity setup logic** to conditionally check coordinator type
2. **Skip Cloud-only entities** when Modbus is active
3. **Or adapt entities** to work with both data structures

This is why the debug logs showed NO platform setup messages - Home Assistant might be aborting platform forwarding when it detects the conflict.
