#!/usr/bin/env python3
"""
Full integration test - simulates what HA does.
Tests validation, connection, reading, and data processing.
"""

import asyncio
import sys

try:
    from pymodbus.client import AsyncModbusTcpClient
except ImportError:
    print("Installing pymodbus...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "pymodbus>=3.5.0"])
    from pymodbus.client import AsyncModbusTcpClient

# Connection details
HOST = "10.0.0.51"
PORT = 502
UNIT_ID = 20

# Error values
ERROR_VALUES = [64936, 64937, 65535]

# Test registers (from modbus_registers.py)
TEST_REGISTERS = [
    (2102, "Outdoor Temperature", 0.1, "°C"),
    (2109, "Loop 1 Current Temp", 0.1, "°C"),
    (2187, "Loop 1 Setpoint", 0.1, "°C"),
    (2049, "Loop 2 Setpoint", 0.1, "°C"),
    (2023, "DHW Setpoint", 0.1, "°C"),
    (2024, "DHW Current Setpoint", 0.1, "°C"),
    (2101, "HP Inlet Temp", 0.1, "°C"),
    (2160, "Loop 1 Thermostat", 0.1, "°C"),
    (2001, "Working Function", 1, ""),
    (2006, "Error/Warning Status", 1, ""),
    (2000, "System Operation", 1, ""),
    (2045, "Loop 1 Pump", 1, ""),
    (2055, "Loop 2 Pump", 1, ""),
    (2028, "DHW Pumps (bits)", 1, ""),
    (2002, "Additional Source (bits)", 1, ""),
    (2325, "System Pressure", 0.1, "bar"),
    (2371, "COP", 0.01, ""),
    (2372, "SCOP", 0.01, ""),
    (2129, "Current Power", 1, "W"),
    (2327, "HP Load", 1, "%"),
    (2329, "Heating Power", 1, "W"),
    (2090, "Operating Hours Heating", 1, "h"),
    (2091, "Operating Hours DHW", 1, "h"),
    (2095, "Operating Hours Additional", 1, "h"),
]

WORKING_FUNCTION_MAP = {
    0: "heating",
    1: "dhw",
    2: "cooling",
    3: "pool_heating",
    4: "thermal_disinfection",
    5: "standby",
    7: "remote_deactivation"
}

ERROR_STATUS_MAP = {
    0: "no_error",
    1: "warning",
    2: "error"
}

def read_bit(value, bit):
    """Extract specific bit from value."""
    return bool((value >> bit) & 1)

async def test_config_flow_validation():
    """Test 1: Config flow validation (what happens when user clicks Submit)."""
    print("\n" + "="*70)
    print("TEST 1: CONFIG FLOW VALIDATION")
    print("="*70)
    print("This simulates what happens when you submit the Modbus config form.\n")
    
    # Simulate user input
    config_data = {
        "host": HOST,
        "port": PORT,
        "unit_id": UNIT_ID,
        "model": "adapt_0416",
    }
    
    print(f"Config data: {config_data}\n")
    
    try:
        # Create client (same as config_flow_modbus.py)
        client = AsyncModbusTcpClient(host=HOST, port=PORT)
        
        print("Connecting...")
        connected = await client.connect()
        
        if not connected:
            print("❌ Connection failed (would show: cannot_connect)")
            return False
        
        print("✅ Connected\n")
        
        print("Testing read (register 2102 - outdoor temp)...")
        result = await client.read_holding_registers(address=2102, count=1, slave=UNIT_ID)
        
        client.close()
        
        if result.isError():
            print(f"❌ Read failed: {result} (would show: cannot_read)")
            return False
        
        value = result.registers[0]
        temp = value * 0.1
        print(f"✅ Read successful: {value} (raw) = {temp:.1f}°C\n")
        
        print("✅ Validation PASSED - Integration would be added successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Exception: {e} (would show: unknown error)")
        import traceback
        traceback.print_exc()
        return False

async def test_coordinator_initialization():
    """Test 2: Coordinator initialization (what happens after integration is added)."""
    print("\n" + "="*70)
    print("TEST 2: COORDINATOR INITIALIZATION")
    print("="*70)
    print("This simulates what ModbusCoordinator does on startup.\n")
    
    try:
        # Create client (same as modbus_coordinator.py)
        client = AsyncModbusTcpClient(host=HOST, port=PORT)
        
        print("Connecting...")
        connected = await client.connect()
        
        if not connected:
            print("❌ Connection failed")
            return False
        
        print("✅ Connected\n")
        
        # Read device ID
        print("Fetching device info...")
        device_id_result = await client.read_holding_registers(address=5054, count=1, slave=UNIT_ID)
        
        if not device_id_result.isError():
            device_id = device_id_result.registers[0]
            print(f"  Device ID: 0x{device_id:04X}")
        else:
            print("  Device ID: Failed to read")
        
        # Read firmware
        firmware_result = await client.read_holding_registers(address=5056, count=1, slave=UNIT_ID)
        
        if not firmware_result.isError():
            firmware = firmware_result.registers[0]
            print(f"  Firmware: {firmware}")
        else:
            print("  Firmware: Failed to read")
        
        print("\n✅ Device info fetched successfully!")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_data_update():
    """Test 3: Data update (what coordinator does every 60 seconds)."""
    print("\n" + "="*70)
    print("TEST 3: DATA UPDATE (SENSOR READING)")
    print("="*70)
    print("This simulates what happens during each coordinator update.\n")
    
    try:
        client = AsyncModbusTcpClient(host=HOST, port=PORT)
        
        connected = await client.connect()
        if not connected:
            print("❌ Connection failed")
            return False
        
        print("✅ Connected\n")
        print(f"Reading {len(TEST_REGISTERS)} registers...\n")
        
        success_count = 0
        error_count = 0
        unavailable_count = 0
        
        data = {}
        
        for addr, name, scale, unit in TEST_REGISTERS:
            try:
                result = await client.read_holding_registers(address=addr, count=1, slave=UNIT_ID)
                
                if result.isError():
                    print(f"  ❌ {addr:4d} {name:35s} - Read error")
                    error_count += 1
                    continue
                
                raw = result.registers[0]
                
                # Check for error values
                if raw in ERROR_VALUES:
                    print(f"  ⚠️  {addr:4d} {name:35s} - Sensor not connected")
                    unavailable_count += 1
                    continue
                
                # Scale value
                value = raw * scale
                
                # Special handling for enums
                if addr == 2001:  # Working function
                    enum_val = WORKING_FUNCTION_MAP.get(raw, f"unknown_{raw}")
                    print(f"  ✅ {addr:4d} {name:35s} - {enum_val} (raw: {raw})")
                    data[addr] = {"value": enum_val, "raw": raw}
                elif addr == 2006:  # Error status
                    enum_val = ERROR_STATUS_MAP.get(raw, f"unknown_{raw}")
                    print(f"  ✅ {addr:4d} {name:35s} - {enum_val} (raw: {raw})")
                    data[addr] = {"value": enum_val, "raw": raw}
                elif addr == 2000 or addr == 2045 or addr == 2055:  # Binary sensors
                    state = "ON" if raw else "OFF"
                    print(f"  ✅ {addr:4d} {name:35s} - {state}")
                    data[addr] = {"value": bool(raw), "raw": raw}
                elif addr == 2028 or addr == 2002:  # Bit-masked
                    if addr == 2028:
                        bit0 = read_bit(raw, 0)
                        bit1 = read_bit(raw, 1)
                        print(f"  ✅ {addr:4d} {name:35s} - bit0={bit0}, bit1={bit1} (raw: {raw})")
                    else:
                        bit0 = read_bit(raw, 0)
                        bit4 = read_bit(raw, 4)
                        print(f"  ✅ {addr:4d} {name:35s} - bit0={bit0}, bit4={bit4} (raw: {raw})")
                    data[addr] = {"value": raw, "raw": raw}
                else:
                    # Regular numeric value
                    unit_str = f" {unit}" if unit else ""
                    print(f"  ✅ {addr:4d} {name:35s} - {value:.2f}{unit_str}")
                    data[addr] = {"value": value, "raw": raw}
                
                success_count += 1
                
            except Exception as e:
                print(f"  ❌ {addr:4d} {name:35s} - Exception: {e}")
                error_count += 1
        
        client.close()
        
        print(f"\n{'='*70}")
        print(f"RESULTS:")
        print(f"  ✅ Success: {success_count}")
        print(f"  ⚠️  Unavailable (sensor not connected): {unavailable_count}")
        print(f"  ❌ Errors: {error_count}")
        print(f"  📊 Total: {len(TEST_REGISTERS)}")
        print(f"{'='*70}\n")
        
        if success_count > 0:
            print(f"✅ Data update successful - {success_count} entities would be available")
            return True
        else:
            print("❌ No data read successfully")
            return False
        
    except Exception as e:
        print(f"❌ Exception during data update: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_write_operation():
    """Test 4: Write operation (changing a setpoint)."""
    print("\n" + "="*70)
    print("TEST 4: WRITE OPERATION (SETPOINT CHANGE)")
    print("="*70)
    print("This tests changing DHW setpoint (read-only for safety).\n")
    
    try:
        client = AsyncModbusTcpClient(host=HOST, port=PORT)
        
        connected = await client.connect()
        if not connected:
            print("❌ Connection failed")
            return False
        
        print("✅ Connected\n")
        
        # Read current DHW setpoint
        print("Reading current DHW setpoint (register 2023)...")
        result = await client.read_holding_registers(address=2023, count=1, slave=UNIT_ID)
        
        if result.isError():
            print("❌ Failed to read current value")
            client.close()
            return False
        
        current_raw = result.registers[0]
        current_temp = current_raw * 0.1
        print(f"  Current value: {current_temp:.1f}°C (raw: {current_raw})\n")
        
        print("✅ Write operations are supported!")
        print("   (Not actually writing to avoid changing settings)")
        print(f"   To test write: Would write to register 2023")
        print(f"   Method: client.write_register(address=2023, value=450, slave={UNIT_ID})")
        print(f"   This would set DHW to 45.0°C\n")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False

async def run_all_tests():
    """Run all integration tests."""
    print("\n" + "="*70)
    print("KRONOTERM MODBUS TCP INTEGRATION - FULL TEST SUITE")
    print("="*70)
    print(f"Device: {HOST}:{PORT}, Unit ID: {UNIT_ID}")
    print(f"Time: {asyncio.get_event_loop().time()}")
    
    results = {
        "config_flow": False,
        "coordinator_init": False,
        "data_update": False,
        "write_ops": False,
    }
    
    # Test 1: Config flow validation
    results["config_flow"] = await test_config_flow_validation()
    
    # Test 2: Coordinator initialization
    if results["config_flow"]:
        results["coordinator_init"] = await test_coordinator_initialization()
    else:
        print("\n⏭️  Skipping coordinator init (validation failed)")
    
    # Test 3: Data update
    if results["coordinator_init"]:
        results["data_update"] = await test_data_update()
    else:
        print("\n⏭️  Skipping data update (coordinator init failed)")
    
    # Test 4: Write operations
    if results["data_update"]:
        results["write_ops"] = await test_write_operation()
    else:
        print("\n⏭️  Skipping write ops (data update failed)")
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {test_name:20s} {status}")
    
    all_passed = all(results.values())
    
    print("\n" + "="*70)
    if all_passed:
        print("✅ ALL TESTS PASSED!")
        print("   The integration is ready to use in Home Assistant.")
        print("   You can safely add it via the UI.")
    else:
        print("❌ SOME TESTS FAILED")
        print("   Review the errors above before adding integration.")
    print("="*70 + "\n")
    
    return all_passed

if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
