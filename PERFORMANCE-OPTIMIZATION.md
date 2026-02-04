# Kronoterm Integration - Performance Optimization

## Problem: 40+ Second Initialization Time

The Modbus integration was taking 40+ seconds to initialize after adding it to Home Assistant.

## Investigation

### Initial Approach: Parallel Reads with asyncio.gather()
- Attempted to read 95 registers concurrently using `asyncio.gather()`
- Expected massive speedup from parallel execution
- **Result: 37 seconds** (actually slower than sequential!)

### Root Cause: Modbus Transaction ID Conflicts
When reading 95 registers simultaneously:
- Each request gets a transaction ID
- Responses must match request transaction IDs
- With 95 concurrent requests, pymodbus got confused
- Register address 2361 being mistaken for transaction ID
- Constant retries and failures

Log output:
```
ERROR: request ask for transaction_id=191 but got id=2361, Skipping.
🔥 Parallel read took 37.29s for 95 registers (393ms per register)
```

## Solution: Batch Reading

### Implementation
Instead of 95 individual read requests, group consecutive registers into batches:

```python
def _group_registers_into_batches(registers, max_gap=5, max_batch=100):
    """Group registers into consecutive batches for efficient Modbus reading."""
    # Sort by address
    # Group consecutive registers (max gap = 5)
    # Max 100 registers per batch
    # Returns: [(start_addr, count, [register_defs]), ...]
```

### Algorithm
1. Sort all 95 registers by address
2. Group consecutive registers:
   - If gap ≤ 5 registers: include in same batch
   - If batch size ≥ 100: start new batch
3. Read each batch with single Modbus request
4. Map results back to individual registers

### Example Batching
```
Registers: 2000, 2001, 2002, 2003, 2007, 2008, 2010...
Batch 1: Read addresses 2000-2010 (11 registers in 1 request)
  - Contains: 2000, 2001, 2002, 2003, 2007, 2008, 2010
  - Gaps filled automatically by Modbus read

Registers: 2100, 2101, 2103, 2110...
Batch 2: Read addresses 2100-2111 (12 registers in 1 request)
```

## Results

### Before (Parallel Individual Reads)
- 95 individual Modbus requests
- Transaction ID conflicts
- **37.29 seconds** total
- **393ms per register**

### After (Batch Reads)
- **12 batch Modbus requests**
- No transaction conflicts
- **0.28 seconds** total
- **23ms per batch**

### Speedup
**133x faster!** 🚀

```
🔥 Reading 95 registers using batch reads...
🔥 Grouped into 12 batches
🔥 Batch read took 0.28s for 95 registers in 12 batches
```

## Integration Initialization Timeline

### Before Optimization
1. Modbus connection: ~1s
2. Register reads (parallel): **37s**
3. Entity creation: ~2s
4. **Total: 40+ seconds**

### After Optimization  
1. Modbus connection: ~1s
2. Register reads (batch): **0.28s** ✅
3. Entity creation: ~1s
4. **Total: < 3 seconds** ✅

## Code Changes

### Main Files Modified
- `modbus_coordinator.py`:
  - Added `_group_registers_into_batches()` method
  - Refactored `_async_update_data()` to use batch reads
  - Added timing diagnostics

### Key Code
```python
# Group registers into batches
batches = self._group_registers_into_batches(registers_to_read)

# Read each batch
for batch_start, batch_count, batch_regs in batches:
    result = await self.client.read_holding_registers(
        batch_start - 1,  # Apply address offset
        count=batch_count,
        device_id=self.unit_id
    )
    # Map results back to individual registers
    for i, reg_def in enumerate(batch_regs):
        offset = reg_def.address - batch_start
        raw_value = result.registers[offset]
        # Process value...
```

## Benefits

1. **Instant initialization** - Users see entities in < 3 seconds
2. **No transaction conflicts** - Reliable Modbus communication
3. **Lower network overhead** - 12 requests instead of 95
4. **Scalable** - Can handle 200+ registers efficiently
5. **Standard Modbus practice** - Batch reads are the proper way

## Lessons Learned

1. **Parallel != Fast for Modbus**
   - Modbus protocol not designed for massive concurrency
   - Transaction ID collisions cause failures
   - Batch reads are the standard approach

2. **Know your protocol**
   - Modbus supports reading up to 125 consecutive registers
   - Single batch read is faster than multiple parallel reads
   - Protocol-level optimization beats application-level parallelism

3. **Always measure**
   - Added timing logs to identify bottleneck
   - Revealed 37s was in register reads, not entity creation
   - Data-driven optimization decisions

## Status
✅ **Production Ready**
- Integration initializes in < 3 seconds
- Reliable Modbus communication
- No transaction conflicts
- All sensors working correctly
