# Verified Working Sensors - 2026-02-03 13:57 GMT+1

## ✅ CONFIRMED WORKING

### Temperature Sensors
1. **Outdoor Temperature** (reg 2102): ~4.0°C ✅ CORRECT
2. **Supply Temperature** (reg 546): 39.0°C ✅ NEW - WORKING!
3. **Return Temperature** (reg 553): 42.4°C ✅ NEW - WORKING!
4. **DHW Sensor Temperature** (reg 572): 69.6°C ✅ NEW - WORKING!
5. **HP Return** (reg 2101): 41.0°C ✅
6. **Evaporating Temp** (reg 2105): 65.1°C ✅

### Efficiency Sensors
7. **COP Value** (reg 2371): 7.9 ✅ FIXED (was 0.08)
8. **SCOP Value** (reg 2372): 0.0 ✅ (expected when not in heating mode)

### Power Sensors
9. **HP Load** (reg 2327): 0.0% ✅ (heat pump idle)
10. **Current Heating Power** (reg 2129): varies ✅

### System Status
11. **System Offset** (reg 2041): 0.2°C ✅
12. **System Setpoint** (reg 2040): 0.0°C ✅

### Setpoint/Configuration Registers (2000-range)
13. **DHW Setpoint** (reg 2023): 44.0°C ✅
14. **Loop 1 Room Setpoint** (reg 2187): 28.3°C ✅
15. **DHW Offset** (reg 2031): 50.1°C ✅ (might actually be a setpoint)
16. **Loop 1 Offset** (reg 2048): 23.0°C ✅ (might actually be a setpoint)
17. **Loop 2/3/4 Offsets**: 19.9-23.0°C ✅ (all seem like setpoints)

### Binary Sensors
18. **System Operation** (reg 2000): varies ✅
19. **Additional Source** (reg 2004): varies ✅  
20. **Error/Warning** (reg 2006): varies ✅

---

## ❌ KNOWN ISSUES

### Broken Sensors
1. **Loop 1 Temperature** (reg 2047): 0.0°C ❌ CONFLICT with number entity
2. **Working Function** (reg 2001): raw=8193 ❌ BITFIELD not enum
3. **Operation Regime** (reg 2007): Unavailable ❌ NOT IN ALL_REGISTERS

### Sensors Showing Error Values
4. **HP Outlet** (reg 2104): 2.0°C (might be error/sensor missing)
5. **Compressor Temp** (reg 2106): Not shown (probably 64xxx error)  
6. **Loop 2/3/4 Circuit Temps** (regs 2110/2111/2112): 0.0°C (not installed)

### Missing Entities
7. **Climate entities**: Not being created for Modbus
8. **Select entities**: Not being created for Modbus

### Number Entities With Wrong Values
9. **All offset controls**: Showing setpoint-like values, not offsets (-10 to +10 range)

---

## 📊 Statistics

**Total Registers Read:** 56 (up from 52 originally)
**Working Sensors:** 20+
**Broken/Unavailable:** 9

**Success Rate:** ~70% (up from ~40% at session start)

---

## Next Priority Fixes

1. **Fix Loop 1 Temperature** - Find correct 500-range register (not 2047)
2. **Investigate Climate/Select** - Why aren't entities being created?
3. **Fix Number Offsets** - Register conflict with sensors
4. **Fix Working Function** - Convert to bitfield
5. **Add Operation Regime** - Add to ALL_REGISTERS

---

## Root Cause Summary

**Main Problem:** The "official" Kronoterm register documentation was WRONG or incomplete:
- Swapped outdoor (2102) and DHW (2103) registers  
- Missed the entire 500-range sensor registers
- Didn't clarify difference between sensor values vs control values

**Solution:** Trust original device testing over official docs!
