# Control Entities Issue - Summary for User

**Date:** 2026-02-03 12:15  
**Status:** 🔍 INVESTIGATING - Added debug logging to diagnose platform loading

## Problem

Control entities (number, switch, select, climate) are **not working** in the Modbus TCP integration:
- Number entities (setpoints, offsets)
- Switch entities (circulation, fast heating, etc.)
- Select entities (operation modes)
- Climate entity (HVAC control)

## What We Did

### 1. Implemented Write Methods ✅
Added 11 async_set_* methods to ModbusCoordinator:
- Temperature setpoints (Loop 1/2, DHW)
- Temperature offsets (eco/comfort)
- Switches (circulation, fast heating, additional source)
- Modes (loop modes, operation regime)
- System on/off

**Result:** Write methods exist and should work IF entities load.

### 2. Diagnosed Platform Loading Issue ⏳
Investigation shows:
- ✅ Sensor and binary_sensor platforms load successfully
- ❌ Number, switch, select, climate platforms **do not appear in logs at all**
- ❌ No error messages, no "Setting up" messages
- Platforms are failing silently during initialization

### 3. Added Debug Logging 🔍
Modified platform files to add explicit logging:
```python
_LOGGER.warning("🔥 PLATFORM SETUP - Coordinator type: %s", type(coordinator).__name__)
```

Added to:
- custom_components/kronoterm/number.py
- custom_components/kronoterm/switch.py  
- custom_components/kronoterm/select.py

**Currently:** Waiting for HA to restart with debug logging enabled to see:
1. Are platform setup functions being called?
2. Is coordinator recognized?
3. Where exactly is the failure happening?

## Possible Root Causes

### Theory A: Data Structure Mismatch
Control entity platforms expect Cloud API JSON structure:
```json
{
  "main_settings": {...},
  "shortcuts": {...}
}
```

But Modbus coordinator provides:
```json
{
  "main": {
    "ModbusReg": [...]
  }
}
```

Some entities (like KronotermMainOffsetNumber) try to read from `main_settings` which doesn't exist for Modbus, causing setup to fail.

### Theory B: Entity Registry Conflicts
- Old Cloud API entities exist in registry with conflicting unique_ids
- New Modbus entities can't be created due to ID conflicts
- Energy sensors showing duplicate ID errors support this theory

### Theory C: Missing Coordinator Methods
- Platforms check if coordinator has certain methods
- Modbus coordinator missing some methods that Cloud coordinator has
- Setup silently aborts when method checks fail

## Next Actions

1. **Wait for debug logs** (40 seconds from now)
2. **Analyze which theory is correct**
3. **Apply targeted fix:**
   - If Theory A: Conditionally skip Cloud API entities for Modbus
   - If Theory B: Clear entity registry or change unique_ids
   - If Theory C: Implement missing methods/properties

## Expected Timeline

- **Now + 1 min:** Debug logs available, root cause identified
- **Now + 5 min:** Fix applied, HA restarted
- **Now + 10 min:** Control entities working

## User Action Required

After next restart, please check:
1. Do you see number/switch/select entities in Home Assistant UI?
2. Can you click on a setpoint and try to change it?
3. What happens when you try?

This will confirm if the fix worked.
