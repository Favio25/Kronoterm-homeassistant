# Control Entities Not Working - Diagnosis

**Date:** 2026-02-03 12:12  
**Issue:** Control entities (number/switch/select/climate) not loading for Modbus TCP integration

## Evidence

### 1. Log Analysis
```
12:05:32 - Modbus coordinator initialized successfully
12:05:32 - Data read: 34/38 registers
12:05:34 - Sensor platform loaded (with duplicate ID errors for energy sensors)
12:05:34 - Binary sensor platform loaded (with duplicate ID errors)
NO MENTION OF: number, switch, select, or climate platforms
```

### 2. Platform Status
- ✅ __init__.py declares PLATFORMS = ["sensor", "binary_sensor", "switch", "climate", "select", "number"]
- ✅ Files exist in container: number.py, switch.py, select.py, climate.py (all dated Feb 2 21:38)
- ❌ NO log messages about these platforms being set up
- ❌ NO error messages about failures during setup

### 3. Recent Errors (from Feb 2 logs, not current)
```
climate.py: 'ModbusCoordinator' object has no attribute 'loop3_installed'
climate.py: 'ModbusCoordinator' object has no attribute 'reservoir_installed'
```
These attributes EXIST in current modbus_coordinator.py (lines 84-86), suggesting old errors from before fixes.

### 4. Feature Flags in ModbusCoordinator
```python
# Line 78-86 in modbus_coordinator.py
self.loop1_installed = True
self.loop2_installed = False
self.loop3_installed = False  # ✅ EXISTS
self.loop4_installed = False
self.dhw_installed = True
self.tap_water_installed = True
self.additional_source_installed = False
self.alt_source_installed = False
self.reservoir_installed = False  # ✅ EXISTS
self.pool_installed = False
```

## Theories

### Theory 1: Silent Setup Failures
Platforms are attempting to load but failing silently during `async_setup_entry()`. Possible causes:
- Entity creation raises exception that HA catches and logs only to DEBUG level
- Data format mismatch between Cloud API expectations and Modbus reality
- Missing methods or attributes during entity initialization

### Theory 2: Entity Registry Conflicts
Entity registry has cached entries from previous Cloud API setup that conflict with new Modbus entities:
- Same entity_id but different unique_id
- Registry prevents new entities from being created
- Energy sensor duplicate ID errors suggest this is happening

### Theory 3: Data Structure Incompatibility
Entity setup code checks coordinator.data structure and fails validation:
```python
# number.py line 243
modbus_list = (coordinator.data or {}).get("main", {}).get("ModbusReg", [])
```

Modbus data structure:
```json
{
  "main": {
    "ModbusReg": [...]
  }
}
```

Cloud API data structure:
```json
{
  "main_settings": {...},
  "shortcuts": {...},
  ...
}
```

Entities designed for Cloud API (like `KronotermMainOffsetNumber`) expect `main_settings` which doesn't exist in Modbus data, causing setup to fail.

### Theory 4: Platform Not Forwarded
`async_forward_entry_setups()` only forwards platforms that pass some internal validation. Modbus coordinator might not be passing this validation for control platforms.

## Next Steps

1. **Enable DEBUG logging** for custom_components.kronoterm to see actual setup errors
2. **Check entity registry** for conflicting entries
3. **Add logging** to platform setup functions to trace execution
4. **Test individual platform** setup by temporarily removing others from PLATFORMS list
5. **Compare coordinator types** - check if entities are checking coordinator type and skipping Modbus

## Immediate Action

Add debug logging statements to async_setup_entry in each platform file to determine if they're even being called.

```python
# Add to top of async_setup_entry in number.py, switch.py, select.py, climate.py
_LOGGER.warning("🔥 PLATFORM SETUP CALLED - coordinator type: %s", type(coordinator).__name__)
```

This will definitively show:
- Are platforms being called at all?
- Is coordinator the right type?
- Where exactly is the failure happening?
