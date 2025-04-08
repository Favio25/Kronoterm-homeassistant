DOMAIN = "kronoterm"
BASE_URL = "https://cloud.kronoterm.com/jsoncgi.php"

# Default intervals/timeouts
DEFAULT_SCAN_INTERVAL = 5  # 5 minutes
REQUEST_TIMEOUT = 10       # 10 seconds
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY_BASE = 2       # seconds (will be raised to power of attempt number)

# DHW Modbus addresses
DHW_CURRENT_TEMP_ADDR = 2102      # "DHW Temperature"
DHW_DESIRED_TEMP_ADDR = 2023      # "Desired DHW Temperature"

# Loop 1 Modbus addresses
LOOP1_CURRENT_BASIC_ADDR = 2130
LOOP1_CURRENT_THERM_ADDR = 2160
LOOP1_DESIRED_TEMP_ADDR  = 2187
LOOP1_THERMOSTAT_FLAG_ADDR = 2192

# Loop 2 Modbus addresses
LOOP2_CURRENT_BASIC_ADDR = 2110
LOOP2_CURRENT_THERM_ADDR = 2161
LOOP2_DESIRED_TEMP_ADDR  = 2049
LOOP2_THERMOSTAT_FLAG_ADDR = 2193

# Reservoir address
RESERVOIR_TEMP_ADDR = 2101

# API Query params - grouped by purpose
API_QUERIES = {
    "main": {"TopPage": "5", "Subpage": "3"},
    "info": {"TopPage": "1", "Subpage": "1"},
    "dhw": {"TopPage": "1", "Subpage": "9", "Action": "1"},
    "loop1": {"TopPage": "1", "Subpage": "5", "Action": "1"},
    "loop2": {"TopPage": "1", "Subpage": "6", "Action": "1"},
    "switch": {"TopPage": "1", "Subpage": "3", "Action": "1"},
    "reservoir": {"TopPage": "1", "Subpage": "4", "Action": "1"},
    "shortcuts": {"TopPage": "1", "Subpage": "3"},
}

SENSOR_DEFINITIONS = [
    (2023, "Desired DHW Temperature", "°C", "mdi:water-boiler", 1),
    (2049, "Desired Loop 2 Temperature", "°C", "mdi:thermometer", 1),
    (2090, "Operating Hours Compressor Heating", "h", "mdi:timer-outline", 1),
    (2091, "Operating Hours Compressor DHW", "h", "mdi:timer-outline", 1),
    (2095, "Operating Hours Additional Source 1", "h", "mdi:timer-outline", 1),
    (2101, "Reservoir Temperature", "°C", "mdi:thermometer", 1),
    (2102, "DHW Temperature", "°C", "mdi:water-boiler", 1),
    (2103, "Outside Temperature", "°C", "mdi:weather-sunny", 1),
    (2104, "HP Outlet Temperature", "°C", "mdi:thermometer", 1),
    (2105, "Compressor Inlet Temperature", "°C", "mdi:thermometer", 1),
    (2106, "Compressor Outlet Temperature", "°C", "mdi:thermometer", 1),
    (2187, "Desired Loop 1 Temperature", "°C", "mdi:thermometer", 1),
    (2130, "Loop 1 Temperature", "°C", "mdi:thermometer", 0.1),
    (2110, "Loop 2 Temperature", "°C", "mdi:thermometer", 1),
    (2160, "Loop 1 Thermostat Temperature", "°C", "mdi:thermostat", 1),
    (2161, "Loop 2 Thermostat Temperature", "°C", "mdi:thermostat", 1),
    (2325, "Pressure Setting", "bar", "mdi:gauge", 1),
    (2326, "Heating System Pressure", "bar", "mdi:gauge", 1),
    (2327, "HP Load", "%", "mdi:engine", 1),
    (2329, "Current Heating/Cooling Capacity", "W", "mdi:lightning-bolt", 1),
    (2371, "COP Value", "", "mdi:chart-line", 0.01),
    (2372, "SCOP Value", "", "mdi:chart-line", 0.01),
    (2155, "Compressor Activations - Heating (24 h)", "", "mdi:counter", 1),
    (2157, "Boiler Activations (24 h)", "", "mdi:counter", 1),
    (2158, "Defrost Activations (24 h)", "", "mdi:snowflake-melt", 1),
    (2362, "Electrical Energy Heating + DHW", "kWh", "mdi:meter-electric", 1),
    (2364, "Heating Energy Heating + DHW", "kWh", "mdi:heat-wave", 1),
]

# Enum sensor definitions: (address, name, options, icon)
ENUM_SENSOR_DEFINITIONS = [
    (
        2001,
        "Working Function",
        {
            0: "Heating",
            1: "DHW",
            2: "Cooling",
            3: "Pool Heating",
            4: "Thermal Disinfection",
            5: "Standby",
            7: "Remote Deactivation",
        },
        "mdi:heat-pump",
    ),
    (
        2006,
        "Error/Warning",
        {0: "No Error", 1: "Warning", 2: "Error"},
        "mdi:alert",
    ),
    (
        2007,
        "Operation Regime",
        {0: "Cooling", 1: "Heating", 2: "Heating and Cooling Off"},
        "mdi:heat-pump",
    ),
]

diagnostic_sensor_addresses = {
    2090,  # Operating Hours Compressor Heating
    2091,  # Operating Hours Compressor DHW
    2095,  # Operating Hours Additional Source 1
    2104,  # HP Outlet Temperature
    2105,  # Compressor Inlet Temperature
    2106,  # Compressor Outlet Temperature
    2325,  # Pressure Setting
    2371,  # COP Value
    2372,  # SCOP Value
    2155,  # Compressor Activations - Heating (24 h)
    2157,  # Boiler Activations (24 h)
    2158,  # Defrost Activations (24 h)
}

# For enum sensors, if you want to mark them diagnostic as well:
diagnostic_enum_addresses = {
    2006,  # Error/Warning
}

# Additional constants
POOL_TEMP_ADDRESS = 2109
ALT_SOURCE_TEMP_ADDRESS = 2107
COMPRESSOR_ACTIVATIONS_COOLING = 2156
HEATING_SOURCE_PRESSURE_SET = 2347
SOURCE_PRESSURE = 2348