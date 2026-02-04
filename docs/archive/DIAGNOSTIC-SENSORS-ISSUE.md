# Diagnostic Sensors Still Disabled - Root Cause

**Issue:** Even after removing `entity_registry_enabled_default = False` from sensor.py, the diagnostic entities remain disabled.

**Root Cause:** Home Assistant caches entity states in the entity registry. Once an entity is created as "disabled", changing the code doesn't retroactively enable it.

**Solutions:**

## Option 1: Manual UI Enable (Easiest for user)
1. Go to: Settings → Devices & Services → Kronoterm
2. Scroll to "11 disabled entities"
3. Click each one and enable it

## Option 2: Delete integration via UI and re-add (Cleanest)
1. Delete the integration from UI
2. Re-add it - all entities will be created enabled

## Option 3: Update workspace to match container (my recommendation)
The container has outdated code. Let me sync the fixed workspace code to the container.
