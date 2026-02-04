# Update Interval: Now in Seconds!

## Change Summary
**Before:** 1-60 minutes (too slow for responsive local Modbus)  
**After:** 5-600 seconds (sub-minute polling supported!) ✅

---

## Why This Matters

### For Local Modbus:
Your batch read completes in **~300ms**. You can now poll every:
- **5 seconds** - Near real-time monitoring
- **10 seconds** - Very responsive (default for testing)
- **30 seconds** - Balanced performance
- **60 seconds** - Normal use
- **300 seconds (5 min)** - Conservative default

### For Cloud API:
- Minimum 30 seconds (protects API rate limits)
- Still benefits from sub-minute intervals

---

## New Settings

### Number Entity: `number.update_interval`
- **Unit:** Seconds (was minutes)
- **Min:** 5 seconds (Modbus) / 30 seconds (Cloud)
- **Max:** 600 seconds (10 minutes)
- **Step:** 5 seconds
- **Default:** 300 seconds (5 minutes)

---

## Examples

| Setting | Interval | Use Case |
|---------|----------|----------|
| 5s | Every 5 seconds | Debugging, watching switch changes |
| 10s | Every 10 seconds | Active heating monitoring |
| 30s | Every 30 seconds | Responsive but efficient |
| 60s | Every 1 minute | Normal monitoring |
| 300s | Every 5 minutes | Default (conservative) |

---

## Backwards Compatibility

✅ **Fully backwards compatible!**

If you had:
- `scan_interval: 5` (5 minutes in old system)

After upgrade:
- Reads `scan_interval_seconds` first
- Falls back to `scan_interval` (minutes) if not set
- First time you change the number entity → saves to `scan_interval_seconds`

---

## How to Use

### Option 1: Number Entity (Recommended)
1. Go to your Kronoterm device page
2. Find **"Update Interval"** entity (CONFIG category)
3. Set desired seconds (e.g., 10 for 10-second updates)
4. Changes apply **immediately** (no reload needed!)

### Option 2: Configuration (Advanced)
Edit integration options:
```yaml
scan_interval_seconds: 10  # 10 second updates
```

---

## Performance Impact

### 5 Second Polling:
- **Reads:** 105 registers every 5s = 21 reads/second
- **Network:** ~300ms per poll = 6% busy time
- **CPU:** Negligible (batch Modbus is fast)
- **Result:** ✅ Totally fine for local Modbus

### 10 Second Polling: (Recommended for active use)
- **Reads:** 105 registers every 10s = 10.5 reads/second  
- **Network:** ~300ms per poll = 3% busy time
- **Result:** ✅ Excellent balance

### 30 Second Polling: (Good default)
- **Reads:** 105 registers every 30s = 3.5 reads/second
- **Network:** ~300ms per poll = 1% busy time
- **Result:** ✅ Very light load

---

## When to Use Each Interval

### 5-10 seconds:
- Debugging new features
- Watching switch state changes
- Active system tuning
- Critical heating scenarios

### 30-60 seconds:
- Normal daily use
- Good responsiveness
- Low overhead
- Recommended for most users

### 300 seconds (5 minutes):
- Low priority monitoring
- Summer (heat pump idle)
- Minimal resource usage
- Cloud API polling

---

## Technical Details

### Storage:
```python
# New (preferred)
options["scan_interval_seconds"] = 10

# Legacy (backwards compat)
options["scan_interval"] = 1  # minutes
```

### Coordinator Initialization:
```python
# Try seconds first
if "scan_interval_seconds" in options:
    interval = timedelta(seconds=options["scan_interval_seconds"])
else:
    # Fall back to minutes
    interval = timedelta(minutes=options.get("scan_interval", 5))
```

### Number Entity:
```python
_attr_native_min_value = 5      # 5 seconds
_attr_native_max_value = 600    # 10 minutes
_attr_native_step = 5           # 5-second increments
_attr_unit_of_measurement = "s"
```

---

## Migration

### Automatic:
- Existing users: Keep current interval (in minutes)
- First edit: Saves to seconds automatically
- No manual action needed!

### Manual (if desired):
1. Current setting: 5 minutes
2. Change to: 300 seconds
3. Done! (equivalent value)

---

## Status
✅ **Deployed** - Commit `f109abf`

**Files Changed:**
- `number.py` - Entity now in seconds
- `modbus_coordinator.py` - Reads seconds with minute fallback
- `coordinator.py` - Cloud API also supports seconds
- `translations/en.json` - Updated label

---

## Testing Checklist

After restart:
1. ✅ Check number entity shows value in seconds
2. ✅ Change to 10 seconds
3. ✅ Watch logs for "Reading 105 registers" every 10s
4. ✅ Entity state updates every 10s
5. ✅ Change back to 300s (5 min default)

---

## Recommendation

**Start with 30 seconds**, then adjust based on your needs:
- Too slow → decrease to 10-15s
- Too fast → increase to 60-120s

For most users: **30-60 seconds is the sweet spot!** ⚡
