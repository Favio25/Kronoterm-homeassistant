# Testing Guide

## Entity Health Check Script

`test_entities.py` validates that all Kronoterm entities are available and working properly.

### Setup

1. **Get a Long-Lived Access Token** from Home Assistant:
   - Go to Profile → Long-Lived Access Tokens
   - Click "Create Token"
   - Copy the token

2. **Set the token** (choose one method):
   ```bash
   # Option 1: Environment variable
   export HA_TOKEN="your_token_here"
   
   # Option 2: Script will prompt you
   ```

3. **Update the script config** (if needed):
   ```python
   # Edit test_entities.py if your HA is not at localhost:8123
   HA_URL = "http://localhost:8123"  # Change if different
   ```

### Usage

```bash
# Run the test
./test_entities.py

# Or with Python directly
python3 test_entities.py
```

### What It Checks

✅ **Mode Detection**
- Auto-detects Cloud API vs Modbus mode based on sensor count
- Adjusts expected entity counts accordingly

✅ **Entity Availability**
- Entities not in "unavailable" or "unknown" state

✅ **Proper Naming**
- Entities have friendly names (not "Unknown")

✅ **Valid Values**
- No error values (64936 / -600)
- Temperature sensors within reasonable range (-50°C to 100°C)

✅ **Climate Entities**
- Have current_temperature
- Have target temperature setpoint

✅ **Expected Counts (Mode-Specific)**

**Cloud API Mode:**
- 31 sensors
- 6 binary sensors (circulation pumps, defrost, etc.)
- 6 switches (backup heater, antilegionella, etc.)
- 10 number entities (comfort/eco offsets)
- 4 select entities (operation modes)
- 4 climate entities (DHW, Loop1, Loop2, Reservoir)

**Modbus Mode:**
- 112 sensors (direct register reads)
- 2 binary sensors (system_on, error_status)
- 4 climate entities (DHW, Loop1, Loop2, Reservoir)

### Output

**Summary View (Cloud API mode):**
```
=== Kronoterm Entity Summary ===
Mode: Cloud API

✓ binary_sensor          6/6   healthy (expected: 6)
✓ climate                4/4   healthy (expected: 4)
✓ number                10/10  healthy (expected: 10)
✓ select                 4/4   healthy (expected: 4)
✓ sensor                31/31  healthy (expected: 31)
✓ switch                 6/6   healthy (expected: 6)

Total: 61/61 entities healthy

✓ All entities are healthy!
```

**Summary View (Modbus mode):**
```
=== Kronoterm Entity Summary ===
Mode: Modbus

✓ sensor               112/112 healthy (expected: 112)
✓ binary_sensor          2/2   healthy (expected: 2)
✓ climate                4/4   healthy (expected: 4)

Total: 118/118 entities healthy

✓ All entities are healthy!
```

**If Issues Found:**
```
=== Issues Found ===

✗ sensor.kronoterm_outdoor_temperature
  - State is unavailable
  
✗ sensor.kronoterm_buffer_top
  - Error value detected: 64936
```

**Detailed Report** (optional):
Shows every entity with its state, friendly name, and status.

### Return Codes

- `0` - All entities healthy ✅
- `1` - Issues found or connection error ❌

### CI/CD Integration

Use in automated testing:

```bash
#!/bin/bash
# Run after Home Assistant restart
docker restart homeassistant
sleep 30  # Wait for HA to initialize

# Test entities
if ./test_entities.py; then
    echo "✓ All entities healthy"
    exit 0
else
    echo "✗ Entity health check failed"
    exit 1
fi
```

### Troubleshooting

**"No Kronoterm entities found"**
- Check integration is loaded in HA
- Verify entity IDs contain "kronoterm"
- Check entity filter logic in script

**Connection errors**
- Verify HA is running (`docker ps | grep homeassistant`)
- Check HA_URL is correct
- Verify token is valid

**False positives**
- Adjust `EXPECTED_COUNTS` for your setup
- Modify temperature range checks if needed
- Update entity filtering logic if using custom naming
