# Climate Entity Temperature Mapping (Modbus)

## Overview
Modbus climate entities now properly map current and target temperatures according to Kronoterm register structure.

## Temperature Sensor Priority

### Current Temperature (what user sees)
Climate entities use this priority:
1. **Thermostat Temperature** (if installed and reading valid value)
2. **Loop Temperature** (fallback if no thermostat)

This allows the climate entity to show room temperature when a thermostat is connected, or loop/outlet temperature when operating without a thermostat.

### Target Temperature
- **Read from:** `loop_x_room_current_setpoint` (current active setpoint)
- **Write to:** `loop_x_room_setpoint` or `loop_x_setpoint` (user adjustment)

## Register Mapping

### DHW (Domestic Hot Water)
- **Current temp:** `2102` (dhw_temperature)
- **Target temp (read):** `2024` (dhw_current_setpoint)
- **Target temp (write):** `2023` (dhw_setpoint)
- **Thermostat:** N/A (no thermostat for DHW)

### Loop 1
- **Current temp:** `2130` (loop_1_temperature)
- **Thermostat temp:** `2160` (loop_1_thermostat_temperature) — **preferred**
- **Target temp (read):** `2191` (loop_1_room_current_setpoint)
- **Target temp (write):** `2187` (loop_1_room_setpoint)

### Loop 2
- **Current temp:** `2110` (loop_2_temperature)
- **Thermostat temp:** `2161` (loop_2_thermostat_temperature) — **preferred**
- **Target temp (read):** `2051` (loop_2_room_current_setpoint)
- **Target temp (write):** `2049` (loop_2_setpoint)

### Loop 3
- **Current temp:** `2111` (loop_3_temperature)
- **Thermostat temp:** `2162` (loop_3_thermostat_temperature) — **preferred**
- **Target temp (read):** `2061` (loop_3_room_current_setpoint)
- **Target temp (write):** `2059` (loop_3_setpoint)

### Loop 4
- **Current temp:** `2112` (loop_4_temperature)
- **Thermostat temp:** `2163` (loop_4_thermostat_temperature) — **preferred**
- **Target temp (read):** `2071` (loop_4_room_current_setpoint)
- **Target temp (write):** `2069` (loop_4_setpoint)

### Reservoir
- **Current temp:** `2101` (return_temperature) — uses system return temp
- **Thermostat temp:** N/A (no thermostat for reservoir)
- **Target temp (read):** `2034` (reservoir_current_setpoint)
- **Target temp (write):** `2305` (solar_reservoir_setpoint)

## Implementation Details

### Base Class: `KronotermModbusBaseClimate`
New base class for all Modbus climate entities with:
- Automatic thermostat temperature preference with loop temp fallback
- Direct register addressing (no page-based abstraction)
- Proper temperature scaling (× 10 for Modbus format)
- Invalid temperature filtering (-60.0°C = sensor error)

### New Method: `async_write_register(address, temperature)`
Added to ModbusCoordinator:
```python
async def async_write_register(self, address: int, temperature: float) -> bool:
    """Write temperature value with automatic scaling (× 10)."""
```

## Benefits
✅ Proper room temperature display when thermostat is installed  
✅ Automatic fallback to loop temperature when no thermostat  
✅ Direct register access (faster, simpler)  
✅ Consistent with Kronoterm manual register definitions  
✅ Error handling for invalid sensor readings  

## Testing Checklist
- [ ] Loop with thermostat shows room temperature
- [ ] Loop without thermostat shows loop temperature
- [ ] Setting temperature writes to correct register
- [ ] Temperature changes reflected after coordinator refresh
- [ ] Invalid temps (-60.0) filtered out properly
- [ ] DHW climate entity works (no thermostat option)
