# Kronoterm Modbus Integration - Working Version

**Date Saved:** 2026-02-03 11:16 GMT+1  
**Status:** ✅ FULLY FUNCTIONAL  
**Git Commit:** 0ea034f

---

## Summary

This is a **working Modbus TCP integration** for Kronoterm heat pumps in Home Assistant. It provides local control as an alternative to the cloud API.

### What Works
- ✅ **35 out of 39 Modbus registers** reading successfully
- ✅ **45 entities created** (30 regular + 14 diagnostic + 1 error/warning)
- ✅ **All diagnostic sensors enabled** by default
- ✅ **Dual mode support** - Cloud API and Modbus can coexist
- ✅ **Auto-update every 5 minutes**

### What's Unavailable (Expected)
- ⚠️ **2-4 registers** return error values (physical sensors not installed on hardware)
- Temperature Compressor Outlet (2106)
- Temperature HP Outlet (2104) 
- Loop 2 Current Temperature (2110)

This is **normal** - these sensors aren't physically present on all heat pump models.

---

## Installation

### 1. Copy Files to Home Assistant
```bash
# Copy the entire custom_components folder
cp -r custom_components/kronoterm /path/to/homeassistant/custom_components/
```

### 2. Restart Home Assistant
```bash
# Via systemd
sudo systemctl restart home-assistant@homeassistant.service

# Or via Docker
docker restart homeassistant
```

### 3. Add Integration
1. Go to **Settings → Devices & Services**
2. Click **"+ Add Integration"**
3. Search for **"Kronoterm"**
4. Select **"Modbus TCP"** connection type
5. Enter:
   - **Host:** Your heat pump IP (e.g., 10.0.0.51)
   - **Port:** 502
   - **Unit ID:** 20 (default for Kronoterm)
   - **Model:** adapt_0416 (or your model)
6. Click **Submit**

### 4. Verify
Wait 5 minutes for first data poll, then check:
- **Settings → Devices & Services → Kronoterm**
- You should see 42-43 entities with values
- 2-3 entities may be unavailable (missing hardware sensors)

---

## Key Files

### Core Integration Files
- **`__init__.py`** - Integration setup and coordinator initialization
- **`manifest.json`** - Integration metadata and dependencies
- **`config_flow.py`** - Setup UI (Cloud API)
- **`config_flow_modbus.py`** - Setup UI (Modbus TCP)
- **`strings.json`** - UI translations

### Modbus Implementation
- **`modbus_coordinator.py`** - Modbus TCP communication coordinator (346 lines)
- **`modbus_registers.py`** - Register definitions (39 registers, 540 lines)

### Entity Platforms
- **`sensor.py`** - Temperature, power, status sensors
- **`binary_sensor.py`** - Pumps, heater status
- **`switch.py`** - Controls (DHW circulation, etc.)
- **`climate.py`** - Loop temperature control
- **`number.py`** - Setpoint adjustments
- **`select.py`** - Mode selection

### Supporting Files
- **`const.py`** - Constants and sensor definitions
- **`coordinator.py`** - Cloud API coordinator
- **`entities.py`** - Base entity classes
- **`energy.py`** - Energy calculation sensors

---

## Register Map (39 Registers)

### Temperature Sensors (14)
- 2102: Outdoor Temperature
- 2109: Loop 1 Current Temperature
- 2187: Loop 1 Setpoint
- 2049: Loop 2 Setpoint
- 2023: DHW Setpoint
- 2024: DHW Current Setpoint
- 2101: HP Inlet Temperature
- 2104: HP Outlet Temperature
- 2105: Evaporating Temperature
- 2106: Compressor Temperature
- 2160: Loop 1 Thermostat Temperature
- 2161: Loop 2 Thermostat Temperature
- 2110: Loop 2 Current Temperature
- 2107: Alternative Source Temperature

### Binary Sensors (7)
- 2000: System Operation
- 2045: Loop 1 Circulation Pump
- 2055: Loop 2 Circulation Pump
- 2028 (bit 0): DHW Circulation Pump
- 2028 (bit 1): DHW Tank Circulation Pump
- 2002 (bit 0): Additional Source Activation
- 2002 (bit 4): Additional Source Active

### Status/Enum Sensors (5)
- 2001: Working Function
- 2006: Error/Warning Status
- 2007: Operation Regime
- 2044: Loop 1 Operation Status
- 2026: DHW Operation

### Power & Load (4)
- 2129: Current Power Consumption
- 2327: Heat Pump Load
- 2329: Current Heating Power
- 2325: System Pressure

### Efficiency (2)
- 2371: COP
- 2372: SCOP

### Operating Hours (3)
- 2090: Operating Hours Compressor Heating
- 2091: Operating Hours Compressor DHW
- 2095: Operating Hours Additional Source

### Activation Counters (4)
- 2155: Compressor Activations Heating
- 2156: Compressor Activations Cooling
- 2157: Activations Boiler
- 2158: Activations Defrost

---

## Error Value Detection

The integration detects when sensors are not connected by checking for error values:
- **64936, 64937** - Sensor not connected
- **65517, 65526** - Sensor error
- **65535** - Invalid/unavailable

When detected, entities show as "unavailable" instead of displaying incorrect data.

---

## Configuration

### Connection Settings
```yaml
host: "10.0.0.51"       # Your heat pump IP
port: 502               # Modbus TCP port (default)
unit_id: 20             # Modbus slave ID (default for Kronoterm)
model: "adapt_0416"     # Your heat pump model
```

### Update Interval
Default: **5 minutes** (300 seconds)

Can be changed in integration options:
1. Go to integration settings
2. Click "Configure"
3. Adjust scan interval

---

## Troubleshooting

### Integration Not Loading
1. Check logs: **Settings → System → Logs**
2. Look for errors containing "kronoterm"
3. Verify IP address and port are correct
4. Ensure heat pump is reachable: `ping 10.0.0.51`

### Entities Unavailable
1. **Check if it's expected** - Some entities are unavailable due to missing hardware sensors
2. **Wait 5 minutes** - First poll happens after initialization
3. **Check coordinator status** in logs - Should see "Successfully read X registers"
4. **Check device in HA** - Settings → Devices → Kronoterm → Check last update time

### Slow Response
- Normal behavior - Modbus reads 39 registers sequentially
- Takes ~1-2 seconds per update cycle
- Don't set update interval below 1 minute

---

## Development Notes

### Pymodbus Version
Home Assistant uses **pymodbus 3.x** which requires `device_id` parameter, not `slave`.

**Correct:**
```python
result = await self.client.read_holding_registers(
    address, count=1, device_id=unit_id
)
```

**Incorrect (will break):**
```python
result = await self.client.read_holding_registers(
    address, count=1, slave=unit_id  # ❌ Wrong!
)
```

### Adding New Registers
1. Add register definition in `modbus_registers.py`
2. Add to appropriate collection (TEMPERATURE_SENSORS, etc.)
3. Add to ALL_REGISTERS list
4. Add sensor definition in `const.py` (if needed)
5. Restart Home Assistant

### Testing Modbus Directly
Use the included test script:
```bash
python3 check-modbus-entities.py
```

---

## Backup

### Files Backed Up
- Full integration in: `backup-working-20260203-111607/`
- Git commit: `0ea034f`
- All modified files saved to workspace

### Restore From Backup
```bash
cd /home/frelih/.openclaw/workspace/kronoterm-integration
cp -r backup-working-20260203-111607/custom_components/kronoterm /path/to/homeassistant/custom_components/
```

---

## Support

### Logs
Check Home Assistant logs for diagnostic info:
```bash
# Via container
docker logs homeassistant | grep kronoterm

# Via file
tail -f /config/home-assistant.log | grep kronoterm
```

### Direct Modbus Test
```bash
python3 check-modbus-entities.py
```

Shows raw register values and connection status.

---

## Version History

- **2026-02-03 11:16** - Initial working version saved
  - 39 registers defined
  - 45 entities created
  - All diagnostic sensors enabled
  - Dual mode (Cloud + Modbus) support

---

**Status: ✅ Ready for Production Use**

All core functionality tested and working. Integration is stable and can be used reliably for local Kronoterm heat pump control.
