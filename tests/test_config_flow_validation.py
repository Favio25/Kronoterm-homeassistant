#!/usr/bin/env python3
"""
Test the config flow validation function.
This tests what happens when user submits the Modbus config form.
"""

import asyncio
import sys

# Add the integration to path
sys.path.insert(0, '/home/frelih/.openclaw/workspace/kronoterm-integration/custom_components/kronoterm')

from config_flow_modbus import validate_modbus_connection

async def test_validation():
    """Test the validation function."""
    print("=" * 60)
    print("Testing Modbus Config Flow Validation")
    print("=" * 60)
    
    # Test data (what user would enter in UI)
    test_data = {
        "host": "10.0.0.51",
        "port": 502,
        "unit_id": 20,
        "model": "adapt_0416",
    }
    
    print(f"\nTest data: {test_data}\n")
    print("Calling validate_modbus_connection()...")
    
    error = await validate_modbus_connection(test_data)
    
    if error is None:
        print("✅ Validation PASSED - connection successful!")
        return True
    else:
        print(f"❌ Validation FAILED - error code: {error}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_validation())
    sys.exit(0 if success else 1)
