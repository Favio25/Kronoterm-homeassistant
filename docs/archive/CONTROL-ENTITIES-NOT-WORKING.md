# Control Entities Not Working - Root Cause Analysis

**Date:** 2026-02-03 11:58  
**Status:** ⚠️ CRITICAL - All control entities non-functional in Modbus mode

## Problem

Number, switch, select, and climate entities are non-functional in Modbus TCP mode:
- Number entities (temperature setpoints, offsets)
- Switch entities (DHW circulation, fast heating, additional source)
- Select entities (operation mode, loop modes)
- Climate entities (HVAC control)

All read operations work correctly (35/39 registers successful), but **write operations fail silently**.

## Root Cause

Control entities call write methods that exist in `KronotermCoordinator` (Cloud API) but are **NOT implemented** in `ModbusCoordinator`:

### Missing Methods in ModbusCoordinator

```python
# From coordinator.py (Cloud API) - ALL MISSING IN MODBUS:
async def async_set_temperature(page, new_temp) -> bool
async def async_set_offset(page, param_name, new_value) -> bool
async def async_set_heatpump_state(turn_on) -> bool
async def async_set_loop_mode_by_page(page, new_mode) -> bool
async def async_set_main_temp_offset(new_value) -> bool
async def async_set_antilegionella(enable) -> bool
async def async_set_dhw_circulation(enable) -> bool
async def async_set_fast_water_heating(enable) -> bool
async def async_set_reserve_source(enable) -> bool
async def async_set_additional_source(enable) -> bool
async def async_set_main_mode(new_mode) -> bool
```

### Low-Level Write Method EXISTS

```python
# modbus_coordinator.py line ~295
async def write_register(register: Register, value: int) -> bool
```

This method works correctly but entities call the **high-level methods** listed above.

## Evidence

```python
# number.py line 109:
success = await self.coordinator.async_set_offset(
    page=self._page,
    param_name=self._param_name,
    new_value=new_offset,
)
```

When Modbus coordinator is active, this method **doesn't exist** → entities fail silently.

## Required Fix

Implement all high-level write methods in `ModbusCoordinator` that:

1. **Map Cloud API "page" logic to Modbus registers**
2. **Convert values to correct format** (temperature × 10, bool → 0/1, etc.)
3. **Call existing `write_register()` method**
4. **Return success/failure**

### Register Mappings Needed

```python
# Temperature setpoints (scale × 10)
LOOP1_SETPOINT = 2187  # page 5
LOOP2_SETPOINT = 2049  # page 6
DHW_SETPOINT = 2023    # page 9

# Offsets (scale × 10) - per loop/DHW
# Loop 1: eco=2047, comfort=2048  (page 5)
# Loop 2: eco=2057, comfort=2058  (page 6)
# DHW: eco=2030, comfort=2031     (page 9)

# Switches (0/1)
FAST_DHW_HEATING = ???
DHW_CIRCULATION = ???
ADDITIONAL_SOURCE = ???
SYSTEM_OPERATION = 2002 (bit 0)

# Modes (enum values)
OPERATION_MODE = ???  # heating/cooling/off
LOOP_MODE = ???       # normal/eco/comfort
```

## Impact

**Current:**
- ✅ All sensors work (temperature, status, power, etc.)
- ❌ All controls broken (can't change setpoints, modes, enable/disable features)
- ❌ Integration is READ-ONLY

**After Fix:**
- ✅ Full feature parity with Cloud API
- ✅ Local control without cloud dependency
- ✅ Dual-mode support (users choose Cloud or Modbus)

## Next Steps

1. Document complete Modbus register map for writable registers
2. Implement all 11 async_set_* methods in ModbusCoordinator
3. Test each control entity type:
   - Number (setpoints, offsets)
   - Switch (circulation, fast heating)
   - Select (modes)
   - Climate (HVAC)
4. Verify writes persist and values update correctly

## Files to Modify

- `custom_components/kronoterm/modbus_coordinator.py` - add 11 methods (~200 lines)
- `custom_components/kronoterm/modbus_registers.py` - document writable registers
- Test with: `number.py`, `switch.py`, `select.py`, `climate.py`

---

**Priority:** HIGH - Integration is 50% complete without this fix.
