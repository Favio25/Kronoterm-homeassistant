#!/usr/bin/env python3
"""
Scan Kronoterm device information registers to find model number.
Looking for: ADAPT 0312, ADAPT 0416, ADAPT 0724, or similar.
"""

from pymodbus.client import ModbusTcpClient
import time

# Connection details
HOST = "10.0.0.51"
PORT = 502
UNIT_ID = 20

def decode_ascii(registers):
    """Decode list of registers to ASCII string."""
    chars = []
    for reg in registers:
        # Each register = 2 bytes = 2 ASCII characters
        high_byte = (reg >> 8) & 0xFF
        low_byte = reg & 0xFF
        if high_byte >= 32 and high_byte <= 126:  # Printable ASCII
            chars.append(chr(high_byte))
        if low_byte >= 32 and low_byte <= 126:
            chars.append(chr(low_byte))
    return ''.join(chars)

def scan_range_detailed(client, start, end):
    """Scan register range and try ASCII decoding."""
    results = []
    
    print(f"\n{'='*100}")
    print(f"SCANNING REGISTERS {start}-{end}")
    print(f"{'='*100}\n")
    
    # Read in chunks for ASCII decoding
    chunk_size = 20
    for chunk_start in range(start, end + 1, chunk_size):
        chunk_end = min(chunk_start + chunk_size - 1, end)
        
        try:
            result = client.read_holding_registers(
                address=chunk_start, 
                count=chunk_end - chunk_start + 1, 
                slave=UNIT_ID
            )
            
            if not result.isError():
                # Show individual registers
                for i, value in enumerate(result.registers):
                    addr = chunk_start + i
                    hex_val = f"0x{value:04X}"
                    
                    # Try to decode as ASCII chars
                    high = (value >> 8) & 0xFF
                    low = value & 0xFF
                    ascii_str = ""
                    if 32 <= high <= 126:
                        ascii_str += chr(high)
                    else:
                        ascii_str += "."
                    if 32 <= low <= 126:
                        ascii_str += chr(low)
                    else:
                        ascii_str += "."
                    
                    print(f"{addr:4d} | {value:5d} | {hex_val:8s} | '{ascii_str}' | {high:3d} {low:3d}")
                    results.append((addr, value))
                
                # Try to decode chunk as ASCII string
                ascii_decoded = decode_ascii(result.registers)
                if ascii_decoded.strip():
                    print(f"\n  → Chunk ASCII: '{ascii_decoded}'\n")
        
        except Exception as e:
            print(f"ERROR reading {chunk_start}-{chunk_end}: {e}")
        
        time.sleep(0.1)  # Small delay between chunks
    
    return results

def scan_individual(client, addresses):
    """Scan specific registers that might contain model info."""
    print(f"\n{'='*100}")
    print("SCANNING SPECIFIC REGISTERS")
    print(f"{'='*100}\n")
    
    for addr in addresses:
        try:
            result = client.read_holding_registers(address=addr, count=1, slave=UNIT_ID)
            
            if not result.isError():
                value = result.registers[0]
                hex_val = f"0x{value:04X}"
                
                high = (value >> 8) & 0xFF
                low = value & 0xFF
                ascii_str = ""
                if 32 <= high <= 126:
                    ascii_str += chr(high)
                else:
                    ascii_str += "."
                if 32 <= low <= 126:
                    ascii_str += chr(low)
                else:
                    ascii_str += "."
                
                print(f"{addr:4d} | {value:5d} | {hex_val:8s} | '{ascii_str}' | high={high:3d} low={low:3d}")
        
        except Exception as e:
            print(f"{addr:4d} | ERROR: {e}")

def main():
    print("="*100)
    print("KRONOTERM DEVICE INFORMATION SCAN")
    print("="*100)
    print(f"Target: {HOST}:{PORT}, Unit ID: {UNIT_ID}")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nLooking for: Model number (ADAPT 0312/0416/0724)")
    
    client = ModbusTcpClient(HOST, port=PORT)
    
    if not client.connect():
        print(f"\n❌ Failed to connect to {HOST}:{PORT}")
        return
    
    print(f"✅ Connected to Modbus TCP device\n")
    
    # Scan device information ranges
    print("\n" + "="*100)
    print("RANGE 5000-5099: Device ID, Serial, Firmware")
    scan_range_detailed(client, 5000, 5099)
    
    print("\n" + "="*100)
    print("RANGE 1-100: Sometimes contains device info")
    scan_range_detailed(client, 1, 50)
    
    print("\n" + "="*100)
    print("RANGE 9000-9050: Sometimes used for device info")
    scan_range_detailed(client, 9000, 9050)
    
    # Check specific registers that might contain model
    print("\n" + "="*100)
    print("Checking registers from kosl/kronoterm2mqtt repo...")
    
    specific_regs = [
        0,      # Sometimes device ID
        1,      # Sometimes model
        2,      # Sometimes serial
        100,    # Config start
        5054,   # Known device ID
        5055,   # Next to device ID
        5056,
        5057,
        5058,
    ]
    
    scan_individual(client, specific_regs)
    
    # Summary
    print(f"\n{'='*100}")
    print("SEARCH FOR MODEL STRING")
    print(f"{'='*100}\n")
    
    print("Looking for strings like: 'ADAPT', '0312', '0416', '0724'")
    print("\nIf model not found in Modbus, we can:")
    print("  1. Check /sys/class/dmi/id/ files on device")
    print("  2. Ask user to manually configure model")
    print("  3. Try to infer from power readings")
    
    client.close()

if __name__ == "__main__":
    main()
