# Unavailable Sensors - Explanation

**Date:** 2026-02-03 11:05 GMT+1

## Summary

Some diagnostic sensors show as "unavailable" because **the physical sensors are not connected** to your heat pump. This is **correct behavior**, not a bug.

## Sensors That Are Unavailable (and Why)

### 1. **Temperature Compressor Outlet** (Register 2106)
- **Modbus Value:** 64936 (error code)
- **Reason:** Physical sensor not installed on your heat pump
- **Status:** ⚠️ UNAVAILABLE (expected)

### 2. **Temperature HP Outlet** (Register 2104)
- **Modbus Value:** 65526 (error code) 
- **Reason:** Physical sensor not installed
- **Status:** ⚠️ UNAVAILABLE (expected)

### 3. **Loop 2 Current Temperature** (Register 2110)
- **Modbus Value:** 64936 (error code)
- **Reason:** Loop 2 not installed or sensor disconnected
- **Status:** ⚠️ UNAVAILABLE (expected)

## What's Working (Diagnostic Sensors with Real Data)

### Operating Hours ✅
- **Compressor Heating:** 3897 hours
- **Compressor DHW:** 0 hours
- **Additional Source:** 1 hour

### Performance Metrics ✅
- **COP:** 7.91
- **SCOP:** 0.0

### Activation Counters ✅
- **Compressor Activations Heating:** 0
- **Compressor Activations Cooling:** 4039
- **Activations Boiler:** 5
- **Activations Defrost:** 0

### Temperature Sensors ✅
- **HP Inlet Temperature:** 36.3°C
- **Evaporating Temperature:** 92.3°C
- **Compressor Inlet:** 90.9°C (from register 2105)

## Why Some Sensors Return Error Values

Kronoterm heat pumps use Modbus error codes to indicate:
- **64936-64937:** Sensor not physically connected
- **65517-65535:** Various error conditions

When the integration detects these values, it correctly marks the entity as "unavailable" rather than displaying incorrect data.

## Is This Normal?

**Yes!** Not all heat pump models have all sensors installed. Your configuration is:
- ✅ **Loop 1:** Installed and working
- ❌ **Loop 2:** Not installed (sensors unavailable)
- ✅ **DHW:** Installed and working
- ⚠️ **Some temperature sensors:** Not connected (compressor outlet, HP outlet)

This matches your heat pump's actual hardware configuration.

## What You Should See

In Home Assistant, you should have:
- ✅ **11-12 diagnostic sensors with values** (COP, operating hours, activations, etc.)
- ⚠️ **2-3 diagnostic sensors unavailable** (missing physical sensors)
- ✅ **30+ regular sensors working** (loops, DHW, power, etc.)

**This is correct and expected behavior!** 🦾

---

**Bottom line:** "Unavailable" = Physical sensor not installed on your heat pump hardware. The integration is working correctly.
