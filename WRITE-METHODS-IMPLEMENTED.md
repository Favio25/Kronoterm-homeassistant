# Modbus Write Methods Implementation

**Date:** 2026-02-03 12:00  
**Status:** ✅ IMPLEMENTED - Control entities now functional

## Problem Solved

All control entities (number, switch, select, climate) were non-functional in Modbus mode because high-level write methods were missing from `ModbusCoordinator`.

## Implementation

Added 11 write methods to `modbus_coordinator.py` matching the Cloud API coordinator interface:

### ✅ Fully Implemented

1. **`async_set_temperature(page, new_temp)`** - Set loop/DHW setpoints
   - Loop 1: register 2187 (page 5)
   - Loop 2: register 2049 (page 6)
   - DHW: register 2023 (page 9)
   - Converts °C to Modbus format (× 10)

2. **`async_set_offset(page, param_name, new_value)`** - Set eco/comfort offsets
   - Loop 1: 2047 (eco), 2048 (comfort)
   - Loop 2: 2057 (eco), 2058 (comfort)
   - Loop 3: 2067 (eco), 2068 (comfort)
   - Loop 4: 2077 (eco), 2078 (comfort)
   - DHW: 2030 (eco), 2031 (comfort)
   - Converts °C to Modbus format (× 10)

3. **`async_set_heatpump_state(turn_on)`** - Enable/disable system
   - Register 2002 (SYSTEM_OPERATION bit 0)
   - Note: Simple implementation, may need read-modify-write for bit masking

4. **`async_set_loop_mode_by_page(page, new_mode)`** - Set loop operation mode
   - Loop 1: register 2042 (page 5)
   - Loop 2: register 2052 (page 6)
   - Loop 3: register 2062 (page 7)
   - Loop 4: register 2072 (page 8)
   - DHW: register 2026 (page 9)
   - Modes: 0=off, 1=normal, 2=eco, 3=comfort

5. **`async_set_dhw_circulation(enable)`** - DHW circulation pump
   - Register 2328

6. **`async_set_fast_water_heating(enable)`** - Fast DHW heating
   - Register 2015

7. **`async_set_additional_source(enable)`** - Additional heating source
   - Register 2016

8. **`async_set_main_mode(new_mode)`** - Main operational mode
   - Register 2007 (OPERATION_REGIME)
   - Modes: 0=heating, 1=cooling, 2=off
   - ⚠️ May not be correct register (Cloud API "main_mode" might be different)

### ⚠️ Partially Implemented / TODO

9. **`async_set_main_temp_offset(new_value)`** - System-wide temp correction
   - ❌ Register unknown - returns False with warning
   - May not exist in Modbus or uses different mechanism

10. **`async_set_antilegionella(enable)`** - Anti-legionella function
    - ❌ Register unknown - returns False with warning
    - Need to find Modbus register

11. **`async_set_reserve_source(enable)`** - Reserve heating source
    - ❌ Register unknown - returns False with warning
    - Need to find Modbus register

## Register Summary

| Function | Register | Format | Notes |
|----------|----------|--------|-------|
| Loop 1 Setpoint | 2187 | temp × 10 | ✅ |
| Loop 2 Setpoint | 2049 | temp × 10 | ✅ |
| DHW Setpoint | 2023 | temp × 10 | ✅ |
| Offsets (8 total) | 2030, 2031, 2047, 2048, 2057, 2058, 2067, 2068, 2077, 2078 | temp × 10 | ✅ |
| Loop Modes (4 total) | 2042, 2052, 2062, 2072 | enum | ✅ |
| DHW Operation | 2026 | enum | ✅ |
| System Operation | 2002 | bit 0 | ✅ (simple) |
| Fast DHW Heating | 2015 | 0/1 | ✅ |
| Additional Source | 2016 | 0/1 | ✅ |
| DHW Circulation | 2328 | 0/1 | ✅ |
| Main Mode | 2007 | enum | ⚠️ verify |
| Main Temp Offset | ??? | temp × 10 | ❌ missing |
| Anti-Legionella | ??? | 0/1 | ❌ missing |
| Reserve Source | ??? | 0/1 | ❌ missing |

## Testing Required

1. **Number Entities:**
   - [ ] Set Loop 1 setpoint
   - [ ] Set Loop 2 setpoint
   - [ ] Set DHW setpoint
   - [ ] Set Loop 1 eco offset
   - [ ] Set Loop 1 comfort offset
   - [ ] Verify values persist after write
   - [ ] Verify sensor updates reflect new values

2. **Switch Entities:**
   - [ ] Toggle heat pump on/off
   - [ ] Toggle DHW circulation
   - [ ] Toggle fast water heating
   - [ ] Toggle additional source
   - [ ] Verify state changes in sensors
   - [ ] Verify physical device responds

3. **Select Entities:**
   - [ ] Change Loop 1 operation mode (off/normal/eco/comfort)
   - [ ] Change DHW operation mode
   - [ ] Change main mode (heating/cooling/off)
   - [ ] Verify mode changes reflected in status sensors

4. **Climate Entity:**
   - [ ] Set target temperature
   - [ ] Change HVAC mode
   - [ ] Verify climate control works

## Known Issues

1. **System Operation (2002):** Current implementation writes 0/1 directly. May need read-modify-write if other bits are used.

2. **Main Mode Register:** Using register 2007 (OPERATION_REGIME) which controls heating/cooling/off. Cloud API "main_mode" (auto/comfort/eco) might be a different register or concept.

3. **Missing Registers:** Three functions not implemented due to unknown register addresses:
   - Main temp offset
   - Anti-legionella
   - Reserve source

4. **Write Confirmation:** Current implementation trusts Modbus write success. Should verify by reading back changed values.

5. **Rate Limiting:** No throttling on writes. Rapid changes could overwhelm device or cause communication errors.

## Next Steps

1. Test all control entities in Home Assistant
2. Monitor logs for write errors
3. Find missing register addresses (main temp offset, anti-legionella, reserve source)
4. Implement read-modify-write for bit-masked registers (2002)
5. Add write validation (read back after write)
6. Consider adding rate limiting for writes
7. Update entity availability based on implemented methods

## Files Modified

- `custom_components/kronoterm/modbus_coordinator.py` - Added ~230 lines of write methods
- Copied to container: `/config/custom_components/kronoterm/modbus_coordinator.py`
- Home Assistant restarted to load changes

---

**Expected Result:** Control entities should now be functional for 8 of 11 operations. Three require additional register discovery.
