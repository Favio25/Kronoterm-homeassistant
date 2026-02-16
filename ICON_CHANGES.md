# Heat Source Icon Changes

**Date:** 2026-02-16  
**Status:** ✅ Implemented

---

## Summary

Changed heat source binary sensor icons to make them visually distinct and semantically correct.

---

## Changes

| Entity | Old Icon | New Icon | Reasoning |
|--------|----------|----------|-----------|
| **Reserve Source Status** | `mdi:fire` 🔥 | `mdi:heating-coil` ⚡ | Internal electric heater (built-in) |
| **Additional Source** | `mdi:fire` 🔥 | `mdi:gas-burner` 🔥 | External backup boiler (oil/gas/pellet) |
| **Alternative Source Status** | `mdi:fire-circle` 🔥 | `mdi:solar-power` ☀️ | Renewable energy (solar, wood stoves) |

---

## Before

All three heat sources used fire-related icons, making them hard to distinguish:
- Reserve Source: 🔥
- Additional Source: 🔥
- Alternative Source: 🔥 (with circle)

**Problem:** Users couldn't quickly tell which source was which in dashboards.

---

## After

Each heat source has a distinctive icon that represents its function:
- **Reserve Source:** ⚡ Electric heating coil (clearly internal/electric)
- **Additional Source:** 🔥 Gas burner (clearly external boiler)
- **Alternative Source:** ☀️ Solar power (clearly renewable/alternative)

**Benefit:** Instant visual identification in dashboards and cards.

---

## Visual Comparison

```
Before:
┌─────────────────────────┐
│ 🔥 Reserve Source: ON   │
│ 🔥 Additional Source: OFF│
│ 🔥 Alternative Source: ON│
└─────────────────────────┘
↑ Confusing! All look the same

After:
┌─────────────────────────┐
│ ⚡ Reserve Source: ON   │
│ 🔥 Additional Source: OFF│
│ ☀️ Alternative Source: ON│
└─────────────────────────┘
↑ Clear! Each has distinct purpose
```

---

## Files Modified

- `custom_components/kronoterm/binary_sensor.py` - Updated icon definitions

---

## What Each Source Does

### ⚡ Reserve Source (mdi:heating-coil)
- **Type:** Internal electric heater (built into heat pump)
- **Purpose:** Emergency heating during failures, bivalent operation assist
- **Control:** Heat pump controlled (can enable/disable)
- **Icon rationale:** Heating coil = electric heating element

### 🔥 Additional Source (mdi:gas-burner)
- **Type:** External backup boiler (oil/gas/pellet)
- **Purpose:** Parallel or alternative heating, backup during failures
- **Control:** Heat pump controlled (automatic switching)
- **Icon rationale:** Gas burner = external heating source

### ☀️ Alternative Source (mdi:solar-power)
- **Type:** Renewable energy (solar collectors, wood stoves, fireplaces)
- **Purpose:** Supplemental heat when available (not always on)
- **Control:** Manual or external conditions (NOT heat pump controlled)
- **Icon rationale:** Solar power = renewable/alternative energy

---

## User Impact

**Existing users:** Icons will update automatically after restart. No configuration needed.

**Dashboard visibility:** Improved at-a-glance recognition of which heat sources are active.

**Learning curve:** New users will immediately understand the system better.

---

## Additional Icon Resources

If users want to customize further, here are some alternatives:

**Reserve Source alternatives:**
- `mdi:flash` - Electric flash
- `mdi:lightning-bolt-circle` - Electric power symbol
- `mdi:heating-coil` - (current choice) ✅

**Additional Source alternatives:**
- `mdi:fire-circle` - Fire in circle
- `mdi:water-boiler` - Water heating boiler
- `mdi:gas-burner` - (current choice) ✅

**Alternative Source alternatives:**
- `mdi:solar-panel` - Solar panel specifically
- `mdi:fireplace` - Wood stove/fireplace
- `mdi:leaf` - Eco/renewable
- `mdi:solar-power` - (current choice) ✅

Users can customize in Developer Tools → States by clicking an entity and editing the icon field.

---

## Next Steps

After restart, verify icons appear correctly:
1. Check Developer Tools → States
2. Search for binary sensors: reserve_source, additional_source, alternative_source
3. Confirm new icons display properly in dashboards

---

**Status:** ✅ Changes deployed, restart in progress
