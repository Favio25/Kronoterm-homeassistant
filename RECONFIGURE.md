# Reconfigure Flow - Switch Between Cloud & Modbus

## Overview

The Kronoterm integration now supports **seamless switching** between Cloud API and Modbus TCP connections **without losing entity history, customizations, or dashboard references**.

## Why This Matters

Previously, switching connection types required:
1. Delete Cloud integration → lose all entity IDs
2. Add Modbus integration → create new entity IDs
3. Result: Lost history, broken dashboards, reset customizations

Now with **Reconfigure Flow**:
- ✅ Keep the same entity IDs
- ✅ Preserve all historical data
- ✅ Maintain dashboard references
- ✅ Retain entity customizations (names, icons, areas)
- ✅ Keep automation/script references working

## How to Use

### Via Home Assistant UI

1. Go to **Settings** → **Devices & Services**
2. Find your **Kronoterm** integration
3. Click the **⋮** (three dots menu)
4. Select **Reconfigure**
5. Choose new connection type:
   - **Cloud** → Enter username/password
   - **Modbus** → Enter IP, port, unit ID, model
6. Click **Submit**
7. Integration reloads automatically with new connection
8. All entities remain unchanged!

### What Gets Preserved

When you reconfigure:
- ✅ **Device** stays the same (no duplicate device entries)
- ✅ **Entity IDs** stay the same (e.g., `sensor.outdoor_temp`)
- ✅ **Historical data** remains intact
- ✅ **Entity customizations** (friendly names, icons, hidden status)
- ✅ **Area assignments** 
- ✅ **Dashboard cards** keep working
- ✅ **Automations/scripts** keep working
- ✅ **Statistics** and **energy dashboard** data

### What Gets Updated

- ✅ **Connection type** (cloud ↔ modbus)
- ✅ **Connection settings** (credentials or IP/port)
- ✅ **Integration title** in UI

## Technical Details

### How It Works

The reconfigure flow uses `async_update_entry()` instead of creating a new config entry:

```python
# Preserves entry_id
self.hass.config_entries.async_update_entry(
    self.reconfig_entry,
    data=new_config,
    title=new_title
)

# Reloads with new settings
await self.hass.config_entries.async_reload(entry_id)
```

### Entity and Device Unique IDs

**Entity unique IDs** include the config entry ID:
```python
f"{coordinator.config_entry.entry_id}_{DOMAIN}_modbus_{address}"
```

**Device identifier** also uses the config entry ID:
```python
"identifiers": {(DOMAIN, config_entry.entry_id)}
```

Since the `entry_id` doesn't change during reconfiguration, both the device and all entity unique IDs remain stable. This ensures:
- No duplicate devices when switching connection types
- All entities remain associated with the same device
- Device-level customizations are preserved

## Use Cases

### 1. Testing Local Control
- Start with Cloud API (easy setup)
- Switch to Modbus TCP to test local control
- Switch back to Cloud if needed
- No data loss at any point

### 2. Moving to Local-Only
- Run both Cloud and Modbus for comparison
- When confident, reconfigure Cloud → Modbus
- Keep all historical data for comparison

### 3. Network Changes
- Switch between connection types based on network topology
- No need to delete/recreate integration

## Validation

The reconfigure flow validates connections before applying:
- **Cloud:** Tests authentication with API
- **Modbus:** Tests TCP connection and reads test register

If validation fails, your existing configuration remains unchanged.

## Troubleshooting

### "Failed to connect" Error
- **Cloud:** Check username/password
- **Modbus:** Check IP address, port (502), and unit ID (20)
- **Both:** Check network connectivity

### Entities Show "Unavailable" After Reconfigure
- Normal during reload (takes 5-30 seconds)
- If persists: Check new connection settings
- Reconfigure again with correct settings

### Lost Customizations
- Shouldn't happen with reconfigure flow
- If it does, report as bug with logs

## Comparison: Delete/Add vs Reconfigure

| Aspect | Delete/Add | Reconfigure |
|--------|-----------|-------------|
| Entity IDs | ❌ Changed | ✅ Preserved |
| Historical data | ❌ Lost | ✅ Kept |
| Customizations | ❌ Reset | ✅ Kept |
| Dashboards | ❌ Break | ✅ Work |
| Automations | ❌ Break | ✅ Work |
| Process | 2 steps | 1 step |

## Future Enhancements

Potential additions:
- Support reconfiguring Modbus settings (IP/port) without switching types
- Support reconfiguring Cloud credentials without switching types
- Add "Test Connection" button before applying changes

## Related Files

- `config_flow.py` - Implements reconfigure flow
- `strings.json` - UI text for reconfigure dialogs
- `__init__.py` - Handles config entry updates and reloads

## Version

Added in: **v2.0.0** (JSON implementation update)
