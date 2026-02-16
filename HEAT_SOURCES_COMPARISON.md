# Heat Sources: Cloud API vs Modbus TCP

## Summary

There are **THREE different heat sources** in the Kronoterm system:

### 1. **Reserve Source** (Rezervni vir)
- **Modbus Status:** Register 2003 → `binary_sensor.kronoterm_reserve_source_status`
- **Modbus Control:** Register 2018 → `switch.kronoterm_reserve_source`
- **Cloud Control:** `switch.kronoterm_reserve_source` (via ShortcutsData "reserve_source")

### 2. **Alternative Source** (Alternativni vir)
- **Modbus Status:** Register 2004 → `binary_sensor.kronoterm_alternative_source_status`
- **Modbus Pump Status:** Register 2088 → `binary_sensor.kronoterm_alternative_source_pump`
- **Modbus Control:** ❌ **NO CONTROL REGISTER** (read-only status)
- **Cloud Control:** ❌ **NO SWITCH** (not exposed in Cloud API)

### 3. **Additional Source** (Dodatni vir)
- **Modbus Status:** Register 2002 bit 0 → `binary_sensor.kronoterm_additional_source`
- **Modbus Control:** Register 2016 → `switch.kronoterm_additional_source`
- **Cloud Control:** `switch.kronoterm_additional_source` (via ShortcutsData "additional_source")

---

## Feature Parity Analysis

### ✅ **Cloud API Mode**
**Switches (Control):**
- Reserve Source (on/off)
- Additional Source (on/off)

**Sensors (Status):**
- ❌ **MISSING:** No status sensors for any heat sources

### ✅ **Modbus TCP Mode**
**Switches (Control):**
- Reserve Source (register 2018)
- Additional Source (register 2016)

**Binary Sensors (Status):**
- Reserve Source Status (register 2003)
- Alternative Source Status (register 2004) ← **READ-ONLY, no control**
- Alternative Source Pump (register 2088)
- Additional Source Status (register 2002 bit 0)

---

## Key Differences

| Feature | Cloud API | Modbus TCP |
|---------|-----------|------------|
| Reserve Source Control | ✅ Switch | ✅ Switch (2018) |
| Reserve Source Status | ❌ Missing | ✅ Binary Sensor (2003) |
| Alternative Source Control | ❌ Not available | ❌ Not available (read-only) |
| Alternative Source Status | ❌ Missing | ✅ Binary Sensor (2004) |
| Alternative Source Pump | ❌ Missing | ✅ Binary Sensor (2088) |
| Additional Source Control | ✅ Switch | ✅ Switch (2016) |
| Additional Source Status | ❌ Missing | ✅ Binary Sensor (2002) |

---

## Recommendations

1. **Cloud API is missing status sensors** - users can turn sources on/off but can't see if they're actually running
2. **Alternative Source has no control** - it appears to be controlled automatically by the heat pump (cannot be manually enabled)
3. **Modbus mode provides more visibility** - you can see both control state AND actual running status

---

## Notes from Kronoterm Manual

- **Register 2003:** Rezervni vir (Reserve source status)
- **Register 2004:** Alternativni vir (Alternative source status)
- **Register 2002 bit 0:** Vklop dodatnega vira (Additional source activation)
- **Register 2016:** Vklop dodatnega vira (Additional source enable control)
- **Register 2018:** Vklop rezervnega vira (Reserve source enable control)
- **Register 2088:** Obtočna črpalka alternativni vir (Alternative source circulation pump)
