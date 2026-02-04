# Modbus JSON-Based Implementation

## Overview

The Modbus TCP integration now uses the official Kronoterm register mapping from `kronoterm.json` as the single source of truth for all entities. This eliminates hardcoded register definitions and makes the integration easier to maintain and extend.

## Architecture

### Components

1. **kronoterm.json** - Official register mapping from Kronoterm manual
   - Document: 17-20-28-4022-04
   - Controller: KSM V3.14-1
   - 168 registers total

2. **register_map.py** - Register map loader
   - Parses JSON into structured RegisterDefinition objects
   - Translates Slovenian names to English snake_case
   - Extracts scaling factors and units
   - Provides filtered accessors (sensors, controls, bitmasks)

3. **modbus_coordinator.py** - Enhanced to load register map
   - Loads JSON on initialization
   - Stores RegisterMap for entities to use
   - Maintains backward compatibility with existing modbus_registers.py

4. **sensor.py** - Auto-generates entities
   - Detects if coordinator has register_map
   - Modbus: Auto-generates entities from JSON
   - Cloud API: Uses hardcoded SENSOR_DEFINITIONS (unchanged)

### Data Flow

```
kronoterm.json
    ↓
RegisterMap.load()
    ↓
ModbusCoordinator.register_map
    ↓
sensor.py detects register_map
    ↓
Auto-generate entities:
  - KronotermModbusRegSensor (numeric values)
  - KronotermEnumSensor (enumerations)
```

## Register Statistics

- **Total registers:** 168
- **Readable sensors:** 115
- **Writable controls:** 23
- **Bitmask registers:** 30

### By Category
- **Temperature sensors:** 61 (all with 0.1°C scaling)
- **Operating hours:** ~10 registers
- **Status/Enum:** ~20 registers
- **Energy counters:** 4 (32-bit pairs)
- **Pumps/Compressors:** ~15 status registers

## Key Features

### Automatic Scaling
Temperature registers with "x 0.1°C" automatically scaled by 0.1:
- 2103: Outdoor temperature
- 2102: DHW temperature  
- 2101: Return temperature
- 2104: Supply temperature
- 2023: DHW setpoint
- 2187: Loop 1 room setpoint

### Icon Assignment
Automatic icon selection based on register type:
- Temperature → `mdi:thermometer` (with variants)
- Power → `mdi:lightning-bolt`
- Energy → `mdi:meter-electric`
- Pressure → `mdi:gauge`
- Pumps → `mdi:pump`
- Compressor → `mdi:engine`

### Device/State Classes
Automatic HA class assignment:
- Temperature → `TEMPERATURE` + `MEASUREMENT`
- Energy → `ENERGY` + `TOTAL`
- Power → `POWER` + `MEASUREMENT`
- Pressure → `PRESSURE` + `MEASUREMENT`
- Duration → `DURATION` + `TOTAL_INCREASING`

### Diagnostic Entities
Auto-detected based on keywords:
- Operating hours
- Activations/counters
- COP/SCOP
- Alarms/errors

## Cloud API Compatibility

**Cloud API integration remains unchanged:**
- Still uses hardcoded `SENSOR_DEFINITIONS` in const.py
- All existing cloud API entities work as before
- No breaking changes to cloud API users

**Detection logic:**
```python
use_register_map = hasattr(coordinator, "register_map") and coordinator.register_map is not None
```

## Translation Layer

Basic Slovenian → English translation implemented:
- "Zunanja temperatura" → "outdoor_temperature"
- "Temperatura sanitarne vode" → "dhw_temperature"
- "Status obtočne črpalke" → "pump_status"

**Fallback:** Simple snake_case conversion for untranslated names.

## Testing

### Verify JSON Loading
```bash
cd custom_components/kronoterm
python3 -c "from register_map import RegisterMap; from pathlib import Path; rm = RegisterMap(Path('kronoterm.json')); print(f'Loaded {len(rm.get_all())} registers')"
```

### Check Temperature Registers
```python
from register_map import RegisterMap
from pathlib import Path

reg_map = RegisterMap(Path('kronoterm.json'))
for reg in reg_map.get_all():
    if reg.unit == '°C':
        print(f'{reg.address}: {reg.name_en} (scale={reg.scale})')
```

## Next Steps

1. **Test with live system** - Deploy to HA and verify entities load
2. **Add missing translations** - Extend translation dictionary
3. **Handle 32-bit registers** - Combine high/low pairs for energy counters
4. **Add binary_sensor platform** - For bitmask registers
5. **Add number/select platforms** - For writable controls
6. **Documentation** - Update README with new entity list

## Benefits

✅ **Single source of truth** - Official manual drives integration  
✅ **Easy to extend** - Just update JSON, no code changes  
✅ **Consistent naming** - Auto-generated from official docs  
✅ **Automatic scaling** - No manual register definitions  
✅ **Cloud API untouched** - No breaking changes  
✅ **Future-proof** - Easy to support new models/firmware  

## Files Changed

- ✅ `kronoterm.json` - Added official register map
- ✅ `register_map.py` - New module for JSON parsing
- ✅ `modbus_coordinator.py` - Load register map on init
- ✅ `sensor.py` - Auto-generate Modbus entities from JSON
- ⚠️ `const.py` - Unchanged (still used for Cloud API)
- ⚠️ `modbus_registers.py` - Still used for write operations
