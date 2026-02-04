# Register Corrections Based on Official Documentation

**Source:** KRONOTERM CNS – Navodila za priklop in uporabo

## 🎯 CRITICAL FINDINGS

### ✅ FOUND - Missing Features

1. **Main Temperature Offset** 
   - Register: **2014** `korekcija_temperature`
   - Scale: **1** (NOT 0.1!)
   - Access: RW
   - This is the system-wide temperature correction

2. **Anti-Legionella**
   - Register: **2301** `dezinfekcija_enable`
   - Type: Binary (0/1)
   - Access: RW
   - Additional registers:
     - 2302: dezinfekcija_temp (temperature, scale 0.1)
     - 2303: dezinfekcija_day
     - 2304: dezinfekcija_minute

3. **Reserve Source**
   - Register: **2018** `vklop_rezervnega_vir`
   - Type: Binary (0/1)
   - Access: RW
   - Status read from: 2003 `rezervni_vir`

---

## ❌ INCORRECT MAPPINGS - Must Fix!

### System Control
- **WRONG:** We used 2002 for system on/off
- **CORRECT:** Register **2012** `vklop_sistema` (RW)
- **Note:** 2002 is `dodatni_vklopi_bitfield` (read-only)

### Loop 1 Current Temperature
- **WRONG:** We thought 2130 was loop 1 current temp
- **CORRECT:** Multiple registers available:
  - **2047**: `krog1_temp` (heating circuit output)
  - **2128**: `temp_krog1` (heating circuit temp)
  - **2130**: `temp_krog1b` (alternate reading)
  - **2191**: `prostor1_current` (room current temp)

### Loop Setpoints
- **WRONG:** We used 2187 for Loop 1 setpoint
- **CORRECT:** 
  - **2187**: `prostor1_set` - Room/space temperature setpoint
  - Loop setpoints appear to be calculated from heating curves
  - Use system_setpoint (2040) + offset (2048) for Loop 1

### DHW Circulation Switch
- **MISSING:** No dedicated circulation switch register found
- **FOUND:** Register 2028 `sanitarna_bitfield` contains pump states
- Need to check if this is read-only or writable

---

## 📊 Correct Register Map

### Control Switches (RW)
| Register | Name | Our Current | Status |
|----------|------|-------------|--------|
| 2012 | System On/Off | ❌ 2002 | FIX NEEDED |
| 2015 | Fast DHW Heating | ✅ Correct | OK |
| 2016 | Additional Source | ✅ Correct | OK |
| 2018 | Reserve Source | ❌ Missing | ADD |
| 2301 | Anti-Legionella | ❌ Missing | ADD |

### Temperature Offsets (Scale 0.1)
| Register | Name | Our Current | Status |
|----------|------|-------------|--------|
| 2014 | Main Temp Correction | ❌ Missing (scale 1!) | ADD |
| 2031 | DHW Offset | ✅ Correct | OK |
| 2041 | System Offset | ❌ Missing | ADD |
| 2048 | Loop 1 Offset | ✅ Correct | OK |
| 2058 | Loop 2 Offset | ✅ Correct | OK |
| 2068 | Loop 3 Offset | ✅ Correct | OK |
| 2078 | Loop 4 Offset | ✅ Correct | OK |
| 2087 | Pool Offset | ❌ Missing | ADD |

### Temperature Setpoints (Scale 0.1)
| Register | Name | Our Current | Status |
|----------|------|-------------|--------|
| 2023 | DHW Setpoint | ✅ Correct | OK |
| 2040 | System Setpoint | ❌ Missing | ADD |
| 2187 | Room 1 Setpoint | ❌ Wrong usage | FIX |

### Current Temperatures (Scale 0.1)
| Register | Name | Our Current | Status |
|----------|------|-------------|--------|
| 2024 | DHW Current Temp | ✅ Correct | OK |
| 2030 | DHW Temp 2 | ❌ Wrong (thought offset) | FIX |
| 2047 | Loop 1 Temp | ❌ Wrong (thought offset) | FIX |
| 2049 | Loop 2 Temp | ✅ Correct | OK |
| 2057 | Loop 2 Temp 2 | ❌ Wrong (thought offset) | FIX |
| 2059 | Loop 3 Temp | ✅ Correct | OK |
| 2067 | Loop 3 Temp 2 | ❌ Wrong (thought offset) | FIX |
| 2069 | Loop 4 Temp | ✅ Correct | OK |
| 2077 | Loop 4 Temp 2 | ❌ Wrong (thought offset) | FIX |
| 2080 | Pool Temp | ❌ Missing | ADD |
| 2101 | Return Temp | ✅ Correct (HP Inlet) | OK |
| 2102 | DHW Tank Temp | ✅ Wrong name | FIX |
| 2103 | Outdoor Temp | ✅ Wrong (used 2102) | FIX |
| 2128 | Loop 1 Circuit Temp | ❌ Missing | ADD |
| 2130 | Loop 1 Alt Temp | ❌ Wrong usage | FIX |

### Operation Modes (RW)
| Register | Name | Our Current | Status |
|----------|------|-------------|--------|
| 2013 | Program Selection | ❌ Missing | ADD |
| 2026 | DHW Mode | ✅ Correct | OK |
| 2035 | Reservoir Mode | ❌ Missing | ADD |
| 2042 | Loop 1 Mode | ✅ Correct | OK |
| 2052 | Loop 2 Mode | ✅ Correct | OK |
| 2062 | Loop 3 Mode | ✅ Correct | OK |
| 2072 | Loop 4 Mode | ✅ Correct | OK |
| 2081 | Pool Mode | ❌ Missing | ADD |

---

## 🔥 CRITICAL FIXES REQUIRED

### Priority 1 - Control Switches
1. **Change system on/off from 2002 → 2012**
2. **Add reserve source switch (2018)**
3. **Add anti-legionella switch (2301)**

### Priority 2 - Temperature Sensors
1. **Fix outdoor temp: 2102 → 2103**
2. **Fix Loop 1 current: Add 2047, 2128, 2130 properly**
3. **Remove offset registers from temp sensor list**
4. **Add 2030 as DHW temp 2 (not offset!)**

### Priority 3 - Offsets
1. **Add main temp correction (2014) with scale=1**
2. **Add system offset (2041)**
3. **Add pool offset (2087)**

### Priority 4 - Setpoints
1. **Add system setpoint (2040)**
2. **Clarify room vs loop setpoints**

### Priority 5 - Additional Sensors
1. **Add pool temperature (2080)**
2. **Add reservoir temps (2034, 2305)**
3. **Add boiler temp (2306)**
4. **Add pressure sensors (2325, 2326)**

---

## 🎯 Implementation Plan

1. **Backup current working integration**
2. **Create corrected modbus_registers.py**
3. **Update switch.py with correct registers**
4. **Update sensor.py with correct temps**
5. **Add new offset entities (main, system, pool)**
6. **Add anti-legionella config (temp, day, minute)**
7. **Test each change incrementally**
8. **Document all changes**

---

## ⚠️ BREAKING CHANGES

Users will need to:
- **Update automations** using old entity names
- **Re-configure dashboards** if entity IDs change
- **Check all offset values** (especially main temp - scale change!)

Consider:
- Migration guide for users
- Deprecation warnings for old entities
- Entity ID preservation where possible
