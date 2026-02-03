#!/usr/bin/env python3
"""
Re-scan Kronoterm Modbus registers 2000-2400 with detailed interpretation.
Focus on registers found in kosl/kronoterm2mqtt repo.
"""

from pymodbus.client import ModbusTcpClient
import time

# Connection details
HOST = "10.0.0.51"
PORT = 502
UNIT_ID = 20

# Known registers from GitHub repo
KNOWN_REGISTERS = {
    2000: ("System operation", "binary", None),
    2001: ("Working function", "enum", {0: "heating", 1: "DHW", 2: "cooling", 3: "pool heating", 4: "thermal disinfection", 5: "standby", 7: "remote deactivation"}),
    2002: ("Additional source status", "bits", {0: "Activation", 4: "Active"}),
    2006: ("Error/warning status", "enum", {0: "no error", 1: "warning", 2: "error"}),
    2007: ("Operation regime", "enum", {0: "cooling", 1: "heating", 2: "off"}),
    2015: ("Fast DHW heating", "switch", None),
    2016: ("Additional Source", "switch", None),
    2023: ("Desired DHW temperature", "temp", 0.1),
    2024: ("Current desired DHW temperature", "temp", 0.1),
    2026: ("DHW Operation", "enum", {0: "Off", 1: "On", 2: "Scheduled"}),
    2028: ("DHW pumps", "bits", {0: "DHW circulation", 1: "DHW tank circulation"}),
    2044: ("Loop 1 operation status", "enum", {0: "off", 1: "normal", 2: "ECO", 3: "COM"}),
    2045: ("Loop 1 circulation pump", "binary", None),
    2047: ("Loop 1 temp offset in ECO", "temp", 0.1),
    2049: ("Loop 2 setpoint", "temp", 0.1),
    2055: ("Loop 2 circulation pump", "binary", None),
    2090: ("Operating hours compressor heating", "hours", 1),
    2091: ("Operating hours compressor DHW", "hours", 1),
    2095: ("Operating hours additional source", "hours", 1),
    2101: ("HP inlet temperature", "temp", 0.1),
    2102: ("DHW/Outdoor temperature", "temp", 0.1),
    2103: ("Outside/Unknown temperature", "temp", 0.1),
    2104: ("HP outlet temperature", "temp", 0.1),
    2105: ("Evaporating temperature", "temp", 0.1),
    2106: ("Compressor temperature", "temp", 0.1),
    2107: ("Alternative source temperature", "temp", 0.1),
    2109: ("Pool temperature", "temp", 0.1),
    2110: ("Loop 2 temperature", "temp", 0.1),
    2129: ("Current power consumption", "power", 1),
    2130: ("Loop 1 temperature", "temp", 0.1),
    2160: ("Loop 1 thermostat temperature", "temp", 0.1),
    2161: ("Loop 2 thermostat temperature", "temp", 0.1),
    2187: ("Loop 1 setpoint", "temp", 0.1),
    2325: ("Setting of the pressure", "pressure", 0.1),
    2326: ("Heating system pressure", "pressure", 0.1),
    2327: ("Current HP load", "percent", 1),
    2328: ("Circulation of sanitary water", "switch", None),
    2329: ("Current heating power", "power", 1),
    2347: ("Setting pressure of heating source", "pressure", 0.1),
    2348: ("Source pressure", "pressure", 0.1),
    2371: ("COP", "cop", 0.01),
    2372: ("SCOP", "cop", 0.01),
}

def read_bit(value, bit):
    """Extract specific bit from value."""
    return bool((value >> bit) & 1)

def format_value(register, raw_value, reg_type, scale_or_map):
    """Format register value based on type."""
    if raw_value == 0 and reg_type not in ["binary", "enum", "bits"]:
        return "0 (might be standby/inactive)"
    
    if raw_value in [64936, 64937, 65535]:
        return f"{raw_value} (ERROR/NOT CONNECTED)"
    
    if reg_type == "temp":
        scaled = raw_value * scale_or_map
        return f"{scaled:.1f}°C (raw: {raw_value})"
    
    elif reg_type == "pressure":
        scaled = raw_value * scale_or_map
        return f"{scaled:.1f} bar (raw: {raw_value})"
    
    elif reg_type == "power":
        return f"{raw_value}W"
    
    elif reg_type == "percent":
        return f"{raw_value}%"
    
    elif reg_type == "hours":
        return f"{raw_value}h"
    
    elif reg_type == "cop":
        scaled = raw_value * scale_or_map
        return f"{scaled:.2f} (raw: {raw_value})"
    
    elif reg_type == "binary":
        return "ON" if raw_value else "OFF"
    
    elif reg_type == "enum" and scale_or_map:
        label = scale_or_map.get(raw_value, f"UNKNOWN({raw_value})")
        return f"{raw_value} = {label}"
    
    elif reg_type == "bits" and scale_or_map:
        bits_str = []
        for bit, name in scale_or_map.items():
            state = "ON" if read_bit(raw_value, bit) else "OFF"
            bits_str.append(f"bit{bit}({name})={state}")
        return f"{raw_value:016b} | " + ", ".join(bits_str)
    
    elif reg_type == "switch":
        return "ON" if raw_value else "OFF"
    
    else:
        return str(raw_value)

def scan_range(client, start, end):
    """Scan register range and return results."""
    results = []
    
    print(f"\n{'='*100}")
    print(f"SCANNING REGISTERS {start}-{end}")
    print(f"{'='*100}\n")
    
    for addr in range(start, end + 1):
        try:
            result = client.read_holding_registers(address=addr, count=1, slave=UNIT_ID)
            
            if not result.isError():
                value = result.registers[0]
                
                # Only show non-zero or known registers
                if value != 0 or addr in KNOWN_REGISTERS:
                    name, reg_type, scale_or_map = KNOWN_REGISTERS.get(addr, ("Unknown", "raw", None))
                    formatted = format_value(addr, value, reg_type, scale_or_map)
                    
                    # Highlight important registers
                    marker = ""
                    if addr in [2001, 2327, 2130, 2326, 2329, 2129]:
                        marker = " ⭐ CRITICAL"
                    elif addr in [2002, 2028, 2045, 2055]:
                        marker = " 🔵 PUMP/HEATER"
                    elif addr in KNOWN_REGISTERS:
                        marker = " ✅ KNOWN"
                    
                    print(f"{addr:4d} | {name:40s} | {formatted}{marker}")
                    results.append((addr, value, name))
        
        except Exception as e:
            if addr in KNOWN_REGISTERS:
                print(f"{addr:4d} | ERROR: {e}")
    
    return results

def main():
    print("="*100)
    print("KRONOTERM MODBUS RE-SCAN: Registers 2000-2400")
    print("="*100)
    print(f"Target: {HOST}:{PORT}, Unit ID: {UNIT_ID}")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    client = ModbusTcpClient(HOST, port=PORT)
    
    if not client.connect():
        print(f"\n❌ Failed to connect to {HOST}:{PORT}")
        return
    
    print(f"✅ Connected to Modbus TCP device\n")
    
    # Scan in chunks
    results = []
    results += scan_range(client, 2000, 2099)
    results += scan_range(client, 2100, 2199)
    results += scan_range(client, 2200, 2299)
    results += scan_range(client, 2300, 2400)
    
    # Summary
    print(f"\n{'='*100}")
    print("SUMMARY")
    print(f"{'='*100}\n")
    
    critical_regs = [
        (2001, "Working function"),
        (2327, "HP Load %"),
        (2130, "Loop 1 Current Temp"),
        (2326, "System Pressure"),
        (2129, "Current Power"),
        (2329, "Heating Power"),
        (2002, "Additional Source (bits)"),
        (2028, "DHW Pumps (bits)"),
        (2045, "Loop 1 Pump"),
        (2055, "Loop 2 Pump"),
    ]
    
    print("CRITICAL REGISTERS STATUS:")
    for addr, expected_name in critical_regs:
        found = next((r for r in results if r[0] == addr), None)
        if found:
            _, value, name = found
            if value == 0:
                print(f"  ⚠️  {addr:4d} ({expected_name:30s}) = 0 (might be standby)")
            else:
                print(f"  ✅ {addr:4d} ({expected_name:30s}) = {value}")
        else:
            print(f"  ❌ {addr:4d} ({expected_name:30s}) = NOT READ")
    
    print(f"\nTotal registers with data: {len(results)}")
    print(f"Scan completed: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    client.close()

if __name__ == "__main__":
    main()
