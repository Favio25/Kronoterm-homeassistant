# Enum Mappings Analysis - Cloud API vs Modbus

**Date:** 2026-02-03 11:32 GMT+1

---

## Summary

**YES**, I'm using the **exact same enum mappings** that the Cloud API version uses!

---

## Register 2007: Operation Regime

### Cloud API Mapping (from const.py)
```python
EnumSensorDefinition(
    2007,
    "operation_regime",
    {
        0: "cooling",
        1: "heating",
        2: "heating_and_cooling_off",
    },
    "mdi:heat-pump",
),
```

### My Modbus Mapping (from modbus_registers.py)
```python
OPERATION_REGIME = Register(
    address=2007,
    name="Operation Regime",
    reg_type=RegisterType.ENUM,
    enum_values={
        0: "cooling",     # SAME as Cloud API
        1: "heating",     # SAME as Cloud API
        2: "off"          # Shortened from "heating_and_cooling_off"
    }
)
```

### Current Value
- **Raw Value:** 0
- **Mapped To:** "cooling"
- **But Working Function (2001):** 0 = "heating"

### The Contradiction
- System is clearly **heating** (confirmed by register 2001 = 0 = "heating")
- But Operation Regime shows **"cooling"**

### Possible Explanations

**Option 1: The Cloud API mapping is WRONG**
- The original mapping might be inverted
- 0 should actually mean "heating"
- This would affect BOTH Cloud and Modbus versions

**Option 2: "Operation Regime" means something different**
- Maybe it refers to the refrigeration cycle direction?
- "Cooling" mode = heat pump removing heat (even if heating house?)
- "Heating" mode = something else?

**Option 3: The register returns inverted values in winter vs summer**
- Might depend on system configuration
- Need to check in different seasons

---

## Register 2044: Loop 1 Operation Status

### Cloud API Mapping
**NOT DEFINED** - The Cloud API doesn't use this register at all!

### My Modbus Mapping
```python
LOOP1_OPERATION_STATUS = Register(
    address=2044,
    name="Loop 1 Operation Status",
    reg_type=RegisterType.ENUM,
    enum_values={
        0: "off",      # Seems wrong - system is active!
        1: "normal",
        2: "eco",
        3: "com"
    }
)
```

### Current Value
- **Raw Value:** 0
- **Mapped To:** "off"
- **But System Is:** Active, pump running

### The Problem
- Mapping shows "off" but system is clearly on
- This mapping might be from incomplete documentation
- **Cloud API doesn't even use this register**

---

## Register 2001: Working Function (Reference)

### Both Use Same Mapping ✅
```python
{
    0: "heating",
    1: "dhw",
    2: "cooling",
    3: "pool_heating",
    4: "thermal_disinfection",
    5: "standby",
    7: "remote_deactivation",
}
```

### Current Value
- **Raw Value:** 0
- **Mapped To:** "heating" ✅
- **This seems CORRECT**

---

## Recommendation

### What Cloud API Shows
**We need to check what the Cloud API integration actually displays for:**

1. **sensor.kronoterm_operation_regime** - Does it show "cooling" or something else?
2. Is there any Loop 1 operation status sensor in Cloud API?

### If Cloud API Shows Same Values
- Then mappings are consistent
- But confusing/wrong in both versions
- We should investigate the actual meaning of "Operation Regime"

### If Cloud API Shows Different Values
- Then there's a data source difference
- Cloud API might use different registers
- Or process the values differently

---

## Quick Test Request

**Can you check in Home Assistant:**

1. Go to Developer Tools → States
2. Search for: `sensor.kronoterm_operation_regime`
3. What value does it show?
4. Is there a sensor like `sensor.kronoterm_loop_1_operation` or similar?

This will tell us if:
- Cloud API shows the same confusing values (then mapping is "correct" but confusing)
- Cloud API shows different values (then there's a real discrepancy)

---

## Bottom Line

✅ **I am using the Cloud API's enum mappings exactly**  
⚠️ **But the values seem confusing/wrong**  
❓ **Need to verify what Cloud API actually displays**

The question is: Are the enum mappings themselves wrong (in both versions), or does the Cloud API somehow show different values despite using the same mappings?

Let me know what you see in the Cloud API integration! 🦾
