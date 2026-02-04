#!/usr/bin/env python3
"""
Test script for Kronoterm Home Assistant integration.
Validates all entities are available and working properly.
"""

import requests
import json
import sys
from typing import Dict, List, Any
from collections import defaultdict

# Configuration
HA_URL = "http://localhost:8123"
HA_TOKEN = None  # Will prompt if not set

# Expected entity counts by mode
EXPECTED_COUNTS_MODBUS = {
    "sensor": 112,  # 112 sensors from Modbus register reads
    "binary_sensor": 2,  # system_on, error_status (from Modbus)
    "switch": 0,
    "number": 0,
    "select": 0,
    "climate": 4,  # DHW, Loop1, Loop2, Reservoir
}

EXPECTED_COUNTS_CLOUD = {
    "sensor": 31,  # Cloud API sensors
    "binary_sensor": 6,  # Circulation pumps, defrost, etc.
    "switch": 6,  # Additional source, antilegionella, etc.
    "number": 10,  # Comfort/eco offsets
    "select": 4,  # Operation modes
    "climate": 4,  # DHW, Loop1, Loop2, Reservoir
}

# Error value that indicates invalid reading
ERROR_VALUE = 64936
SIGNED_ERROR = -600  # 64936 as signed int


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def get_ha_token() -> str:
    """Get HA token from environment or prompt."""
    import os
    token = os.environ.get('HA_TOKEN')
    if not token:
        print(f"{Colors.YELLOW}Enter your Home Assistant Long-Lived Access Token:{Colors.END}")
        token = input().strip()
    return token


def detect_mode_from_entities(kronoterm_entities: Dict[str, List[Dict]]) -> str:
    """Detect mode based on entity counts (more reliable than API)."""
    sensor_count = len(kronoterm_entities.get("sensor", []))
    
    # Modbus has ~112 sensors, Cloud has ~31
    if sensor_count >= 100:
        return "modbus"
    elif sensor_count >= 20 and sensor_count < 50:
        return "cloud"
    else:
        return "unknown"


def get_all_entities(ha_url: str, token: str) -> List[Dict[str, Any]]:
    """Fetch all entities from Home Assistant."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    
    response = requests.get(f"{ha_url}/api/states", headers=headers)
    response.raise_for_status()
    return response.json()


def filter_kronoterm_entities(entities: List[Dict]) -> Dict[str, List[Dict]]:
    """Filter and group Kronoterm entities by domain."""
    kronoterm = defaultdict(list)
    
    for entity in entities:
        entity_id = entity.get("entity_id", "")
        # Match entities that belong to kronoterm integration
        # They typically have unique_id with "kronoterm" or are in kronoterm device
        attributes = entity.get("attributes", {})
        
        # Check if it's a kronoterm entity (via integration or device)
        if "kronoterm" in attributes.get("friendly_name", "").lower() or \
           entity_id.startswith("sensor.kronoterm_") or \
           entity_id.startswith("climate.kronoterm_") or \
           entity_id.startswith("binary_sensor.kronoterm_"):
            domain = entity_id.split(".")[0]
            kronoterm[domain].append(entity)
    
    return kronoterm


def check_entity_health(entity: Dict) -> tuple[bool, List[str]]:
    """Check if an entity is healthy and return issues."""
    issues = []
    entity_id = entity.get("entity_id")
    state = entity.get("state")
    attributes = entity.get("attributes", {})
    
    # Check if unavailable
    if state in ["unavailable", "unknown"]:
        issues.append(f"State is {state}")
        return False, issues
    
    # Check for generic/missing friendly names
    friendly_name = attributes.get("friendly_name", "")
    if not friendly_name or friendly_name == "Unknown":
        issues.append("Missing or generic friendly name")
    
    # Check for error values in sensors
    if entity_id.startswith("sensor."):
        try:
            numeric_state = float(state)
            if numeric_state == ERROR_VALUE or numeric_state == SIGNED_ERROR:
                issues.append(f"Error value detected: {numeric_state}")
            # Check for unreasonable temperature values (if it's a temp sensor)
            if "temperature" in entity_id.lower():
                if numeric_state < -50 or numeric_state > 100:
                    issues.append(f"Unreasonable temperature: {numeric_state}°C")
        except (ValueError, TypeError):
            # Not a numeric sensor, that's fine
            pass
    
    # Check climate entities
    if entity_id.startswith("climate."):
        current_temp = attributes.get("current_temperature")
        target_temp = attributes.get("temperature")
        
        if current_temp is None:
            issues.append("Missing current_temperature")
        if target_temp is None:
            issues.append("Missing target temperature")
    
    return len(issues) == 0, issues


def print_summary(kronoterm_entities: Dict[str, List[Dict]], mode: str):
    """Print summary of entity counts and health."""
    # Select expected counts based on mode
    if mode == "modbus":
        expected_counts = EXPECTED_COUNTS_MODBUS
        mode_display = f"{Colors.BLUE}Modbus{Colors.END}"
    elif mode == "cloud":
        expected_counts = EXPECTED_COUNTS_CLOUD
        mode_display = f"{Colors.BLUE}Cloud API{Colors.END}"
    else:
        expected_counts = {}
        mode_display = f"{Colors.YELLOW}Unknown{Colors.END}"
    
    print(f"\n{Colors.BOLD}=== Kronoterm Entity Summary ==={Colors.END}")
    print(f"Mode: {mode_display}\n")
    
    total_entities = 0
    healthy_entities = 0
    entity_issues = []
    
    for domain, entities in sorted(kronoterm_entities.items()):
        count = len(entities)
        total_entities += count
        expected = expected_counts.get(domain, "?")
        
        # Count healthy entities
        healthy_count = 0
        for entity in entities:
            is_healthy, issues = check_entity_health(entity)
            if is_healthy:
                healthy_count += 1
            else:
                entity_issues.append((entity["entity_id"], issues))
        
        healthy_entities += healthy_count
        
        # Color code based on health
        if healthy_count == count:
            color = Colors.GREEN
            status = "✓"
        elif healthy_count > 0:
            color = Colors.YELLOW
            status = "⚠"
        else:
            color = Colors.RED
            status = "✗"
        
        print(f"{color}{status} {domain:20s} {healthy_count:3d}/{count:3d} healthy "
              f"(expected: {expected}){Colors.END}")
    
    print(f"\n{Colors.BOLD}Total: {healthy_entities}/{total_entities} entities healthy{Colors.END}")
    
    # Print issues if any
    if entity_issues:
        print(f"\n{Colors.BOLD}{Colors.RED}=== Issues Found ==={Colors.END}\n")
        for entity_id, issues in entity_issues:
            print(f"{Colors.RED}✗ {entity_id}{Colors.END}")
            for issue in issues:
                print(f"  - {issue}")
    else:
        print(f"\n{Colors.GREEN}✓ All entities are healthy!{Colors.END}")
    
    return len(entity_issues) == 0


def print_detailed_report(kronoterm_entities: Dict[str, List[Dict]]):
    """Print detailed entity report."""
    print(f"\n{Colors.BOLD}=== Detailed Entity Report ==={Colors.END}\n")
    
    for domain, entities in sorted(kronoterm_entities.items()):
        print(f"\n{Colors.BOLD}{Colors.BLUE}{domain.upper()} ({len(entities)} entities){Colors.END}")
        print("-" * 80)
        
        for entity in sorted(entities, key=lambda e: e["entity_id"]):
            entity_id = entity["entity_id"]
            state = entity["state"]
            friendly_name = entity.get("attributes", {}).get("friendly_name", "N/A")
            
            is_healthy, issues = check_entity_health(entity)
            status_icon = f"{Colors.GREEN}✓{Colors.END}" if is_healthy else f"{Colors.RED}✗{Colors.END}"
            
            print(f"{status_icon} {entity_id:50s} {state:15s} {friendly_name}")
            
            if issues:
                for issue in issues:
                    print(f"  {Colors.RED}└─ {issue}{Colors.END}")


def main():
    """Main test function."""
    print(f"{Colors.BOLD}Kronoterm Integration Entity Test{Colors.END}\n")
    
    # Get token
    token = get_ha_token()
    
    print(f"Connecting to Home Assistant at {HA_URL}...")
    
    try:
        # Fetch all entities
        all_entities = get_all_entities(HA_URL, token)
        print(f"✓ Fetched {len(all_entities)} total entities")
        
        # Filter Kronoterm entities
        kronoterm_entities = filter_kronoterm_entities(all_entities)
        
        if not kronoterm_entities:
            print(f"{Colors.RED}✗ No Kronoterm entities found!{Colors.END}")
            print(f"  Make sure the integration is loaded and entities are created.")
            return 1
        
        # Detect mode from entity counts
        mode = detect_mode_from_entities(kronoterm_entities)
        
        # Print summary
        all_healthy = print_summary(kronoterm_entities, mode)
        
        # Ask if user wants detailed report
        print(f"\n{Colors.YELLOW}Show detailed entity report? [y/N]{Colors.END} ", end="")
        if input().strip().lower() == 'y':
            print_detailed_report(kronoterm_entities)
        
        return 0 if all_healthy else 1
        
    except requests.exceptions.RequestException as e:
        print(f"{Colors.RED}✗ Error connecting to Home Assistant: {e}{Colors.END}")
        return 1
    except Exception as e:
        print(f"{Colors.RED}✗ Unexpected error: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
