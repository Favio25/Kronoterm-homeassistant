# Systematic Fixes Progress - 2026-02-03

## ✅ FIXED (Deployed & Verified)

### 1. Double-Scaling Bug
- **Problem:** Coordinator scaled values, then sensors scaled AGAIN (COP: 7.9 → 0.08)
- **Fix:** All sensor scaling factors in const.py changed to 1.0
- **Result:** COP now shows 7.9 ✅

### 2. Outdoor Temperature Register
- **Problem:** Official docs said 2103=outdoor, but device actually has outdoor on 2102
- **Fix:** Changed both const.py and modbus_registers.py to use 2102
- **Result:** Outdoor temp now shows ~4.0°C instead of ~40°C ✅

---

## ⏳ IN PROGRESS

### 3. Loop 1 Temperature - CONFLICT DETECTED
- **Problem:** Register 2047 used by BOTH sensor (temperature) and number (eco offset)
- **Official Docs:** 2047 = krog1_temp (temperature, READ-ONLY)
- **Current Code:**
  - `const.py`: Loop 1 temperature sensor uses 2047
  - `number.py`: Loop 1 ECO offset control uses 2047 (WRONG!)
- **Device Value:** raw=0 → 0.0°C (conflict or error)

**Action Needed:**
1. Check original discovery docs for 500-range sensor registers (e.g., 546 = supply temp)
2. Fix number.py offset registers to not conflict with temperature sensors
3. Add missing 500-range registers to modbus_registers.py

---

### 4. Offset Values Look Like Setpoints
- **Problem:** "Offset" registers show values like 23°C, 50°C (way too high for offsets)
- **Examples:**
  - 2031 (DHW offset): 50.1°C
  - 2048 (Loop 1 offset): 23.0°C
- **Theory:** These might actually be SETPOINT temperatures, not offsets

**Action Needed:**
1. Compare with Cloud API JSON to see what these values represent
2. Test writing to these registers to understand behavior
3. Possibly rename from "offset" to "setpoint" if confirmed

---

### 5. Working Function Shows Raw Bitfield
- **Problem:** Register 2001 shows raw=8193 instead of enum string
- **Root Cause:** This is a BITFIELD (0x2001), not a simple enum
- **Fix Needed:** Change RegisterType.ENUM → RegisterType.BITS

**Action Needed:**
1. Convert to bitfield register type
2. Create multiple binary sensors for each bit
3. Map bits to their meanings (system on, heating active, DHW active, etc.)

---

### 6. Operation Regime Unavailable
- **Problem:** Register 2007 not in ALL_REGISTERS list
- **Official Docs:** 2007 = "unknown"
- **const.py:** Has EnumSensorDefinition for it

**Action Needed:**
1. Determine if register 2007 exists and is readable
2. Add to modbus_registers.py if valid
3. Otherwise remove from const.py

---

## 🔴 NOT STARTED

### 7. Missing Climate Entities
- User report: Climate entities missing
- Need to investigate why climate.py not creating entities for Modbus

### 8. Missing Select Entities  
- User report: Select entities missing
- Need to investigate why select.py not creating entities for Modbus

### 9. Number Entities Show Incorrect Values
- Related to offset/setpoint confusion (issue #4)

### 10. Many Diagnostic Sensors Unavailable
- Need to check which sensors are reading error values vs missing entirely

---

## Next Actions (Priority Order)

1. **IMMEDIATE:** Add 500-range sensor registers from original discovery
2. **IMMEDIATE:** Fix offset/temperature register conflicts in number.py
3. **HIGH:** Investigate why climate/select entities not being created
4. **MEDIUM:** Fix Working Function bitfield
5. **MEDIUM:** Verify Operation Regime register
6. **LOW:** Clean up unavailable diagnostic sensors

---

## Files Modified This Session

- `custom_components/kronoterm/const.py` - Fixed scaling, outdoor temp register
- `custom_components/kronoterm/modbus_registers.py` - Swapped outdoor/DHW registers
- `custom_components/kronoterm/modbus_coordinator.py` - Added debug logging

**Git Commits:**
- f2de2e3: Fix double-scaling bug
- c2f0cb8: Fix register mapping bugs (loop 1 temp)
- ad9a7e2: Revert outdoor temp to 2102
