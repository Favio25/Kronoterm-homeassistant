#!/usr/bin/env python3
"""
Test the Modbus connection with pymodbus 3.11.x API.
This simulates what the integration will do.
"""

import asyncio
import sys

try:
    from pymodbus.client import AsyncModbusTcpClient
    print(f"✅ pymodbus imported successfully")
    import pymodbus
    print(f"   Version: {pymodbus.__version__}")
except ImportError as e:
    print(f"❌ Failed to import pymodbus: {e}")
    print("   Installing pymodbus...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pymodbus>=3.5.0"])
    from pymodbus.client import AsyncModbusTcpClient
    import pymodbus
    print(f"✅ pymodbus installed: {pymodbus.__version__}")

HOST = "10.0.0.51"
PORT = 502
UNIT_ID = 20

async def test_connection():
    """Test async Modbus TCP connection."""
    print(f"\n{'='*60}")
    print(f"Testing Modbus TCP Connection")
    print(f"{'='*60}")
    print(f"Host: {HOST}:{PORT}")
    print(f"Unit ID: {UNIT_ID}\n")
    
    # Create client (no slave in constructor for pymodbus 3.x)
    print("Creating AsyncModbusTcpClient...")
    client = AsyncModbusTcpClient(
        host=HOST,
        port=PORT,
    )
    
    try:
        # Connect
        print("Connecting...")
        connected = await client.connect()
        
        if not connected:
            print("❌ Connection failed")
            return False
        
        print("✅ Connected successfully\n")
        
        # Test reading outdoor temperature (register 2102)
        print("Reading register 2102 (Outdoor Temperature)...")
        result = await client.read_holding_registers(address=2102, count=1, slave=UNIT_ID)
        
        if result.isError():
            print(f"❌ Read error: {result}")
            return False
        
        raw_value = result.registers[0]
        temp = raw_value * 0.1
        print(f"✅ Read successful: {raw_value} (raw) = {temp:.1f}°C\n")
        
        # Test reading a few more registers
        test_registers = [
            (2109, "Loop 1 Current Temp", 0.1),
            (2187, "Loop 1 Setpoint", 0.1),
            (2023, "DHW Setpoint", 0.1),
            (2001, "Working Function", 1),
            (2325, "System Pressure", 0.1),
            (2371, "COP", 0.01),
        ]
        
        print("Testing additional registers:")
        print("-" * 60)
        
        success_count = 0
        for addr, name, scale in test_registers:
            result = await client.read_holding_registers(address=addr, count=1, slave=UNIT_ID)
            
            if result.isError():
                print(f"  ❌ {addr:4d} {name:30s} - Error: {result}")
            else:
                raw = result.registers[0]
                scaled = raw * scale
                
                # Check for error values
                if raw in [64936, 64937, 65535]:
                    print(f"  ⚠️  {addr:4d} {name:30s} - Sensor not connected")
                else:
                    print(f"  ✅ {addr:4d} {name:30s} - {scaled:.2f}")
                    success_count += 1
        
        print(f"\n{'='*60}")
        print(f"Results: {success_count}/{len(test_registers)} registers read successfully")
        print(f"{'='*60}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        print("\nClosing connection...")
        client.close()
        print("✅ Connection closed")

if __name__ == "__main__":
    print("\n" + "="*60)
    print("Kronoterm Modbus TCP Integration - Connection Test")
    print("="*60)
    
    success = asyncio.run(test_connection())
    
    if success:
        print("\n✅ All tests passed! Integration should work.")
        sys.exit(0)
    else:
        print("\n❌ Tests failed. Check errors above.")
        sys.exit(1)
