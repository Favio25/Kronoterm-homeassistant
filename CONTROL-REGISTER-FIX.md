# Control Register Filter Fix

## Problem
Control registers (type="Control", access="Read/Write") were being created as **both sensors AND switches**, causing duplicate entities.

Example:
- Register 2000: "System Operation" (read-only status) → Sensor
- Register 2012: "System On" (read/write control) → **Both sensor AND switch** ❌

Result: User sees confusing duplicate entities.

## Root Cause
The sensor.py `_should_create_sensor()` function didn't filter out writable Control registers.

## Solution
Added two filters in `sensor.py`:

1. **Skip all writable Control registers:**
   ```python
   if reg_def.type == "Control" and reg_def.access == "Read/Write":
       return False
   ```

2. **Skip redundant status register 2000:**
   ```python
   if reg_def.address == 2000:  # system_operation
       return False
   ```

## Impact
**Before:**
- 25 writable Control registers created as sensors
- Register 2000 created as sensor (redundant with switch at 2012)
- Confusing duplicate entities

**After:**
- ✅ Writable Control registers only created as switches/selects
- ✅ No duplicate system ON/OFF entities
- ✅ Cleaner entity list

## Affected Registers
All writable Control registers now correctly skip sensor creation:
- 2012: system_on (switch only)
- 2013: operation_program_select (select)
- 2015: dhw_quick_heating_enable (switch)
- 2016: additional_source_enable (switch)
- 2017: mode_switch (select)
- 2018: reserve_source_enable (switch)
- 2022: vacation_mode (switch)
- 2026: dhw_operation_mode (select)
- 2035: reservoir_operation_mode (select)
- 2042-2072: loop operation modes (select)
- 2081: pool_operation_mode (select)
- 2301: thermal_disinfection (switch)
- 2307: screed_drying (switch)
- 2320-2323: adaptive curve switches
- 2324: system_filling (switch)

## Status
✅ **Fixed** - Users restart Home Assistant to see clean entity list.

## Note
After applying this fix, users should:
1. Restart Home Assistant
2. Old sensor entities will show as "unavailable"
3. Remove old sensor entities from UI
4. Use the switch entities instead
