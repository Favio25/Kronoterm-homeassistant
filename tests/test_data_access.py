"""Quick test to see what data the coordinator actually has"""
import asyncio
import sys
sys.path.insert(0, '/config/custom_components')

async def test():
    from homeassistant.core import HomeAssistant
    from custom_components.kronoterm import DOMAIN
    
    # This won't work outside HA, but shows the access pattern
    print("Testing data access pattern...")
    
test_data = {
    "main": {
        "ModbusReg": [
            {"address": 2103, "value": 3.8, "raw": 38, "name": "OUTDOOR_TEMP"},
            {"address": 546, "value": 38.1, "raw": 381, "name": "SUPPLY_TEMP"},
        ]
    }
}

# Test entity access
def get_modbus_value(data, address):
    main_data = data.get("main", {})
    modbus_reg = main_data.get("ModbusReg", [])
    return next(
        (reg.get("value") for reg in modbus_reg if reg.get("address") == address),
        None,
    )

print(f"Test outdoor temp (2103): {get_modbus_value(test_data, 2103)}")
print(f"Test supply temp (546): {get_modbus_value(test_data, 546)}")
print(f"Test missing (9999): {get_modbus_value(test_data, 9999)}")

if __name__ == "__main__":
    print("Data access pattern test complete")
