# Fix Applied - Restart Home Assistant

**Date:** 2026-02-03 10:27 GMT+1  
**Status:** Critical bug fixed, restart required

---

## 🐛 Bug Found and Fixed

### Issue
The ModbusCoordinator was using incorrect parameter name `device_id=` for pymodbus calls.

**Error:** `ModbusClientMixin.read_holding_registers() got an unexpected keyword argument 'device_id'`

### Fix Applied
Changed parameter name from `device_id=` to `slave=` in:
1. `_read_register()` method (line 265)
2. `write_register()` method (line 298)

**Files modified:**
- `custom_components/kronoterm/modbus_coordinator.py`

---

## ✅ Verification Test Results

Tested all 35 Modbus registers directly:

```
✅ Successful reads: 33/35
⚠️  Error values: 2/35 (sensors not connected - normal)
❌ Failed reads: 0/35
```

**Working sensors include:**
- Outdoor Temperature: 3.8°C ✅
- Loop 1 Current: 38.5°C ✅
- Loop 1 Setpoint: 28.3°C ✅
- DHW Setpoint: 44.0°C ✅
- HP Inlet: 43.1°C ✅
- HP Load: 0% ✅
- Working Function: heating ✅
- System Pressure: 1.7 bar ✅
- COP: 7.91 ✅
- Operating Hours: 3897h ✅

**Sensors with error values (not connected):**
- 2106: Compressor Temperature (ERROR 64936)
- 2110: Loop 2 Current Temperature (ERROR 64936)

These will show as unavailable, which is correct behavior.

---

## 🚀 Next Steps

### **Restart Home Assistant**

Run this command:
```bash
sudo systemctl restart home-assistant@frelih.service
```

### **Then check the integration:**

1. Go to: **Settings → Devices & Services**
2. Find: **Kronoterm** (Modbus)
3. Check that entities are now showing values
4. Look for entities like:
   - `sensor.kronoterm_temperature_outside`
   - `sensor.kronoterm_hp_load`
   - `sensor.kronoterm_working_function`
   - `sensor.kronoterm_cop_value`

---

## 📊 Expected Result

After restart, you should see:
- ✅ 33 entities with values
- ⚠️  2 entities unavailable (sensors not connected)
- ✅ No errors in logs
- ✅ Data updating every 5 minutes

---

**Ready to restart!** 🦾
