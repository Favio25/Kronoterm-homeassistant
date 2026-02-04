# Kronoterm Modbus Integration - Systematic Fix Session

## Session Start: 2026-02-03 13:30 GMT+1
## Current Time: 2026-02-03 14:00 GMT+1

---

## User Feedback That Triggered This Session

> "Your testing method is very flawed. A lot of sensors are missing, some are unavailable, number entities show incorrect values, climate entities are missing, select entities are missing."

**Response:** You were 100% correct. I found multiple critical bugs through systematic testing.

---

## Bugs Found & Fixed

### ✅ BUG #1: Double-Scaling (FIXED)
- **Problem:** COP showed 0.08 instead of 7.9
- **Root Cause:** Coordinator scaled by 0.01, then sensor scaled AGAIN by 0.01
- **Fix:** Changed all const.py sensor scales to 1.0
- **Status:** ✅ DEPLOYED - COP now shows 7.9 correctly

### ✅ BUG #2: Wrong Outdoor Temperature Register (FIXED)
- **Problem:** Showed ~40°C instead of ~4°C
- **Root Cause:** Used register 2103 per "official docs", but device actually has outdoor on 2102
- **Fix:** Reverted to 2102 (original discovery was correct, official docs were WRONG)
- **Status:** ✅ DEPLOYED - Outdoor temp now shows ~4°C correctly

### ✅ BUG #3: Missing 500-Range Sensor Registers (FIXED)
- **Problem:** Critical sensors like Supply/Return/DHW temps were MISSING
- **Root Cause:** Original discovery found these (546, 553, 572) but they were never coded!
- **Fix:** Added SUPPLY_TEMP (546), RETURN_TEMP (553), DHW_SENSOR_TEMP (572)
- **Status:** ⏳ DEPLOYING NOW (restart in progress)

---

## Bugs Identified But Not Yet Fixed

### ⏳ BUG #4: Register Conflicts (number.py vs sensor.py)
- **Problem:** Register 2047 used by BOTH Loop 1 temperature sensor AND Loop 1 eco offset control
- **Impact:** Loop 1 temp shows 0.0°C because number entity is trying to write to it
- **Fix Needed:** Separate sensor registers (500-range) from control registers (2000-range)
- **Priority:** HIGH

### ⏳ BUG #5: "Offsets" Are Actually Setpoints
- **Problem:** DHW offset shows 50.1°C, Loop offsets show 23°C (way too high)
- **Theory:** These 2000-range "offset" registers are actually SETPOINT temperatures
- **Fix Needed:** Rename/reclassify these registers, compare with Cloud API
- **Priority:** MEDIUM

### ⏳ BUG #6: Working Function Shows Raw Bitfield
- **Problem:** Shows 8193 instead of "heating"/"dhw"/etc.
- **Root Cause:** Register 2001 is a BITFIELD (0x2001), not a simple enum
- **Fix Needed:** Convert to RegisterType.BITS, create binary sensors for each bit
- **Priority:** MEDIUM

### ⏳ BUG #7: Operation Regime Unavailable
- **Problem:** Register 2007 not in ALL_REGISTERS
- **Fix Needed:** Add register definition or remove from const.py
- **Priority:** LOW

### ⏳ BUG #8: Climate Entities Missing
- **Problem:** User reports climate entities not showing
- **Fix Needed:** Investigate climate.py entity creation logic for Modbus
- **Priority:** HIGH

### ⏳ BUG #9: Select Entities Missing
- **Problem:** User reports select entities not showing
- **Fix Needed:** Investigate select.py entity creation logic for Modbus
- **Priority:** HIGH

---

## Root Cause Analysis

### The 500-Range vs 2000-Range Discovery

This is the **KEY INSIGHT** that explains most issues:

**500-Range Registers:**
- Real sensor values (current state)
- Read-only
- Match Cloud API perfectly
- Examples: 546=supply temp, 553=return temp, 572=DHW temp

**2000-Range Registers:**
- Control/configuration values (setpoints, modes, offsets)
- Read/write mix
- Don't always match current sensor readings
- Examples: 2047=loop setpoint(?), 2048=loop offset(?)

**What Went Wrong:**
1. Original discovery found both ranges
2. "Official Kronoterm docs" only documented 2000+ range
3. Code was "corrected" to match official docs  
4. 500-range sensors were LOST in the correction
5. 2000-range registers were misunderstood (offset vs setpoint confusion)

---

## Testing Methodology Improvements

### Before (Flawed):
- Checked if integration loaded without errors ✅
- Assumed "Successfully read X registers" meant everything worked ✅
- Didn't verify actual sensor VALUES ❌
- Didn't check entity availability in HA UI ❌

### Now (Systematic):
1. Added debug logging for ALL temperature registers
2. Compare actual values to expected ranges (4°C outdoor, not 40°C!)
3. Cross-reference with Cloud API values
4. Check for register conflicts (same address used twice)
5. Verify entity creation in UI (not just logs)

---

## Files Modified This Session

1. `const.py` - Fixed scaling, register mappings, added 500-range sensors
2. `modbus_registers.py` - Added 500-range sensors, fixed outdoor/DHW swap
3. `modbus_coordinator.py` - Added comprehensive debug logging

**Git Commits:** 4 commits
- f2de2e3: Fix double-scaling bug
- ad9a7e2: Revert outdoor temp to 2102  
- fe7347d: Fix labels + add analysis docs
- c6b2b62: Add 500-range sensor registers

---

## Next Steps (Priority Order)

1. **IMMEDIATE:** Verify 500-range sensors show correct values after restart
2. **IMMEDIATE:** Fix register conflicts in number.py (offsets vs temps)
3. **HIGH:** Investigate climate/select entity creation
4. **MEDIUM:** Fix Working Function bitfield
5. **MEDIUM:** Clarify offset vs setpoint registers
6. **LOW:** Clean up unavailable diagnostic sensors

---

## Expected State After Current Restart

**Should Be Working:**
- ✅ Outdoor Temperature: ~4°C
- ✅ COP Value: ~7.9  
- ✅ Supply Temperature: ~38-40°C (NEW!)
- ✅ Return Temperature: ~38-40°C (NEW!)
- ✅ DHW Sensor Temperature: ~50-55°C (NEW!)

**Still Broken:**
- ❌ Loop 1 Temperature (conflict with offset)
- ❌ Working Function (bitfield)
- ❌ Operation Regime (missing)
- ❌ Climate entities (not created)
- ❌ Select entities (not created)  
- ❌ Number entities (wrong values)

---

**Status:** Restart in progress, awaiting verification of 500-range sensors...
