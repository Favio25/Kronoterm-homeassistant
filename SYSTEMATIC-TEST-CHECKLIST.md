# Systematic Test & Fix Checklist

**Command to trigger:** "Test and fix the integration until everything works"

---

## 🔄 Test Cycle Process

### Phase 1: Data Collection
- [ ] Check HA logs for errors
- [ ] Count entities by type
- [ ] List unavailable entities
- [ ] Check register read success rate
- [ ] Verify all platforms loaded

### Phase 2: Analysis
- [ ] Compare entity count vs expected
- [ ] Identify missing entity types
- [ ] Find error patterns in logs
- [ ] Check register availability

### Phase 3: Diagnosis
- [ ] Determine root cause
- [ ] Check if registers defined
- [ ] Verify entity creation logic
- [ ] Confirm coordinator data structure

### Phase 4: Fix
- [ ] Apply code correction
- [ ] Copy to container
- [ ] Restart Home Assistant
- [ ] Wait for full startup

### Phase 5: Verification
- [ ] Re-check entity count
- [ ] Verify fix resolved issue
- [ ] Check for new errors
- [ ] Test entity functionality

### Phase 6: Iterate
- [ ] If issues remain → return to Phase 1
- [ ] If all fixed → final verification
- [ ] Document results

---

## ✅ Expected Entity Counts

Based on official documentation and single-loop installation:

| Type | Min | Max | Notes |
|------|-----|-----|-------|
| Sensors | 24 | 35 | Temps, status, power |
| Binary Sensors | 6 | 10 | Pumps, heaters, flags |
| Switches | 5 | 6 | Controls |
| Numbers | 6 | 10 | Setpoints, offsets |
| Selects | 2 | 6 | Modes (loop1, DHW, program) |
| Climate | 1 | 4 | DHW + loops |
| **Total** | **44** | **71** | Depends on installation |

---

## 🔍 Common Issues & Fixes

### Issue: Binary Sensors Missing
**Symptoms:** 0 binary sensors created  
**Cause:** Pump registers not in modbus_registers.py  
**Fix:** Add LOOP*_PUMP_STATUS registers  

### Issue: Entities Unavailable
**Symptoms:** State shows "unavailable"  
**Cause:** Register not being read  
**Fix:** Add register to ALL_REGISTERS list  

### Issue: Import Errors
**Symptoms:** "cannot import name 'XXX'"  
**Cause:** Register renamed but import not updated  
**Fix:** Update imports in coordinator.py  

### Issue: Wrong Values
**Symptoms:** Values don't match expected  
**Cause:** Incorrect scale factor or wrong register  
**Fix:** Check official docs, correct address/scale  

### Issue: Duplicate ID Errors
**Symptoms:** "ID already exists"  
**Cause:** Cloud + Modbus both creating same entities  
**Fix:** Cosmetic only, or fix unique_id generation  

---

## 📊 Verification Commands

### Check Entity Count
```python
import json
registry = json.load(open("/config/.storage/core.entity_registry"))
modbus_entry = "01KGHQ4NEEFNPFVWF7W3PWPN57"  # Update this!
entities = [e for e in registry["data"]["entities"] if e.get("config_entry_id") == modbus_entry]
print(f"Total: {len(entities)}")
```

### Check for Errors
```bash
sg docker -c "docker logs homeassistant" | grep -i "error\|exception" | grep kronoterm | tail -20
```

### Check Register Reading
```bash
sg docker -c "docker logs homeassistant" | grep "Successfully read" | tail -5
```

### Check Platform Loading
```bash
sg docker -c "docker logs homeassistant" | grep "PLATFORM SETUP" | grep Modbus
```

---

## 🎯 Success Criteria

Integration is considered "complete" when:

1. ✅ All platforms load without errors
2. ✅ Entity count matches expected range
3. ✅ 0 unavailable entities (except hardware not installed)
4. ✅ 95%+ register read success rate
5. ✅ No critical errors in logs
6. ✅ Control entities respond to changes
7. ✅ Values match Cloud API (if available)
8. ✅ All expected features accessible

---

## 📝 Issue Tracking Template

```markdown
### Issue #X: [Title]

**Status:** 🔄 In Progress / ✅ Fixed / ❌ Blocked

**Symptoms:**
- What's wrong
- How to reproduce

**Root Cause:**
- Technical explanation

**Fix:**
- What was changed
- Which files modified

**Testing:**
- How to verify fix
- Expected result

**Result:**
- Did it work?
- Any side effects?
```

---

## 🚀 Quick Test Command

Run this after any change:

```bash
# 1. Copy files
sg docker -c "docker cp custom_components/kronoterm/FILE.py homeassistant:/config/custom_components/kronoterm/"

# 2. Restart
sg docker -c "docker restart homeassistant" && sleep 45

# 3. Check results
sg docker -c "docker logs homeassistant --tail 100" | grep -E "🔥|ERROR|Successfully"
```

---

**Use this checklist every time you run "Test and fix the integration"**
