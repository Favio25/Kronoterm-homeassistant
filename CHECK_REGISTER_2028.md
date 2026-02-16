# Checking Register 2028 (DHW Circulation Pump Status)

## Issue
`binary_sensor.kronoterm_circulation_dhw` shows as unavailable

## Possible Causes
1. Register 2028 not present on your heat pump model
2. Register exists but bit 0 is never set
3. Register isn't being read by coordinator

## Manual Check
Try reading register 2028 directly with qModMaster or similar Modbus tool:
- **Address:** 2028
- **Type:** Holding Register
- **Expected:** Bitmask value
  - Bit 0 (value 1) = DHW circulation pump status
  - Bit 1 (value 2) = DHW recirculation pump status

If register doesn't exist or always returns 0, this feature isn't available on your heat pump.

## Workaround
If this sensor isn't needed, you can ignore it. The DHW circulation **switch** (register 2328) should still work for control.
