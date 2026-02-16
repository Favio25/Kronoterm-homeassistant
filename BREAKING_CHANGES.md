# Breaking Changes - v1.5.0

## ⚠️ Modbus Entity Names & Unique IDs Unified with Cloud API

**Affects:** Users running Modbus TCP mode only  
**Impact:** Entity IDs will change, historical data will NOT be preserved

### Two Types of Changes

1. **Entity Names** - Translation keys unified (affects entity_id)
2. **Unique IDs** - Internal ID format unified (fixes duplicate entities on reconfigure)

### Why This Change?

- Eliminates duplicate entities when reconfiguring between Cloud API ↔ Modbus
- Aligns Modbus naming with official Kronoterm Cloud API
- Creates single source of truth for entity names

### Changed Entity IDs (Modbus Only)

After updating to v1.5.0, these entity IDs will change:

| Old Entity ID | New Entity ID |
|---------------|---------------|
| `sensor.kronoterm_error_status` | `sensor.kronoterm_error_warning` |
| `sensor.kronoterm_operation_mode` | `sensor.kronoterm_operation_regime` |
| `sensor.kronoterm_operating_hours_heating` | `sensor.kronoterm_operating_hours_compressor_heating` |
| `sensor.kronoterm_operating_hours_dhw` | `sensor.kronoterm_operating_hours_compressor_dhw` |
| `sensor.kronoterm_operating_hours_heater_1` | `sensor.kronoterm_operating_hours_additional_source_1` |
| `sensor.kronoterm_return_temperature` | `sensor.kronoterm_hp_inlet_temperature` |
| `sensor.kronoterm_outdoor_temperature` | `sensor.kronoterm_temperature_outside` |
| `sensor.kronoterm_supply_temperature` | `sensor.kronoterm_hp_outlet_temperature` |
| `sensor.kronoterm_evaporation_temperature` | `sensor.kronoterm_temperature_compressor_inlet` |
| `sensor.kronoterm_compressor_temperature` | `sensor.kronoterm_temperature_compressor_outlet` |
| `sensor.kronoterm_current_power_consumption` | `sensor.kronoterm_current_heating_cooling_capacity` |
| `sensor.kronoterm_system_pressure_setting` | `sensor.kronoterm_heating_system_pressure` |
| `sensor.kronoterm_cop` | `sensor.kronoterm_cop_value` |
| `sensor.kronoterm_scop` | `sensor.kronoterm_scop_value` |

### What You Need to Do

1. **Update the integration** to v1.5.0
2. **Reload the integration:** Settings → Devices & Services → Kronoterm → ⋮ → Reload
3. **Update your dashboards/automations** to use the new entity IDs
4. **Clean up old entities:**
   - Settings → Devices & Services → Entities
   - Filter by "kronoterm"
   - Delete unavailable entities with old names

### What Will Happen

- ✅ Integration continues working immediately
- ✅ New entities appear with correct names
- ❌ Old entities become "unavailable"
- ❌ Historical data remains tied to old entity IDs (orphaned but not deleted)
- ❌ Dashboards referencing old entity IDs will show "Entity not available"

### Migration Note

**Historical data is NOT migrated automatically.** If you need to preserve specific long-term statistics (COP trends, operating hours), consider:

1. Taking screenshots of important graphs before updating
2. Exporting data via Home Assistant's history export
3. Advanced users: Manual entity_id rename in `.storage/core.entity_registry` (risky, backup first)

### Critical Bug Fixes in v1.5.0

**❗ MAJOR FIX:** Eliminated duplicate entities on Cloud ↔ Modbus reconfigure

- **All switches duplicating** → Fixed! (unique_id format unified)
- **All sensors duplicating** → Fixed! (unique_id format unified)
- **20+ duplicate entities after reconfigure** → Now zero duplicates!

Before v1.5.0:
- Reconfiguring Cloud → Modbus created 20+ duplicate entities
- User had to manually delete old entities
- Lost entity history on reconfigure

After v1.5.0:
- Reconfigure preserves entities (same unique_id)
- No manual cleanup needed
- History preserved across modes

### New Features in v1.5.0

- ✅ **Defrost Status** sensor now available (`sensor.kronoterm_defrost_status`)
- ✅ No more duplicate entities when switching Cloud ↔ Modbus
- ✅ Entity naming consistency across all modes

---

**If you're happy with your Cloud API setup, this change does NOT affect you.**

**For Modbus users:** This update is CRITICAL - it fixes completely broken temperature readings.
