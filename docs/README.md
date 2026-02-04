# Kronoterm Integration Documentation

## User Documentation

### Setup & Configuration
- **[RECONFIGURE.md](RECONFIGURE.md)** - Switch between Cloud API and Modbus modes without losing entities

### Features
- **[CLIMATE-COMPLETE.md](CLIMATE-COMPLETE.md)** - Climate entity implementation guide
- **[CLIMATE-MODBUS-MAPPING.md](CLIMATE-MODBUS-MAPPING.md)** - Temperature sensor register mappings
- **[UPDATE-INTERVAL-SECONDS.md](UPDATE-INTERVAL-SECONDS.md)** - Configure polling frequency (5-600s)
- **[WRITABLE-VALUE-NUMBERS.md](WRITABLE-VALUE-NUMBERS.md)** - Adjustable parameters via number entities

## Developer Documentation

### Implementation Details
- **[JSON-IMPLEMENTATION-COMPLETE.md](JSON-IMPLEMENTATION-COMPLETE.md)** - JSON-based register map architecture
- **[MODBUS-JSON-IMPLEMENTATION.md](MODBUS-JSON-IMPLEMENTATION.md)** - How Modbus coordinator uses kronoterm.json
- **[PERFORMANCE-OPTIMIZATION.md](PERFORMANCE-OPTIMIZATION.md)** - Batch reading optimization (133x speedup)

### Bug Fixes & Improvements
- **[SWITCH-STATE-FIX.md](SWITCH-STATE-FIX.md)** - Control register polling for switch state
- **[FINAL-UPDATE-SUMMARY.md](FINAL-UPDATE-SUMMARY.md)** - Complete changelog of recent updates

### Development History
- **[SESSION-SUMMARY-2026-02-03.md](SESSION-SUMMARY-2026-02-03.md)** - Feb 3, 2026 development session
- **[SESSION-STATUS-UPDATE.md](SESSION-STATUS-UPDATE.md)** - Feb 4, 2026 development session

## Archive
Older development notes and intermediate status files are in `archive/`
