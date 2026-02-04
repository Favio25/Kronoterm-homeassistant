# 500-Range Sensor Registers - Critical Discovery

## Background

During original device testing, 500-range registers were discovered and validated against Cloud API values:

| Register | Name | Cloud API Value | Modbus Value | Match |
|----------|------|----------------|--------------|-------|
| 546 | Supply Temperature | 39.5°C | 39.5°C | ✅ |
| 553 | Return Temperature | 39.5°C | 39.5°C | ✅ |
| 572 | DHW Temperature | 54.9°C | 54.9°C | ✅ |

**Problem:** These registers were documented but NEVER ADDED to the code!

---

## Why This Matters

### The 500-Range vs 2000-Range Confusion

**500-Range (546, 553, 572):**
- ACTUAL sensor readings
- Real-time temperature values
- Match Cloud API perfectly
- Read-only

**2000-Range (2047, 2101, etc.):**
- Control/configuration registers
- Might be setpoints, not current temps
- Some return 0.0°C or weird values
- Mix of read/write

### What Was Broken

1. **Loop Temperature sensors** tried to use 2047/2109 (wrong range) → showed 0.0°C or "Unavailable"
2. **Supply/Return temps** were missing entirely
3. **DHW sensor** reading was missing (only had setpoint)

---

## Fix Applied

### Added to `modbus_registers.py`:

```python
SUPPLY_TEMP = Register(
    address=546,
    name="Supply Temperature",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

RETURN_TEMP = Register(
    address=553,
    name="Return Temperature",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

DHW_SENSOR_TEMP = Register(
    address=572,
    name="DHW Sensor Temperature",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)
```

### Added to `const.py`:

```python
SensorDefinition(546, "supply_temperature", "°C", "mdi:thermometer-chevron-up", 1.0),
SensorDefinition(553, "return_temperature", "°C", "mdi:thermometer-chevron-down", 1.0),
SensorDefinition(572, "dhw_sensor_temperature", "°C", "mdi:water-thermometer", 1.0),
```

---

## Expected Results

After restart, should see:
- ✅ Supply Temperature: ~38-40°C (matches heat pump output)
- ✅ Return Temperature: ~38-40°C (matches heat pump input)  
- ✅ DHW Sensor Temperature: ~45-55°C (matches water tank)

These will finally provide the REAL sensor values users expect!

---

## Still To Fix

1. **Loop 1 Temperature** - Need to find correct 500-range register (might be 547-550)
2. **Offset vs Setpoint confusion** - 2000-range registers need proper classification
3. **Number entities** - Still reading wrong registers for offsets
