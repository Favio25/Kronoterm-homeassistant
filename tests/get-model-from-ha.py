#!/usr/bin/env python3
"""Get Kronoterm model from Home Assistant API."""

import requests
import json

HA_URL = "http://localhost:8123"

try:
    # Get all states
    response = requests.get(f"{HA_URL}/api/states", timeout=5)
    response.raise_for_status()
    
    states = response.json()
    
    # Find Kronoterm entities
    kronoterm_entities = [s for s in states if 'kronoterm' in s.get('entity_id', '').lower()]
    
    if kronoterm_entities:
        print(f"Found {len(kronoterm_entities)} Kronoterm entities\n")
        
        # Check first entity for device info
        entity = kronoterm_entities[0]
        print(f"Entity: {entity['entity_id']}")
        print(f"State: {entity['state']}")
        
        attrs = entity.get('attributes', {})
        
        # Look for model info
        for key in ['model', 'device_model', 'pump_model', 'pumpModel']:
            if key in attrs:
                print(f"\n✅ MODEL FOUND: {key} = {attrs[key]}")
        
        # Look for device info
        if 'device_info' in attrs:
            print(f"\nDevice Info: {json.dumps(attrs['device_info'], indent=2)}")
        
        # Show all attributes that might contain model
        print(f"\nAll attributes:")
        for key, value in attrs.items():
            if isinstance(value, (str, int, float)) and len(str(value)) < 100:
                print(f"  {key}: {value}")
    
    else:
        print("No Kronoterm entities found")

except Exception as e:
    print(f"Error: {e}")
