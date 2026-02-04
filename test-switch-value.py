#!/usr/bin/env python3
"""Test script to check register 2012 value and switch state."""
import asyncio
from pymodbus.client import AsyncModbusTcpClient

async def test_register_2012():
    # Connect to Modbus
    client = AsyncModbusTcpClient("10.0.0.51", port=502)
    await client.connect()
    
    # Read register 2012 (system_on)
    # Apply -1 offset for pymodbus
    result = await client.read_holding_registers(2012 - 1, count=1, slave=20)
    
    if result.isError():
        print(f"❌ Error reading register 2012: {result}")
    else:
        raw_value = result.registers[0]
        print(f"✅ Register 2012 (system_on) raw value: {raw_value}")
        print(f"   Meaning: {'ON (1)' if raw_value == 1 else 'OFF (0)' if raw_value == 0 else f'Unknown ({raw_value})'}")
        
        # Convert to signed if needed
        if raw_value >= 32768:
            signed_value = raw_value - 65536
            print(f"   Signed value: {signed_value}")
    
    await client.close()

if __name__ == "__main__":
    asyncio.run(test_register_2012())
