# Heat Sources Explained (Official Kronoterm Manual)

## 🌞 **ALTERNATIVNI VIR (Alternative Source)**

**Type:** External heat source (solar collectors, fireplace stoves, wood stoves)

**Description:** Heat source used for systems with solar collectors, fireplace stoves, and wood stoves, when either:
- We don't have a guaranteed heat source available at every moment, OR
- Automatic switching via signal from device controller (e.g., wood stove) is not possible

**Control:** Manual or external conditions (not controlled by heat pump)

**Why no control switch?** This source is either manually operated (wood stove) or depends on external conditions (sun for solar collectors). The heat pump monitors its status but doesn't control it.

**Modbus Registers:**
- **2004** - Status (0=Off, 1=On) → `binary_sensor.kronoterm_alternative_source_status`
- **2088** - Circulation pump status → `binary_sensor.kronoterm_alternative_source_pump`
- **No write register** - read-only status

---

## 🔥 **ZUNANJI DODATNI VIR (Additional Source)**

**Type:** External backup heat source (oil/gas/pellet boiler, external electric heater)

**Description:** Heat source located next to the device that can be used:
- **In parallel** with the heat pump, OR
- **Alternatively** (either-or system)
- Automatic switching via signal from device controller
- In case of heat pump failure (anti-freeze program), can briefly take over heating

**Control:** Heat pump controlled (can enable/disable)

**Modbus Registers:**
- **2002 bit 0** - Status (activation flag) → `binary_sensor.kronoterm_additional_source`
- **2016** - Control (0=Off, 1=On) → `switch.kronoterm_additional_source`

---

## ⚡ **REZERVNI VIR (Reserve Source)**

**Type:** Internal flow-through electric heater (built into the heat pump)

**Description:** 
- **Emergency heating:** Activates during heat pump failure (anti-freeze program) to ensure basic operation until service arrives
- **Bivalent operation:** Can assist the heat pump below the bivalent point when heat pump power is insufficient to cover building heat losses

**Control:** Heat pump controlled (can enable/disable)

**Modbus Registers:**
- **2003** - Status (0=Off, 1=On) → `binary_sensor.kronoterm_reserve_source_status`
- **2018** - Control (0=Off, 1=On) → `switch.kronoterm_reserve_source`

**Note:** The manual text says "Rezervni oz. dodatni vir" (Reserve **or** additional source) but this is imprecise terminology. It should just say "Rezervni vir" (Reserve source) to avoid confusion with the actual "Dodatni vir" (Additional source) which refers to the external backup heater.

---

## 📊 Summary Table

| Source Type | Location | Purpose | Heat Pump Control? | Registers |
|-------------|----------|---------|-------------------|-----------|
| **Alternative** | External (solar/wood) | Renewable/manual heat | ❌ No (monitor only) | 2004 (status), 2088 (pump) |
| **Additional** | External (boiler) | Backup/parallel heating | ✅ Yes | 2002 (status), 2016 (control) |
| **Reserve** | Built-in (electric) | Emergency + bivalent | ✅ Yes | 2003 (status), 2018 (control) |

---

## Naming Clarification

The manual uses imprecise terminology in one place, saying "Rezervni oz. dodatni vir" (Reserve **or** additional source) for the internal heater, but this should just be called **"Reserve Source"**.

The correct naming is:
- **Reserve Source** (Rezervni vir) = Internal electric heater (2018/2003)
- **Additional Source** (Dodatni vir) = External backup heater (2016/2002)
- **Alternative Source** (Alternativni vir) = External renewable/manual (2004/2088)

This makes logical sense:
- **Reserve** = always available backup (built into unit)
- **Additional** = external system added to installation
- **Alternative** = alternative heat sources (solar, wood)

---

## Cloud API vs Modbus

### Cloud API
- ✅ Reserve Source switch (internal electric)
- ✅ Additional Source switch (external backup)
- ❌ No Alternative Source (makes sense - it's not heat pump controlled!)
- ❌ No status sensors (can't see if sources are actually running)

### Modbus TCP
- ✅ Reserve Source switch + status sensor
- ✅ Additional Source switch + status sensor
- ✅ Alternative Source status sensors (read-only, monitor external source)
- ✅ Full visibility into actual running state

---

## Bivalent Point

The **bivalent point** is the outdoor temperature below which the heat pump alone cannot provide enough heating power. Below this temperature, the reserve/additional source activates to assist.

For example:
- Above -5°C: Heat pump alone
- Below -5°C: Heat pump + reserve electric heater

This ensures the building stays warm even in extreme cold.
