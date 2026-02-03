# Register Mapping Issues Found

**Date:** 2026-02-03 11:28 GMT+1

---

## Comparison Results

### ✅ Correctly Mapped Registers

These match expected values:

| Register | Name | Value | Status |
|----------|------|-------|--------|
| 546 | Supply Temperature | 39.0°C | ✅ |
| 551 | Outdoor Temperature | 3.8°C | ✅ |
| 553 | Return Temperature | 37.3°C | ✅ |
| 572 | DHW Temperature | 55.7°C | ✅ |
| 2102 | Outdoor Temp (2000s range) | 3.8°C | ✅ (matches 551) |
| 2109 | Loop 1 Current | 37.3°C | ✅ (matches 553 return) |
| 2187 | Loop 1 Setpoint | 28.6°C | ✅ |
| 2023 | DHW Setpoint | 44.0°C | ✅ |
| 2101 | Reservoir/HP Inlet | 18.1°C | ✅ |
| 2160 | Loop 1 Thermostat | 22.9°C | ✅ |
| 2001 | Working Function | heating (0) | ✅ |
| 2129 | Current Power | 392W | ✅ |
| 2371 | COP | 7.91 | ✅ |
| 2090 | Operating Hours Heating | 3898h | ✅ |
| 2155-2158 | Activation Counters | Various | ✅ |

---

## ❌ ISSUES FOUND

### 1. Register 2104: HP Outlet Temperature
**Problem:** Returns 65497 which scales to 6549.7°C (clearly wrong)  
**Root Cause:** This is an error value not in our ERROR_VALUES list  
**Fix:** Add 65497 to ERROR_VALUES in modbus_coordinator.py  
**Status:** Sensor not connected / returning error code

### 2. Register 2007: Operation Regime ENUM INVERTED
**Problem:**
- Raw value: 0
- Current mapping: 0="cooling", 1="heating", 2="off"
- Actual state: System is heating (confirmed by 2001=0=heating)
- **The enum values appear to be INVERTED!**

**Correct mapping should be:**
```python
0: "heating",  # NOT "cooling"
1: "cooling",  # NOT "heating"
2: "off"
```

### 3. Register 2044: Loop 1 Operation Mode ENUM WRONG
**Problem:**
- Raw value: 0
- Current mapping: 0="off", 1="normal", 2="eco", 3="comfort"
- Actual state: Pump is running, system active
- **The enum is incorrect!**

**Need to verify correct mapping** - probably:
```python
0: "normal" or "auto",  # NOT "off"
1: "eco",
2: "comfort",
...
```

### 4. Register 2130: Loop 1 Basic Mode Temp
**Problem:**
- Returns: 0.0°C
- Expected: Should match Loop 1 current temp (37.3°C)
- **This is likely NOT the correct register for Loop 1 current temperature**

**Current usage:** We use 2109 for Loop 1 Current (37.3°C) which matches return temp (553=37.3°C), so 2109 is correct.  
**Action:** Remove 2130 from register list or mark it as diagnostic-only

---

## 🔄 Registers That Need Cloud API Comparison

These are working but should be verified against Cloud API:

| Register | Name | Modbus Value | Need Cloud Verification |
|----------|------|--------------|------------------------|
| 2105 | Evaporating Temperature | 88.0°C | ❓ Is this normal range? |
| 2327 | HP Load | 0% | ❓ Should this be 0 when heating? |
| 2329 | Heating Power | 0W | ❓ Contradicts 2129=392W? |
| 2372 | SCOP | 0.0 | ❓ Why always 0? |

---

## 📋 Recommended Fixes

### Fix 1: Update ERROR_VALUES
```python
# In modbus_coordinator.py
ERROR_VALUES = [64936, 64937, 65535, 65517, 65526, 65497, 65499]  # Added 65497, 65499
```

### Fix 2: Fix Operation Regime Enum
```python
# In modbus_registers.py
OPERATION_REGIME = Register(
    address=2007,
    name="Operation Regime",
    reg_type=RegisterType.ENUM,
    enum_values={
        0: "heating",   # FIXED: was "cooling"
        1: "cooling",   # FIXED: was "heating"
        2: "off"
    }
)
```

### Fix 3: Fix Loop 1 Operation Mode Enum
**Need to research correct values** - possible fix:
```python
LOOP1_OPERATION_STATUS = Register(
    address=2044,
    name="Loop 1 Operation Status",
    reg_type=RegisterType.ENUM,
    enum_values={
        0: "normal",  # NEEDS VERIFICATION
        1: "eco",
        2: "comfort",
        3: "off"      # or maybe this order?
    }
)
```

### Fix 4: Remove or Document 2130
Either:
- Remove from temperature sensor list
- Or mark as diagnostic and document it's "basic mode setpoint" not current temp

---

## 🎯 Next Steps

1. **Apply error value fix** (easy - just add to list)
2. **Fix Operation Regime enum** (swap 0 and 1 values)
3. **Research Loop 1 Operation Mode enum** (need documentation or testing)
4. **Verify registers 2327, 2329, 2372** against Cloud API
5. **Test and confirm all fixes**

---

## Cloud API Values Needed

To complete the verification, please check these in the **Cloud API integration**:

1. **Operation Regime** - What does it show? (should be "heating" not "cooling")
2. **Loop 1 Operation Status** - What does it show? (should NOT be "off")
3. **HP Load** - Is it 0% in Cloud API too?
4. **Heating Power vs Current Power** - Are they different in Cloud API?
5. **SCOP** - Is it always 0 in Cloud API too?

Let me know these values and I'll fix all the mappings! 🦾
