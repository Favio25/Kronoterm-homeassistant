# Modbus vs Cloud API Value Comparison

**Date:** 2026-02-03 11:20 GMT+1

---

## Current Modbus Values (Just Scanned)

Here are the current readings from the Modbus integration:

### Temperature Sensors
- **Outdoor Temperature:** 3.8°C (register 2102, raw: 38)
- **Loop 1 Current Temperature:** 37.9°C (register 2109, raw: 379)
- **Loop 1 Setpoint:** 28.6°C (register 2187, raw: 286)
- **Loop 1 Thermostat Temperature:** 22.9°C (register 2160, raw: 229)
- **DHW Setpoint:** 44.0°C (register 2023, raw: 440)
- **HP Inlet Temperature:** 18.5°C (register 2101, raw: 185)
- **Evaporating Temperature:** 89.1°C (register 2105, raw: 891)

### Power & Load
- **Current Power:** 399W (register 2129, raw: 399)
- **HP Load:** 0% (register 2327, raw: 0)
- **System Pressure:** 1.7 bar (register 2325, raw: 17)
- **COP:** 7.91 (register 2371, raw: 791)
- **SCOP:** 0.0 (register 2372, raw: 0)

### Operating Hours
- **Compressor Heating:** 3898h (register 2090, raw: 3898)
- **Compressor DHW:** 0h (register 2091, raw: 0)
- **Additional Source:** 1h (register 2095, raw: 1)

### Status
- **Working Function:** heating (register 2001, raw: 0)
- **Error/Warning:** warning (register 2006, raw: 1)
- **Operation Regime:** cooling (register 2007, raw: 0)
- **Loop 1 Operation Status:** off (register 2044, raw: 0)
- **DHW Operation:** on (register 2026, raw: 1)

### Pumps
- **Loop 1 Circulation Pump:** ON (register 2045, raw: 257)
- **Loop 2 Circulation Pump:** ON (register 2055, raw: 1)
- **DHW Tank Circulation Pump:** ON (register 2028 bit 1, raw: 1550)

### Activation Counters
- **Compressor Activations Heating:** 0 (register 2155, raw: 0)
- **Compressor Activations Cooling:** 4039 (register 2156, raw: 4039)
- **Activations Boiler:** 5 (register 2157, raw: 5)
- **Activations Defrost:** 0 (register 2158, raw: 0)

---

## ⚠️ Suspicious Values Noticed

### 1. Loop 1 Operation Status: "off" (raw: 0)
- Modbus shows: **off**
- Expected: Should probably be "normal" or "on" if system is running
- **Register 2044 might be wrong mapping**

### 2. Operation Regime: "cooling" (raw: 0)
- Modbus shows: **cooling**
- Expected: Should probably be "heating" if heating is active
- **Register 2007 enum values might be inverted**

### 3. HP Outlet Temperature: 6549.9°C (raw: 65499)
- Clearly an error value that's not in ERROR_VALUES list
- Should be unavailable

---

## Please Provide Cloud API Values

Can you check these values in the **Cloud API** integration and tell me if they match?

###Key Sensors to Compare:
1. **Outdoor Temperature** - Modbus says 3.8°C
2. **Loop 1 Current Temperature** - Modbus says 37.9°C
3. **Loop 1 Operation Status** - Modbus says "off" (suspicious!)
4. **Operation Regime** - Modbus says "cooling" (suspicious!)
5. **Working Function** - Modbus says "heating"
6. **Current Power** - Modbus says 399W
7. **COP** - Modbus says 7.91
8. **Operating Hours Heating** - Modbus says 3898h

---

## How to Check Cloud API Values

1. Go to: **Developer Tools → States**
2. Search for: `kronoterm`
3. Look for entities WITHOUT "adapt_0416" in the name (those are Modbus)
4. Check the values for the sensors listed above

OR

Just tell me which specific values look wrong and I'll investigate those registers.

---

## Next Steps

Once I know which values don't match:
1. I'll do a detailed scan of those specific registers
2. Check register mappings against the original documentation
3. Fix any incorrect mappings
4. Update the const.py and modbus_registers.py files
5. Test and verify

Please let me know what you see! 🦾
