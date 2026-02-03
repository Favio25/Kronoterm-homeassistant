#!/usr/bin/env python3
"""
Compare current Modbus readings with expected values and identify mismatches.
This will help verify register mappings are correct.
"""
import asyncio
from pymodbus.client import AsyncModbusTcpClient

HOST = "10.0.0.51"
PORT = 502
UNIT_ID = 20

# Known correct mappings from kronoterm2mqtt and validation
REGISTER_MAP = {
    # Temperatures (scale 0.1)
    546: {"name": "Supply Temperature", "scale": 0.1, "unit": "°C"},
    551: {"name": "Outdoor Temperature", "scale": 0.1, "unit": "°C"},
    553: {"name": "Return Temperature", "scale": 0.1, "unit": "°C"},
    572: {"name": "DHW Temperature", "scale": 0.1, "unit": "°C"},
    2023: {"name": "DHW Setpoint", "scale": 0.1, "unit": "°C"},
    2049: {"name": "Loop 2 Setpoint", "scale": 0.1, "unit": "°C"},
    2101: {"name": "Reservoir/HP Inlet", "scale": 0.1, "unit": "°C"},
    2102: {"name": "Outdoor Temp (duplicate of 551?)", "scale": 0.1, "unit": "°C"},
    2104: {"name": "HP Outlet", "scale": 0.1, "unit": "°C"},
    2105: {"name": "Compressor Inlet/Evaporating", "scale": 0.1, "unit": "°C"},
    2106: {"name": "Compressor Outlet", "scale": 0.1, "unit": "°C"},
    2109: {"name": "Loop 1 Current", "scale": 0.1, "unit": "°C"},
    2110: {"name": "Loop 2 Current", "scale": 0.1, "unit": "°C"},
    2130: {"name": "Loop 1 Basic Mode Temp", "scale": 0.1, "unit": "°C"},
    2160: {"name": "Loop 1 Thermostat", "scale": 0.1, "unit": "°C"},
    2161: {"name": "Loop 2 Thermostat", "scale": 0.1, "unit": "°C"},
    2187: {"name": "Loop 1 Setpoint", "scale": 0.1, "unit": "°C"},
    
    # Status/Enum
    2001: {"name": "Working Function", "type": "enum", "values": {
        0: "heating", 1: "dhw", 2: "cooling", 3: "pool", 4: "thermal_disinfection", 5: "standby", 7: "remote_deactivation"
    }},
    2006: {"name": "Error/Warning", "type": "enum", "values": {0: "no_error", 1: "warning", 2: "error"}},
    2007: {"name": "Operation Regime", "type": "enum", "values": {0: "heating", 1: "cooling", 2: "off"}},  # FIXED: inverted
    # 2044: Removed - not used by Cloud API, values unreliable
    2026: {"name": "DHW Operation", "type": "enum", "values": {0: "off", 1: "on", 2: "scheduled"}},
    
    # Power/Load
    2129: {"name": "Current Power", "scale": 1, "unit": "W"},
    2327: {"name": "HP Load", "scale": 1, "unit": "%"},
    2329: {"name": "Heating Power", "scale": 1, "unit": "W"},
    
    # Pressure
    2325: {"name": "System Pressure", "scale": 0.1, "unit": "bar"},
    
    # Efficiency
    2371: {"name": "COP", "scale": 0.01, "unit": ""},
    2372: {"name": "SCOP", "scale": 0.01, "unit": ""},
    
    # Hours
    2090: {"name": "Op Hours Heating", "scale": 1, "unit": "h"},
    2091: {"name": "Op Hours DHW", "scale": 1, "unit": "h"},
    2095: {"name": "Op Hours Additional", "scale": 1, "unit": "h"},
    
    # Activations
    2155: {"name": "Activations Heating", "scale": 1, "unit": ""},
    2156: {"name": "Activations Cooling", "scale": 1, "unit": ""},
    2157: {"name": "Activations Boiler", "scale": 1, "unit": ""},
    2158: {"name": "Activations Defrost", "scale": 1, "unit": ""},
}

async def scan_and_compare():
    """Scan all registers and compare with expected mappings."""
    client = AsyncModbusTcpClient(host=HOST, port=PORT)
    
    try:
        connected = await client.connect()
        if not connected:
            print("❌ Failed to connect")
            return
        
        print("✅ Connected to Modbus device\n")
        print("=" * 120)
        print(f"{'Address':<10} {'Raw Value':<12} {'Scaled Value':<20} {'Expected Name':<40} {'Notes'}")
        print("=" * 120)
        
        issues = []
        
        for address in sorted(REGISTER_MAP.keys()):
            info = REGISTER_MAP[address]
            
            try:
                result = await client.read_holding_registers(address, count=1, slave=UNIT_ID)
                
                if result.isError():
                    print(f"{address:<10} ERROR        -                    {info['name']:<40} Read failed")
                    issues.append(f"Register {address} ({info['name']}): Read failed")
                    continue
                
                raw = result.registers[0]
                
                # Check for error values
                if raw in [64936, 64937, 65535, 65517, 65526]:
                    print(f"{address:<10} {raw:<12} ERROR VALUE         {info['name']:<40} Sensor not connected")
                    continue
                
                # Process value
                if info.get('type') == 'enum':
                    enum_val = info['values'].get(raw, f"unknown({raw})")
                    scaled_str = enum_val
                    unit_str = ""
                    notes = ""
                else:
                    scale = info.get('scale', 1)
                    scaled = raw * scale
                    unit = info.get('unit', '')
                    scaled_str = f"{scaled:.2f}"
                    unit_str = unit
                    
                    # Check for suspicious values
                    notes = ""
                    if unit == "°C" and (scaled < -60 or scaled > 100):
                        notes = "⚠️ SUSPICIOUS VALUE"
                        issues.append(f"Register {address} ({info['name']}): Value {scaled}°C seems wrong")
                    elif unit == "%" and (scaled < 0 or scaled > 100):
                        notes = "⚠️ OUT OF RANGE"
                        issues.append(f"Register {address} ({info['name']}): {scaled}% out of range")
                
                display_val = f"{scaled_str}{unit_str}"
                print(f"{address:<10} {raw:<12} {display_val:<20} {info['name']:<40} {notes}")
                
            except Exception as e:
                print(f"{address:<10} EXCEPTION    -                    {info['name']:<40} {e}")
                issues.append(f"Register {address} ({info['name']}): Exception - {e}")
        
        print("=" * 120)
        
        if issues:
            print(f"\n⚠️  ISSUES FOUND ({len(issues)}):")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print("\n✅ All registers reading normally!")
        
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(scan_and_compare())
