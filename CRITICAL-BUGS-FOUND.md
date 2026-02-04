# Critical Bugs Found - 2026-02-03 13:42

## 🐛 Bug #1: Double-Scaling (FIXED)

**Problem:** Coordinator scales values, then sensor scales AGAIN

**Example:**
- COP raw value: 790
- Coordinator scales: 790 × 0.01 = 7.9 ✅
- Sensor scales again: 7.9 × 0.01 = **0.08** ❌

**Fix Applied:** Changed ALL sensor scaling factors in `const.py` from 0.1/0.01 to 1.0

**Status:** ✅ FIXED - Needs restart to verify

---

## 🐛 Bug #2: Wrong Register for Outdoor Temperature

**Problem:** Sensor uses register 2102 (DHW tank) instead of 2103 (outdoor)

**Official Docs:**
- 2102: `temp_sanitarna` (DHW tank temp)
- 2103: `temp_zunanja` (outdoor temp)

**Result:** Shows DHW temp (~48°C) instead of outdoor temp (~0.4°C)

**Fix Applied:** Changed register 2102 → 2103 in const.py

**Status:** ✅ FIXED - Needs restart to verify

---

## 🐛 Bug #3: Wrong Register for Loop 1 Temperature

**Problem:** Sensor uses register 2109 (pool temp) instead of 2047 (loop 1)

**Official Docs:**
- 2047: `krog1_temp` (Loop 1 temperature)
- 2109: `temp_bazen` (Pool temperature)

**Result:** Shows "Unavailable" (no pool installed)

**Fix Applied:** Changed register 2109 → 2047 in const.py

**Status:** ✅ FIXED - Needs restart to verify

---

## 🐛 Bug #4: Operation Regime Register Not Defined

**Problem:** const.py has EnumSensorDefinition for register 2007, but it's not in modbus_registers.py ALL_REGISTERS list

**Official Docs:** 2007 is marked as "unknown"

**Result:** Operation Regime shows "Unavailable"

**Possible Solutions:**
1. Remove the sensor from const.py (if register doesn't exist)
2. Add register definition and include in ALL_REGISTERS
3. Map to a different register (2008 Operation Program?)

**Status:** ⏳ PENDING DECISION

---

## 🐛 Bug #5: Working Function Shows Raw Value (33) Instead of Enum String

**Problem:** Register 2001 reads raw value 33, but enum only has values 0-5

**Expected:** Should show "heating", "dhw", "cooling", etc.
**Actual:** Shows "Unknown" or raw value 33

**Debug Output:** `Reg 2001 (Working Function): raw=33, scaled=33`

**Possible Causes:**
1. Register 2001 might be a bitfield, not a simple enum
2. Enum mapping is wrong
3. Different encoding than documented

**Status:** ⏳ NEEDS INVESTIGATION

---

## 🐛 Bug #6: Missing Climate and Select Entities

**User Report:** "climate entities are missing, select entities are missing"

**Possible Causes:**
1. Entities not being created for Modbus coordinator
2. Conditional logic preventing creation
3. Register data not available

**Status:** ⏳ NEEDS INVESTIGATION after fixes above

---

## Summary

**Fixed (awaiting restart):**
- ✅ Double-scaling bug (all sensor scales → 1.0)
- ✅ Outdoor temp register (2102 → 2103)
- ✅ Loop 1 temp register (2109 → 2047)

**Still To Fix:**
- ⏳ Operation Regime (register 2007)
- ⏳ Working Function enum mapping
- ⏳ Missing climate/select entities
- ⏳ Number entities showing incorrect values
- ⏳ Many diagnostic sensors unavailable

**Next Steps:**
1. Copy fixed files and restart HA
2. Verify temperature sensors now show correct values
3. Investigate why Working Function shows raw value 33
4. Check which climate/select entities are missing
5. Validate number entities
