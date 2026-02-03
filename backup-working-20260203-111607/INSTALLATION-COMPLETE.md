# ✅ Kronoterm Modbus TCP Integration - Installation Complete!

**Date:** 2026-02-02 21:41 GMT+1  
**Status:** Installed and Ready to Configure

---

## 🎉 Installation Summary

### ✅ What Was Done

1. **Backed up** existing integration → `kronoterm.backup.20260202_*`
2. **Copied** new Modbus integration to `/home/frelih/homeassistant/custom_components/kronoterm/`
3. **Verified** all 4 new files installed:
   - `modbus_coordinator.py` (12K)
   - `modbus_registers.py` (11K)
   - `config_flow_modbus.py` (4.1K)
   - `strings.json` (2.0K)
4. **Restarted** Home Assistant container successfully
5. **Confirmed** HA is running and responding

### 📦 Version Installed

- **Version:** 2.0.0
- **Dependency:** pymodbus==3.5.4
- **IoT Class:** local_polling
- **Connection Types:** Cloud API + Modbus TCP

---

## 🚀 Next Steps: Add Modbus Integration

### Option 1: Add New Modbus Connection (Recommended)

**Steps:**
1. Open Home Assistant UI (http://localhost:8123)
2. Go to **Settings → Devices & Services**
3. Click **"+ Add Integration"** (bottom right)
4. Search for **"Kronoterm"**
5. You'll see a connection type selection:
   - **Cloud API (Internet required)** - Your existing setup
   - **Modbus TCP (Local network)** - ⭐ NEW!
6. Select **"Modbus TCP (Local network)"**
7. Fill in the form:
   ```
   IP Address: 10.0.0.51
   Port: 502
   Modbus Unit ID: 20
   Heat Pump Model: ADAPT 0416
   ```
8. Click **Submit**
9. Integration will:
   - Connect to your heat pump
   - Test read register 2102 (outdoor temp)
   - Fetch device info
   - Create all sensor entities

### Option 2: Keep Cloud API, Test Modbus Later

Your existing cloud API integration will continue to work normally. You can add Modbus as a second integration later for comparison.

---

## 📊 What You'll Get

### Temperature Sensors (14 total)
- ✅ Outdoor Temperature (2102)
- ✅ Loop 1 Current Temperature (2109) ⭐ Corrected!
- ✅ Loop 1 Setpoint (2187)
- ✅ Loop 2 Setpoint (2049)
- ✅ DHW Setpoint (2023)
- ✅ DHW Current Setpoint (2024)
- ✅ Heat Pump Inlet (2101)
- ✅ Heat Pump Outlet (2104)
- ✅ Evaporating Temperature (2105)
- ✅ Compressor Temperature (2106)
- ✅ Loop 1 Thermostat (2160)
- ✅ Loop 2 Thermostat (2161)
- ✅ Loop 2 Current (2110)
- ✅ Alternative Source (2107)

### Binary Sensors (7 total)
- ✅ System Operation (2000)
- ✅ Loop 1 Circulation Pump (2045)
- ✅ Loop 2 Circulation Pump (2055)
- ✅ DHW Circulation Pump (2028 bit 0)
- ✅ DHW Tank Circulation (2028 bit 1)
- ✅ Additional Source Activation (2002 bit 0)
- ✅ Additional Source Active (2002 bit 4)

### Status Sensors (5 total)
- ✅ Working Function (2001) - heating/dhw/cooling
- ✅ Error/Warning Status (2006)
- ✅ Operation Regime (2007)
- ✅ Loop 1 Operation Status (2044)
- ✅ DHW Operation (2026)

### Power & Efficiency Sensors (6 total)
- ✅ Current Power Consumption (2129)
- ✅ Heat Pump Load % (2327)
- ✅ Current Heating Power (2329)
- ✅ System Pressure (2325) ⭐ Corrected!
- ✅ COP (2371)
- ✅ SCOP (2372)

### Operating Hours (3 total)
- ✅ Compressor Heating Hours (2090)
- ✅ Compressor DHW Hours (2091)
- ✅ Additional Source Hours (2095)

### Writable Controls (7 total)
- ✅ DHW Setpoint (2023)
- ✅ Loop 1 Setpoint (2187)
- ✅ Loop 2 Setpoint (2049)
- ✅ Fast DHW Heating (2015)
- ✅ Additional Source Switch (2016)
- ✅ DHW Circulation Switch (2328)
- ✅ DHW Operation Mode (2026)

**Total:** 42 entities!

---

## 🔍 Troubleshooting

### Integration Doesn't Appear in UI

**Check:**
```bash
# Verify files are present
ls -la /home/frelih/homeassistant/custom_components/kronoterm/modbus*

# Check HA logs for errors
sudo docker logs homeassistant --tail 100 | grep -i kronoterm
```

**Solution:**
- Clear browser cache (Ctrl+Shift+R)
- Restart HA again: `sudo docker restart homeassistant`
- Check manifest.json is valid JSON

### "Cannot Connect" Error

**Check:**
```bash
# Test if heat pump is reachable
ping 10.0.0.51

# Test Modbus TCP port
telnet 10.0.0.51 502
# or
nc -zv 10.0.0.51 502
```

**Common Issues:**
- Wrong IP address
- Port 502 blocked by firewall
- Heat pump not on same network
- Wrong Unit ID (try 1, 10, 20)

### "Cannot Read" Error

**Meaning:** Connection succeeded but couldn't read register 2102

**Solutions:**
1. Try different Unit ID (1, 10, 20, 247)
2. Check if Modbus TCP is enabled on heat pump
3. Verify device supports holding registers
4. Check HA logs for detailed error

### Sensors Show "Unknown" or "Unavailable"

**Normal for:**
- Loop 2 sensors (if Loop 2 not installed)
- Pool sensors (if pool not installed)
- Alternative source (if not installed)

**Check logs:**
```bash
# Enable debug logging (configuration.yaml)
logger:
  logs:
    custom_components.kronoterm: debug
    pymodbus: debug
```

---

## 📚 Documentation

**In workspace:**
- `IMPLEMENTATION-SUMMARY.md` - What we built
- `MODBUS-IMPLEMENTATION-STATUS.md` - Testing plan
- `CORRECTED-REGISTER-MAP.md` - All registers
- `kronoterm-status.md` - Quick status

**Read first:** IMPLEMENTATION-SUMMARY.md

---

## 🔄 Comparing Cloud vs Modbus

### Cloud API (Existing)
✅ No configuration needed  
✅ Works from anywhere  
❌ Requires internet  
❌ Slower updates (~60s)  
❌ Depends on cloud service

### Modbus TCP (New!)
✅ Local network only  
✅ Faster updates (5-60s configurable)  
✅ Works offline  
✅ Direct hardware access  
❌ Requires local network access  
❌ Needs model selection for energy calc

### Hybrid (Both!)
✅ Best of both worlds  
✅ Cloud for remote access  
✅ Modbus for local speed  
✅ Automatic failover

---

## 🎯 Recommended Setup

**For best results:**

1. **Keep existing cloud integration** (for remote access)
2. **Add Modbus TCP integration** (for local control)
3. **Compare sensor values** (should match within ±0.5°C)
4. **Use Modbus for automations** (faster response)
5. **Keep cloud as backup** (if Modbus fails)

**Scan intervals:**
- Cloud API: 60 seconds (default)
- Modbus TCP: 30-60 seconds (configurable)

---

## ✅ Validation Checklist

After adding the integration:

- [ ] Integration shows in Devices & Services
- [ ] Device shows correct model (ADAPT 0416)
- [ ] All temperature sensors reading values
- [ ] Values match cloud API (±0.5°C tolerance)
- [ ] Binary sensors show correct states
- [ ] No errors in HA logs
- [ ] Can change DHW setpoint
- [ ] Can toggle DHW circulation switch
- [ ] COP shows reasonable value (4-8 typical)
- [ ] System pressure shows ~1.7 bar

---

## 🆘 Need Help?

**Check logs:**
```bash
# In Home Assistant
Settings → System → Logs
Search for: kronoterm

# Or via command line
sudo docker logs homeassistant | grep -i kronoterm
```

**Common log patterns:**
```
✅ Good: "Successfully connected to Modbus device"
✅ Good: "Successfully read X registers from Modbus"
❌ Bad: "Failed to connect to Modbus device"
❌ Bad: "Modbus Error: [Input/Output]"
⚠️  Warning: "Register X returned error value"
```

---

## 🎉 Success Indicators

**You'll know it's working when:**

1. ✅ Integration shows as "Kronoterm ADAPT 0416 (Modbus)"
2. ✅ Device page shows ~42 entities
3. ✅ Temperature sensors update every 60s
4. ✅ Outdoor temp matches your weather
5. ✅ Loop 1 current temp matches thermostat
6. ✅ System pressure shows 1-2 bar
7. ✅ COP shows 4-8 (normal operating range)
8. ✅ Pump sensors show ON when running
9. ✅ No errors in logs
10. ✅ Changing setpoint works and updates immediately

---

**Ready to test!** 🚀

Open Home Assistant UI and add the integration following the steps above.

Good luck! Let me know if you encounter any issues.

---

**Installation completed:** 2026-02-02 21:41 GMT+1  
**Installed by:** Claw 🦾  
**Status:** Ready for configuration
