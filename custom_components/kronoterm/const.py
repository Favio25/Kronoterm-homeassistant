from typing import NamedTuple, Dict, List, Set, Any, Optional

DOMAIN = "kronoterm"
BASE_URL = "https://cloud.kronoterm.com/jsoncgi.php"
BASE_URL_DHW = "https://cloud.kronoterm.com/dhws/jsoncgi.php"

# ----------------------------------------------------------------------------
# Default intervals/timeouts
# ----------------------------------------------------------------------------
DEFAULT_SCAN_INTERVAL = 5  # 5 minutes
REQUEST_TIMEOUT = 10       # 10 seconds
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY_BASE = 2       # seconds (will be raised to power of attempt number)
SHORTCUT_DELAY_DEFAULT = 2 # seconds to wait after setting a shortcut
SHORTCUT_DELAY_STATE = 1   # seconds for heatpump_on state change

# ----------------------------------------------------------------------------
# Modbus addresses for dedicated platforms (e.g., water_heater, climate)
# ----------------------------------------------------------------------------

# DHW Modbus addresses (likely used by water_heater platform)
DHW_CURRENT_TEMP_ADDR = 2102
DHW_DESIRED_TEMP_ADDR = 2023

# Loop 1 Modbus addresses (likely used by climate platform)
LOOP1_CURRENT_BASIC_ADDR = 2130
LOOP1_CURRENT_THERM_ADDR = 2160
LOOP1_DESIRED_TEMP_ADDR  = 2187
LOOP1_THERMOSTAT_FLAG_ADDR = 2192

# Loop 2 Modbus addresses (likely used by climate platform)
LOOP2_CURRENT_BASIC_ADDR = 2110
LOOP2_CURRENT_THERM_ADDR = 2161
LOOP2_DESIRED_TEMP_ADDR  = 2049
LOOP2_THERMOSTAT_FLAG_ADDR = 2193

# Reservoir address (likely used by climate or sensor platform)
RESERVOIR_TEMP_ADDR = 2101

# ----------------------------------------------------------------------------
# API Query definitions
# ----------------------------------------------------------------------------
# Queries for GETting data (fetching state)
API_QUERIES_GET = {
    "menu": {"Menu": "1"},
    "main": {"TopPage": "5", "Subpage": "3"},
    "info": {"TopPage": "1", "Subpage": "1"},
    "shortcuts": {"TopPage": "1", "Subpage": "3"},
    "reservoir": {"TopPage": "1", "Subpage": "4"},
    "loop1": {"TopPage": "1", "Subpage": "5"},
    "loop2": {"TopPage": "1", "Subpage": "6"},
    "loop3": {"TopPage": "1", "Subpage": "7"},
    "loop4": {"TopPage": "1", "Subpage": "8"},
    "dhw": {"TopPage": "1", "Subpage": "9"},
    "consumption": {"TopPage": "4", "Subpage": "4", "Action": "4"},
    "main_settings": {"TopPage": "3", "Subpage": "11"},
    "system_data": {"TopPage": "1", "Subpage": "2"},
}

# Queries for SETting data (sending commands, POST)
API_QUERIES_SET = {
    "switch": {"TopPage": "1", "Subpage": "3", "Action": "1"},
    "reservoir": {"TopPage": "1", "Subpage": "4", "Action": "1"},
    "loop1": {"TopPage": "1", "Subpage": "5", "Action": "1"},
    "loop2": {"TopPage": "1", "Subpage": "6", "Action": "1"},
    "loop3": {"TopPage": "1", "Subpage": "7", "Action": "1"},
    "loop4": {"TopPage": "1", "Subpage": "8", "Action": "1"},
    "dhw": {"TopPage": "1", "Subpage": "9", "Action": "1"},
    "main_settings": {"TopPage": "3", "Subpage": "11", "Action": "1"},
}

# API Queries for DHW Cloud (https://cloud.kronoterm.com/dhws/)
API_QUERIES_GET_DHW = {
    "menu": {"Menu": "1"},
    "main": {"TopPage": "1", "Subpage": "1"},
    "shortcuts": {"TopPage": "1", "Subpage": "2"},
    "schedule": {"TopPage": "1", "Subpage": "3"},
    "alarms": {"TopPage": "1", "Subpage": "4"},
}

API_QUERIES_SET_DHW = {
    "main": {"TopPage": "1", "Subpage": "1", "Action": "1"},
    "shortcuts": {"TopPage": "1", "Subpage": "2", "Action": "1"},
    "schedule": {"TopPage": "1", "Subpage": "3", "Action": "1"},
}

# Maps page numbers to the correct API_QUERIES_SET key
PAGE_TO_SET_QUERY_KEY = {
    4: "reservoir",
    5: "loop1",
    6: "loop2",
    7: "loop3",
    8: "loop4",
    9: "dhw",
}

# ----------------------------------------------------------------------------
# API Parameter Names (for POST form data)
# ----------------------------------------------------------------------------
API_PARAM_KEYS = {
    # Page parameters
    "TEMP": "circle_temp",
    "MODE": "circle_status",
    # Shortcut (switch) parameters
    "HEAT_PUMP": "heatpump_on",
    "ANTILEGIONELLA": "antilegionella",
    "CIRCULATION": "circulation_on",
    "FAST_HEATING": "water_heating_on",
    "RESERVE_SOURCE": "reserve_source_on",  # Fixed: was "reserve_source"
    "ADDITIONAL_SOURCE": "additional_source_on",  # Fixed: was "additional_source"
    # Main settings parameters
    "MAIN_MODE": "main_mode",
}

# Operational mode mapping (ECO/Auto/Comfort)
MAIN_MODE_OPTIONS = {
    0: "auto",
    1: "eco",
    2: "comfort",
}

# Base form data for consumption fetching (date params added dynamically)
CONSUMPTION_FORM_BASE = [
    # aValues:
    ("aValues[]", "17"),
    # dValues:
    ("dValues[]", "90"),
    ("dValues[]", "0"),
    ("dValues[]", "91"),
    ("dValues[]", "92"),
    ("dValues[]", "1"),
    ("dValues[]", "2"),
    ("dValues[]", "24"),
    ("dValues[]", "71"),
]


# ----------------------------------------------------------------------------
# Sensor definitions (for generic sensor platform)
# ----------------------------------------------------------------------------

class SensorDefinition(NamedTuple):
    """A definition for a standard numeric sensor."""
    address: int
    key: str  # Translation key
    unit: Optional[str]
    icon: str
    scaling: float = 1.0
    diagnostic: bool = False

class EnumSensorDefinition(NamedTuple):
    """A definition for a sensor with enumerated string values."""
    address: int
    key: str  # Translation key
    options: Dict[int, str]
    icon: str
    diagnostic: bool = False

# List of all standard sensors to be created.
SENSOR_DEFINITIONS: List[SensorDefinition] = [
    # 500-range registers are Modbus-only, not available in Cloud API
    # They are auto-created from kronoterm.json in Modbus mode
    # 2000-range: Control/status registers
    # (2023, "Desired DHW Temperature", "°C", "mdi:water-boiler", 1),       # Handled by water_heater
    # (2049, "Desired Loop 2 Temperature", "°C", "mdi:thermometer", 1),    # Handled by climate
    # (2101, "Reservoir Temperature", "°C", "mdi:thermometer", 1),          # Handled by climate/sensor
    # (2102, "DHW Temperature", "°C", "mdi:water-boiler", 1),               # Handled by water_heater
    # (2187, "Desired Loop 1 Temperature", "°C", "mdi:thermometer", 1),    # Handled by climate
    
    # Diagnostic Sensors
    # Note: Cloud API returns raw values WITHOUT scaling, Modbus applies scaling from kronoterm.json
    SensorDefinition(2090, "operating_hours_compressor_heating", "h", "mdi:timer-outline", 1.0, True),
    SensorDefinition(2091, "operating_hours_compressor_dhw", "h", "mdi:timer-outline", 1.0, True),
    SensorDefinition(2095, "operating_hours_additional_source_1", "h", "mdi:timer-outline", 1.0, True),
    SensorDefinition(2104, "hp_outlet_temperature", "°C", "mdi:thermometer", 1.0, True),  # Cloud API: no scaling
    SensorDefinition(2101, "hp_inlet_temperature", "°C", "mdi:thermometer", 1.0, True),  # Cloud API: no scaling
    SensorDefinition(2105, "temperature_compressor_inlet", "°C", "mdi:thermometer", 1.0, True),  # Cloud API: no scaling
    SensorDefinition(2106, "temperature_compressor_outlet", "°C", "mdi:thermometer", 1.0, True),  # Cloud API: no scaling
    SensorDefinition(2371, "cop_value", "", "mdi:chart-line", 0.01, True),
    SensorDefinition(2372, "scop_value", "", "mdi:chart-line", 0.01, True),
    SensorDefinition(2155, "compressor_activations_heating", "", "mdi:counter", 1, True),
    SensorDefinition(2157, "activations_boiler", "", "mdi:counter", 1, True),
    SensorDefinition(2158, "activations_defrost", "", "mdi:snowflake-melt", 1, True),
    SensorDefinition(2156, "compressor_activations_cooling", "", "mdi:counter", 1, True),

    # Standard Sensors
    # Note: Cloud API returns raw values WITHOUT scaling, Modbus applies scaling from kronoterm.json
    SensorDefinition(2103, "temperature_outside", "°C", "mdi:weather-sunny", 1.0),  # Cloud API: no scaling
    # Loop 1 & 2 temperature sensors removed - handled by climate entities
    # SensorDefinition(2130, "loop_1_temperature", "°C", "mdi:thermometer", 0.1),
    # SensorDefinition(2110, "loop_2_temperature", "°C", "mdi:thermometer", 0.1),
    SensorDefinition(2160, "loop_1_thermostat_temperature", "°C", "mdi:thermostat", 1.0),  # Cloud API: no scaling
    SensorDefinition(2161, "loop_2_thermostat_temperature", "°C", "mdi:thermostat", 1.0),  # Cloud API: no scaling
    SensorDefinition(2162, "loop_3_thermostat_temperature", "°C", "mdi:thermostat", 1.0),  # Cloud API: no scaling
    SensorDefinition(2163, "loop_4_thermostat_temperature", "°C", "mdi:thermostat", 1.0),  # Cloud API: no scaling
    SensorDefinition(2325, "heating_system_pressure", "bar", "mdi:gauge", 1.0),  # Cloud API: no scaling
    SensorDefinition(2327, "hp_load", "%", "mdi:engine", 1.0),
    SensorDefinition(2129, "current_heating_cooling_power", "W", "mdi:lightning-bolt", 1.0),
    SensorDefinition(2362, "electrical_energy_heating_dhw", "kWh", "mdi:meter-electric", 1.0),
    SensorDefinition(2364, "heating_energy_heating_dhw", "kWh", "mdi:heat-wave", 1.0),

    # Sensors previously in "Additional constants"
    SensorDefinition(2107, "alternative_source_temperature", "°C", "mdi:thermometer", 0.1),
]

# List of all enumeration sensors to be created.
ENUM_SENSOR_DEFINITIONS: List[EnumSensorDefinition] = [
    EnumSensorDefinition(
        2001,
        "working_function",
        {
            0: "heating",
            1: "dhw",
            2: "cooling",
            3: "pool_heating",
            4: "thermal_disinfection",
            5: "standby",
            7: "remote_deactivation",
        },
        "mdi:heat-pump",
    ),
    EnumSensorDefinition(
        2006,
        "error_warning",
        {
            0: "no_error",
            1: "warning",
            2: "error",
        },
        "mdi:alert",
        diagnostic=True  # Mark this as a diagnostic sensor
    ),
    EnumSensorDefinition(
        2007,
        "operation_regime",
        {
            0: "cooling",
            1: "heating",
            2: "heating_and_cooling_off",
        },
        "mdi:heat-pump",
    ),
]

# ----------------------------------------------------------------------------
# Auto-generated Diagnostic Sets
# ----------------------------------------------------------------------------
diagnostic_sensor_addresses: Set[int] = {
    s.address for s in SENSOR_DEFINITIONS if s.diagnostic
}

diagnostic_enum_addresses: Set[int] = {
    s.address for s in ENUM_SENSOR_DEFINITIONS if s.diagnostic
}