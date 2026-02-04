# Register Mapping Conflicts - Critical Analysis

## Problem: Multiple Components Using Same Registers for Different Purposes

### Conflict #1: Register 2047 (Loop 1)

**Official Docs:** `krog1_temp` - Loop 1 Current Temperature (READ-ONLY, scale 0.1)

**Current Usage:**
- `sensor.py` / `const.py`: Loop 1 Temperature sensor (after my "fix")
- `number.py`: Loop 1 ECO Offset control (range -10 to 0°C)

**Actual Device Value:** raw=0 → 0.0°C

**Conclusion:** ❌ WRONG - Either:
1. Register 2047 is temperature (sensor correct, number wrong)
2. Register 2047 is offset (number correct, sensor wrong)  
3. Both are wrong and need different registers

**Most Likely:** Official docs say it's TEMPERATURE, so number.py should NOT use it for offset

---

### Conflict #2: Register 2048 (Loop 1 Offset)

**Official Docs:** `krog1_offset` - Loop 1 Offset (READ/WRITE, scale 0.1)

**Current Usage:**
- `number.py`: Loop 1 COMFORT Offset control (range 0 to +10°C)

**Actual Device Value:** raw=230 → 23.0°C

**Problem:** 23°C is way too high for an offset! Offsets should be ±10°C max.

**Conclusion:** ❌ SUSPICIOUS - Either:
1. Wrong scale (should be 0.01 not 0.1?)
2. Wrong register entirely  
3. Device value is corrupted/error

---

### Conflict #3: Register 2030 (DHW)

**Official Docs:** `sanitarna_temp2` - DHW Temperature 2 (READ-ONLY, scale 0.1)

**Current Usage:**
- `number.py`: DHW ECO Offset control (range -10 to 0°C)

**Actual Device Value:** raw=0 → 0.0°C

**Conclusion:** ❌ WRONG - Official docs say READ-ONLY temperature, but number.py uses it for WRITE offset

---

### Conflict #4: Register 2031 (DHW Offset)

**Official Docs:** `sanitarna_offset` - DHW Offset (READ/WRITE, scale 0.1)

**Current Usage:**
- `number.py`: DHW COMFORT Offset control (range 0 to +10°C)

**Actual Device Value:** raw=501 → 50.1°C

**Problem:** 50.1°C is way too high for an offset!

**Conclusion:** ❌ WRONG - Same as 2048, value doesn't make sense

---

## Pattern Detection

Looking at all the "offset" registers showing huge values:
- 2031 (DHW offset): 50.1°C
- 2048 (Loop 1 offset): 23.0°C  
- 2058 (Loop 2 offset): 19.9°C
- 2068 (Loop 3 offset): 19.9°C
- 2078 (Loop 4 offset): 23.0°C

**Theory:** These might not be offsets at all - they might be SETPOINT temperatures!

If 2048 = 23.0°C setpoint (room temp), that makes perfect sense!
If 2031 = 50.1°C setpoint (DHW tank), that also makes sense!

**Hypothesis:** The "offset" registers in the official docs might actually be SETPOINT registers,
or the official naming is confusing what they actually represent.

---

## Loop 1 Temperature - Where Is It?

**Tried:**
- 2109: Official = pool temp → Wrong, shows unavailable
- 2047: Official = loop 1 temp → Shows 0.0°C (error or conflict with number entity)
- 2128: Official = another loop 1 register → Shows 0.0°C

**From original discovery (before official docs):**
- Register 546 was documented as "Supply Temperature" showing ~38°C

**Problem:** Register 546 was never added to modbus_registers.py - it was manual discovery only

---

## Working Function (Register 2001)

**Expected:** Enum with values 0-5 (heating, dhw, cooling, etc.)

**Actual:** raw=8193 (0x2001 in hex = binary 0010 0000 0000 0001)

**Conclusion:** This is a BITFIELD, not a simple enum!

**Fix Needed:** Change from RegisterType.ENUM to RegisterType.BITS and create multiple binary sensors

---

## Next Steps

1. **URGENT:** Separate temperature sensors from offset controls
   - Find correct registers for Loop 1-4 temperatures (might be in 500-range like 546)
   - Fix number.py to not conflict with sensor.py

2. **Verify Offsets:** Check if "offset" registers are actually setpoints
   - Test writing to 2048 and see if it changes Loop 1 target temp
   - Compare with Cloud API JSON to see what these values represent

3. **Add 500-range sensor registers:**
   - 546: Supply Temperature (from original discovery)
   - Others from original scan that were never coded

4. **Fix Working Function:** Convert to bitfield

5. **Add Operation Regime:** Register 2007 to ALL_REGISTERS
