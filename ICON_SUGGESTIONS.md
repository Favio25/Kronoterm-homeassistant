# Entity Icon Suggestions

Current icons are mostly good! Here are some suggestions for improvements:

---

## 🔥 Heat Sources

### Current
- Reserve Source: `mdi:fire`
- Additional Source: `mdi:fire`
- Alternative Source: `mdi:fire-circle`

### Suggested
```python
# Reserve Source (internal electric heater)
BinarySensorConfig(2003, "reserve_source_status", icon="mdi:heating-coil")  # or mdi:flash

# Additional Source (external backup boiler)
BinarySensorConfig(2002, "additional_source", bit=0, icon="mdi:gas-burner")  # or mdi:fire-circle

# Alternative Source (solar/wood/renewable)
BinarySensorConfig(2004, "alternative_source_status", icon="mdi:solar-power")  # or mdi:fireplace
BinarySensorConfig(2088, "alternative_source_pump", icon="mdi:pump")  # keep as pump
```

**Reasoning:**
- `mdi:heating-coil` - looks like electric heating element
- `mdi:gas-burner` - clearly external boiler/burner
- `mdi:solar-power` - renewable/alternative energy

Alternative options:
- Reserve: `mdi:flash` (electric), `mdi:lightning-bolt-circle`
- Additional: `mdi:fire-circle`, `mdi:water-boiler`
- Alternative: `mdi:fireplace`, `mdi:solar-panel`, `mdi:leaf`

---

## 💧 Pumps

### Current
All pumps use `mdi:pump` (good, but no differentiation)

### Suggested
```python
# Main circulation pump (primary system pump)
BinarySensorConfig(2038, "main_pump_status", icon="mdi:pump")

# Loop circulation pumps (smaller, zone-specific)
BinarySensorConfig(2045, "circulation_loop_1", icon="mdi:pump-off")  # when off shows differently
# or
BinarySensorConfig(2045, "circulation_loop_1", icon="mdi:water-pump")

# DHW/circulation pumps
BinarySensorConfig(2033, "circulation_pump", icon="mdi:pump")
BinarySensorConfig(2034, "dhw_circulation_pump", icon="mdi:water-pump")
```

**Reasoning:**
- Main pump stays `mdi:pump` (most important)
- Loop pumps could use `mdi:water-pump` (smaller/secondary)
- Or keep all `mdi:pump` for consistency (current is fine)

**Recommendation:** Keep current `mdi:pump` for all - consistency is better than visual variety here.

---

## ❄️ Compressor & System

### Current
```python
# Compressor temperatures
temperature_compressor_inlet: "mdi:thermometer"
temperature_compressor_outlet: "mdi:thermometer"

# Compressor load/status
compressor_status: (no icon set?)
hp_load: "mdi:engine"
```

### Suggested
```python
# Compressor-specific icon
temperature_compressor_inlet: "mdi:thermometer-chevron-down"  # intake
temperature_compressor_outlet: "mdi:thermometer-chevron-up"  # output
hp_load: "mdi:gauge-full"  # or keep mdi:engine
```

---

## 🌡️ Temperature Sensors

### Current (Good!)
- Outdoor: `mdi:thermometer` or `mdi:weather-sunny`
- Water/DHW: `mdi:water-thermometer`
- Supply/Outlet: `mdi:thermometer-chevron-up`
- Return/Inlet: `mdi:thermometer-chevron-down`
- Thermostat: `mdi:thermostat`

**Recommendation:** Keep as-is! Well differentiated.

### One improvement:
```python
# Outdoor temperature
outdoor_temperature: "mdi:home-thermometer-outline"  # makes it clear it's for the house/system
```

---

## ⚡ Energy & Power

### Current (Perfect!)
- Power: `mdi:lightning-bolt`
- Energy: `mdi:meter-electric`
- COP/SCOP: `mdi:chart-line`

**Recommendation:** Keep as-is!

---

## 🔧 System Status

### Current
- Pressure: `mdi:gauge`
- Operating hours: `mdi:timer-outline`
- Defrost: `mdi:snowflake-melt` ✅ Perfect!

### Suggested addition
```python
# System operation/working function
system_operation: "mdi:power"  # on/off switch visual
working_function: "mdi:cog"  # mode/function selection

# Error/warning status
error_warning: "mdi:alert-circle"  # or mdi:alert-octagon

# Vacation mode
vacation_mode: "mdi:island"  # or mdi:beach
```

---

## 📊 Summary: Recommended Changes

### High Priority (Clear Visual Improvements)
1. **Reserve Source:** `mdi:fire` → `mdi:heating-coil` (electric heater)
2. **Additional Source:** `mdi:fire` → `mdi:gas-burner` (external boiler)
3. **Alternative Source:** `mdi:fire-circle` → `mdi:solar-power` (renewable)

### Medium Priority (Nice to Have)
4. **Outdoor temp:** `mdi:thermometer` → `mdi:home-thermometer-outline`
5. **Error status:** Add `mdi:alert-circle`
6. **Vacation mode:** Add `mdi:island`

### Low Priority (Optional)
7. Loop pumps: Consider `mdi:water-pump` vs `mdi:pump`

---

## Implementation

To change binary sensor icons, edit `custom_components/kronoterm/binary_sensor.py`:

```python
BINARY_SENSOR_DEFINITIONS: List[BinarySensorConfig] = [
    # Heat sources with distinctive icons
    BinarySensorConfig(2003, "reserve_source_status", icon="mdi:heating-coil"),
    BinarySensorConfig(2004, "alternative_source_status", icon="mdi:solar-power"),
    BinarySensorConfig(2002, "additional_source", bit=0, icon="mdi:gas-burner"),
    # ... rest stay the same
]
```

For other sensors, icons are auto-assigned in `sensor.py` via `_get_icon_for_register()` function.

---

## Material Design Icons Reference

Browse all available icons: https://pictogrammers.com/library/mdi/

Useful heat pump related icons:
- `mdi:heating-coil` - electric heating element
- `mdi:gas-burner` - gas/boiler
- `mdi:solar-power` - solar/renewable
- `mdi:water-boiler` - water heating
- `mdi:heat-pump` - generic heat pump (consider for main device)
- `mdi:heat-pump-outline` - outlined version
- `mdi:home-thermometer` - house temperature
- `mdi:water-thermometer` - water temperature
- `mdi:thermometer-lines` - generic temp with lines
- `mdi:pump` - circulation pump
- `mdi:water-pump` - water pump specifically

---

**Question:** Would you like me to implement the heat source icon changes? They're the most impactful visual improvements.
