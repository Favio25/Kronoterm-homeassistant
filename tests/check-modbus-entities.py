#!/usr/bin/env python3
"""
Check Modbus entity status and register values.
"""
import asyncio
import sys
from pymodbus.client import AsyncModbusTcpClient

# Import register definitions
sys.path.insert(0, '/home/frelih/.openclaw/workspace/kronoterm-integration/custom_components/kronoterm')
from modbus_registers import ALL_REGISTERS, scale_value, format_enum, read_bit, RegisterType

HOST = "10.0.0.51"
PORT = 502
UNIT_ID = 20
ERROR_VALUES = [64936, 64937, 65535]

async def check_registers():
    """Check all register values."""
    client = AsyncModbusTcpClient(host=HOST, port=PORT)
    
    try:
        connected = await client.connect()
        if not connected:
            print("❌ Failed to connect to Modbus device")
            return
        
        print("✅ Connected to Modbus device")
        print(f"\nReading {len(ALL_REGISTERS)} registers...\n")
        
        successful = 0
        failed = 0
        error_value = 0
        
        results = []
        
        for register in ALL_REGISTERS:
            try:
                result = await client.read_holding_registers(
                    register.address, count=1, slave=UNIT_ID
                )
                
                if result.isError():
                    failed += 1
                    results.append((register.address, register.name, "READ ERROR", None))
                    continue
                
                raw_value = result.registers[0]
                
                if raw_value in ERROR_VALUES:
                    error_value += 1
                    results.append((register.address, register.name, f"ERROR VALUE ({raw_value})", None))
                    continue
                
                # Process value based on type
                if register.reg_type == RegisterType.BITS:
                    value = read_bit(raw_value, register.bit)
                    display = f"{value} (bit {register.bit} of {raw_value})"
                elif register.reg_type == RegisterType.BINARY:
                    value = bool(raw_value)
                    display = f"{value} ({raw_value})"
                elif register.reg_type == RegisterType.ENUM:
                    value = format_enum(register, raw_value)
                    display = f"{value} ({raw_value})"
                else:
                    value = scale_value(register, raw_value)
                    if value is None:
                        error_value += 1
                        results.append((register.address, register.name, "SCALE ERROR", raw_value))
                        continue
                    unit = register.unit if hasattr(register, 'unit') and register.unit else ""
                    display = f"{value}{unit} (raw {raw_value})"
                
                successful += 1
                results.append((register.address, register.name, "OK", display))
                
            except Exception as err:
                failed += 1
                results.append((register.address, register.name, f"EXCEPTION: {err}", None))
        
        # Print results
        print("=" * 100)
        print(f"{'Address':<8} {'Status':<20} {'Value':<50} {'Name'}")
        print("=" * 100)
        
        for addr, name, status, value in results:
            value_str = value if value else ""
            print(f"{addr:<8} {status:<20} {value_str:<50} {name}")
        
        print("=" * 100)
        print(f"\n✅ Successful: {successful}")
        print(f"⚠️  Error values: {error_value}")
        print(f"❌ Failed reads: {failed}")
        print(f"📊 Total: {len(ALL_REGISTERS)}")
        
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(check_registers())
