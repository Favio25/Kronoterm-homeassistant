# Changelog

## 2026-03-14

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
