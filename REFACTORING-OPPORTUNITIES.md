# Kronoterm Integration - Refactoring Opportunities

## 🎯 Priority: High

### 1. **Remove Dead Code**
- **File:** `modbus_registers_old.py` (14KB)
- **Status:** Not imported anywhere
- **Action:** Delete the file
- **Risk:** None (not referenced)

### 2. **Consolidate Register System**
**Problem:** Mixed architecture - JSON for reads, Python constants for writes

**Current State:**
- `kronoterm.json` + `register_map.py` → used for sensor reads (168 registers)
- `modbus_registers.py` (907 lines) → hardcoded constants for writes

**Issues:**
- Duplication between JSON and Python definitions
- Some registers marked Read-only in JSON but written to in code
- Maintenance burden: updates needed in two places
- Register 2033 (ANTI_LEGIONELLA_ENABLE) not in JSON at all

**Registers with access mode conflicts:**
```
2002: Dodatni vklopi (JSON: Read, Code: writes to it via ADDITIONAL_SOURCE_SWITCH)
2003: Rezervni vir (JSON: Read, Code: writes to it via RESERVE_SOURCE_SWITCH)
2010: Hitro segrevanje (JSON: Read, but code may write to 2015 instead)
```

**Proposed Solution:**
A. **Update JSON with correct access modes** (Read/Write where applicable)
B. **Migrate write operations to use RegisterMap** instead of hardcoded constants
C. **Keep Register/RegisterType classes** in a lightweight types module
D. **Deprecate modbus_registers.py** once migration complete

### 3. **Fix Placeholder Addresses in binary_sensor.py**
```python
# Line ~24-27:
BinarySensorConfig(2065, "circulation_loop_3", ...)  # !!! UPDATE XXXX !!!
BinarySensorConfig(2075, "circulation_loop_4", ...)  # !!! UPDATE YYYY !!!
```

**Action:** 
- Find correct addresses from Kronoterm manual or mark as unavailable
- Remove TODO comments

---

## 🎯 Priority: Medium

### 4. **Code Organization**
**File sizes (largest first):**
```
modbus_coordinator.py    37K
coordinator.py           30K
climate.py               25K
sensor.py                24K
register_map.py          21K
modbus_registers.py      20K (CANDIDATE FOR REMOVAL)
```

**Observations:**
- `modbus_coordinator.py` is getting large (37K, ~1000 lines)
- Could benefit from splitting write operations into separate module
- Climate-specific logic could be extracted

**Potential splits:**
```
modbus_coordinator.py → 
  - modbus_coordinator.py (core polling/reads)
  - modbus_writes.py (all write operations)
  - modbus_climate.py (climate-specific methods)
```

### 5. **Type Safety & Documentation**
- Add return type hints to all coordinator methods
- Document register address sources (which manual, which page)
- Add docstrings to all public methods

### 6. **Error Handling**
Check for:
- Graceful degradation when registers return error values (64936, -600, etc.)
- Timeout handling in write operations
- Connection loss recovery

---

## 🎯 Priority: Low

### 7. **Configuration**
- Consider moving hardcoded timeouts to config options
- Make batch read size configurable
- Add option to disable specific register ranges if causing issues

### 8. **Testing**
- No tests currently exist
- Add unit tests for RegisterMap
- Add integration tests for modbus read/write
- Mock tests for coordinator logic

### 9. **Performance**
Current batch reading is excellent (0.28s). Future optimizations:
- Cache writable register addresses for faster writes
- Implement smart polling (skip unchanged values)
- Add configurable poll intervals per register type

---

## 📋 Recommended Action Plan

### Phase 1: Cleanup (Low Risk)
1. ✅ Delete `modbus_registers_old.py`
2. ✅ Fix placeholder addresses in `binary_sensor.py`
3. ✅ Add missing register 2033 to JSON
4. ✅ Update access modes in JSON (2002, 2003, 2010, 2015, 2016)

### Phase 2: Consolidation (Medium Risk)
5. Create `modbus_types.py` with Register/RegisterType classes
6. Extend RegisterMap to support lookups by name for write operations
7. Update coordinator write methods to use RegisterMap
8. Deprecate `modbus_registers.py` (mark for removal)

### Phase 3: Refactor (Higher Risk)
9. Split `modbus_coordinator.py` into logical modules
10. Add comprehensive type hints
11. Improve error handling

### Phase 4: Quality (Long-term)
12. Add unit tests
13. Add integration tests
14. Performance profiling and optimization

---

## ⚠️ Breaking Changes

None of the proposed changes should affect end users:
- Entity IDs remain unchanged
- Config entries remain compatible
- All existing functionality preserved

---

## 🧪 Testing Checklist (After Changes)

- [ ] Integration loads without errors
- [ ] All 121 entities present
- [ ] Climate entities work (read + write temps)
- [ ] Switches work (on/off operations)
- [ ] Sensors update correctly
- [ ] Reconfigure flow works
- [ ] No register addressing errors in logs

---

**Generated:** 2026-02-04  
**Integration Status:** Production Ready ✅  
**Next Review:** After Phase 1 completion
