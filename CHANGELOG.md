# Changelog

## Unreleased (since v1.6.3)

### Added
- **TT3000 support**: Auto-detect Modbus register set (extended vs TT3000) and load matching JSON map
- TT3000 register map file (`kronoterm_tt3000.json`)
- TT3000 loop temperature mapping (buffer tank + loop temps, no thermostat)
- TT3000: passive cooling temperature register (2108)
- TT3000: missing registers from PDF (status/commands/ops/temps)
- BasicAuth handshake retry logic: 3 retry attempts with exponential backoff (1.5s, 3s) for transient connection failures
- Missing coordinator method: `async_set_additional_source()` for additional_source switch
- Modbus switch optimistic updates: instant UI feedback after write (updates both `value` and `raw` in coordinator data)

### Fixed
- **Modbus power sensor calculation**: Register 2129 (`current_heating_cooling_power`) now reads directly from Modbus register; calculation from capacity/COP only applies to cloud integration
- TT3000: loop 4 operation mode uses register 2074
- TT3000: hide switches for registers not present (antilegionella 2301, DHW circulation 2328)
- TT3000: reservoir write uses register 2032
- NoneType errors in entity setup: double guards in `binary_sensor.py` and `number.py`
- Cloud main temperature offset: use correct `param_name="main_temp"` and `page=-1`
- DHW climate HVAC modes: all three DHW climate classes now correctly show only `[HEAT, OFF]` modes

### Changed
- Merged upstream PR #47: added new `working_function` states (`6: "start"`, `8: "protection"`)
- BasicAuth retry logs at DEBUG level (reduced noise)

## 2026-03-14 — v1.6.3

### Added
- Energy statistics maintenance:
  - Daily auto re-import of **yesterday’s** energy statistics
  - **Reimport Energy Statistics** button (rebuilds full history)
- Modbus RTU support (transport selection + serial config flow)

### Fixed
- Energy statistics import pipeline:
  - Use **30‑day daily totals** from Kronoterm consumption API
  - Import **chronologically** with monotonic cumulative sums
  - Avoid duplicate-day imports across overlapping windows
  - Robust handling of timestamps/metadata for recorder statistics
- Operational mode select (cloud + modbus) and read fallback
- Restored cloud heatpump on/off shortcut
- Disabled DHW external source temperature sensor

## 2026-03-09 — v1.6.2

### Added
- Auto-detect cloud login method (legacy vs web login)
- Web-session login fallback with browser-like headers
- Cloud consumption fetch: hardened logging and debug controls

### Fixed
- Modbus client strict/transaction checks disabled for compatibility
- Daily energy sensors now report **TOTAL** state_class
- State_class auditing based on units
- Legacy handshake JSON validation and error severity cleanup
- Consumption log index error and stability fixes

## 2026-03-04 — v1.6.1

### Added
- Display precision for setpoint sensors
- Loop setpoint registers used as Modbus target temp
- HVAC mode mapping to global regime + system regime select
- Cooling/auto HVAC modes enabled by default

### Fixed
- COP/SCOP scaling, units, and state_class cleanup
- Modbus HVAC mode logic (global regime OFF → HVAC OFF)
- Preset labels normalized (ON/OFF/AUTO)
- DHW HVAC modes restricted to HEAT
- Reverted invalid 500°C Modbus climate handling

## 2026-02-22 — v1.5.1

### Fixed
- Reverted consumption request parameter change (compatibility)

## 2026-02-16 — v1.5.0

### Added
- Cloud + Modbus entity unification
- Climate **OFF** mode and auto-entity cleanup
- DHW support: climates, shortcuts, presets, sensors, and offsets
- Modbus number entities for register control (min/max temp, party mode)
- Presets for Modbus DHW/reservoir climates
- Multi-instance support (Cloud + Modbus simultaneously)
- Updated translations (SL/DE/IT to 100%)

### Fixed
- Cloud/Modbus binary sensor issues
- Cloud temperature scaling and JSON parsing for DHW/reservoir
- Unique ID conflicts for multi-instance setups
- Enum mapping alignment with Cloud API
- HP load sensor visibility (read/write measurement register)

### Changed
- License switched to **MIT**
- README updates and cleanup of old documentation artifacts

## 2026-02-04 — v1.4.0

### Fixed
- Cloud API temperature/pressure scaling
- operation_regime enum mapping

## 2026-02-04 — v1.3.0

### Added
- Major refactor: clean architecture and production optimizations
- v1.2.0 entity ID compatibility retained
- Register system consolidation; writes migrated to JSON

### Changed
- Repository cleanup (removed temporary docs/test files)
- README documentation overhaul

## 2025-11-24 — v1.2.0

### Added
- Dashboard refresh and updated imagery
- Quick‑start guide and progress summary docs
- Comprehensive README expansion (usage and setup)
- Session summary/reference notes

## 2025-11-24 — v1.1.9

### Added
- Additional properties in `hacs.json`

## 2025-10-21 — v1.1.8

### Changed
- Metadata refresh and content cleanup

## 2025-04-19 — v1.1.7

### Changed
- Manifest updates

## 2025-04-08 — v1.1.6

### Added
- HACS + hassfest CI workflows (`validate_hacs`, `hassfest`)
- `hacs.json` metadata alignment

## 2025-03-30 — v1.1.5

### Changed
- Packaging refresh / uploads

## 2025-03-30 — v1.1.4

### Changed
- Manifest update

## 2025-03-29

### Added
- DHW switch functionality (PR #7)

## 2025-03-07 — v1.1.3

### Changed
- Manifest update

## 2025-02-14 — v1.1.2

### Changed
- Packaging refresh / uploads

## 2025-02-05 — v1.1.1

### Changed
- Packaging refresh / uploads

## 2025-02-04 — v1.1.0

### Added
- README updates and initial metadata polish

## 2025-01-14 — v1.0.3 / v1.0.2 / v1.0.1

### Fixed
- Early bug fixes and sensor updates (`sensor.py`)
- Packaging/cleanup adjustments

## 2025-01-13 — v1.0.0

### Added
- Initial public release
